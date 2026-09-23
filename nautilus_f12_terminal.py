#!/usr/bin/env python3
"""
Nautilus F12 Embedded Terminal Extension
Target Environment: Ubuntu 22.04+ | GNOME 42+ (GTK4 / GTK3) | Wayland / X11 | python3-nautilus

Bulletproof Guardrails & Architecture:
- GTK4 / Nautilus 4.0 First-Class API: Strictly uses GTK4 layout models (append, set_child, set_visible, unparent).
- Wayland-Compatible F12 Keybinding: Binds directly to the Nautilus Application Window using Gtk.EventControllerKey.
- Asynchronous Shell Execution: Non-blocking Vte.Terminal.spawn_async prevents any UI freezing.
- State Machine & Execution Matrix:
  * F12 (First Run): Injects VTE widget, asynchronously spawns shell in active Nautilus directory, reveals & focuses.
  * F12 (Toggle Hide/Show): Toggles visibility; keeps background process alive; syncs cwd on Show.
  * Ctrl+D / Exit: Cleans up terminated process state, hides widget, and resets VTE instance.
  * F12 (After Exit): Detects dead state, resets, and spawns a fresh shell in active directory.
  * Window Close / Navigation: Cleans up subprocesses and reparents widgets safely.
"""

import os
import sys
import shlex
import signal
import logging
import gi

# Setup logging
logging.basicConfig(level=logging.INFO, format="[Nautilus-F12] %(levelname)s: %(message)s")
logger = logging.getLogger("nautilus-f12")

# Require Introspection Namespaces
try:
    gi.require_version("Nautilus", "4.0")
except (ValueError, AttributeError):
    try:
        gi.require_version("Nautilus", "3.0")
    except (ValueError, AttributeError):
        pass

try:
    gi.require_version("Gtk", "4.0")
except (ValueError, AttributeError):
    try:
        gi.require_version("Gtk", "3.0")
    except (ValueError, AttributeError):
        pass

try:
    gi.require_version("Vte", "3.91")  # GTK4 VTE namespace
except (ValueError, AttributeError):
    try:
        gi.require_version("Vte", "2.91")  # Standard VTE namespace
    except (ValueError, AttributeError):
        pass

from gi.repository import GObject, Gtk, Gdk, GLib, Gio, Pango

try:
    from gi.repository import Vte
except ImportError:
    Vte = None
    logger.error("Vte introspection library missing. Please install gir1.2-vte-2.91 / vte-gtk4.")

try:
    from gi.repository import Nautilus
except ImportError:
    Nautilus = None
    logger.error("Nautilus introspection library missing. Please install python3-nautilus.")


# Detect GTK major version
GTK_VERSION = Gtk.get_major_version() if hasattr(Gtk, "get_major_version") else 3
IS_GTK4 = GTK_VERSION >= 4


def uri_to_path(uri: str) -> str:
    """Converts a Nautilus GVFS URI to a verified local filesystem path."""
    if not uri:
        return os.path.expanduser("~")
    try:
        gfile = Gio.File.new_for_uri(uri)
        path = gfile.get_path()
        if path and os.path.isdir(path):
            return path
    except Exception as exc:
        logger.debug(f"Could not convert URI {uri} to path: {exc}")
    return os.path.expanduser("~")


class WindowTerminalManager:
    """
    Manages an embedded VTE terminal for a single Nautilus window.
    Implements the complete lifecycle and execution matrix.
    """

    def __init__(self, window: Gtk.Window, extension_ref=None):
        self.window = window
        self.extension_ref = extension_ref
        
        self.current_uri = None
        self.current_path = os.path.expanduser("~")
        self.last_synced_path = None
        
        # Process State
        self.vte = None
        self.pid = None
        self.is_running = False
        self.is_visible = False
        
        # GTK Widgets
        self.container_box = None
        self.scrolled_window = None
        self.separator = None
        
        self._build_ui_containers()
        self._install_key_controller()
        self._connect_window_signals()

    def _build_ui_containers(self):
        """Constructs UI container tree using GTK4 APIs."""
        if IS_GTK4:
            self.container_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.container_box.set_visible(False)
            
            self.scrolled_window = Gtk.ScrolledWindow()
            self.scrolled_window.set_vexpand(False)
            self.scrolled_window.set_hexpand(True)
            self.scrolled_window.set_min_content_height(240)
            self.scrolled_window.set_size_request(-1, 240)
            
            self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            
            self.container_box.append(self.scrolled_window)
            self.container_box.append(self.separator)
        else:
            self.container_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.container_box.set_no_show_all(True)
            self.container_box.hide()
            
            self.scrolled_window = Gtk.ScrolledWindow()
            self.scrolled_window.set_min_content_height(240)
            self.scrolled_window.set_size_request(-1, 240)
            
            self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
            
            self.container_box.pack_start(self.scrolled_window, True, True, 0)
            self.container_box.pack_start(self.separator, False, False, 0)

    def _install_key_controller(self):
        """
        Binds F12 key listener to the top-level Nautilus window.
        Uses Gtk.EventControllerKey to guarantee Wayland compliance.
        """
        if hasattr(self.window, "_f12_terminal_controller_installed"):
            return
        
        if IS_GTK4:
            controller = Gtk.EventControllerKey.new()
            controller.connect("key-pressed", self._on_key_pressed)
            self.window.add_controller(controller)
        else:
            self.window.connect("key-press-event", self._on_key_press_gtk3)
            
        self.window._f12_terminal_controller_installed = True
        logger.info("Attached F12 EventControllerKey to Nautilus window.")

    def _connect_window_signals(self):
        """Connects window destruction to clean up child shell processes."""
        self.window.connect("destroy", self._on_window_destroy)

    def _on_window_destroy(self, widget):
        """Kills any active shell process when the parent Nautilus window closes."""
        logger.info("Nautilus window destroyed. Cleaning up shell process...")
        self._terminate_shell_process()
        if self.extension_ref and self.window in self.extension_ref.managers:
            del self.extension_ref.managers[self.window]

    def _terminate_shell_process(self):
        """Terminates the shell process via SIGHUP/SIGTERM."""
        if self.pid and self.is_running:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.debug(f"Error terminating shell PID {self.pid}: {e}")
        self.is_running = False
        self.pid = None

    def _on_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """GTK4 key-pressed handler for F12."""
        if keyval == Gdk.KEY_F12:
            self.toggle()
            return True  # Stop event propagation
        return False

    def _on_key_press_gtk3(self, widget, event) -> bool:
        """GTK3 key-press-event fallback."""
        if event.keyval == Gdk.KEY_F12:
            self.toggle()
            return True
        return False

    def create_and_spawn_terminal(self):
        """
        Matrix Case 1 & 4: Instantiates Vte.Terminal and spawns a fresh shell asynchronously.
        """
        if Vte is None:
            logger.error("Vte is not available. Shell cannot be instantiated.")
            return

        self._cleanup_vte()

        self.vte = Vte.Terminal.new() if hasattr(Vte.Terminal, "new") else Vte.Terminal()
        self.vte.set_scroll_on_output(False)
        self.vte.set_scroll_on_keystroke(True)
        self.vte.set_mouse_autohide(True)
        self.vte.set_audible_bell(False)
        self.vte.set_word_char_exceptions("-#%&+,./:=?@_~")

        # Set standard Monospace font
        try:
            font_desc = Pango.FontDescription.from_string("Monospace 10")
            self.vte.set_font(font_desc)
        except Exception as exc:
            logger.debug(f"Failed to set font: {exc}")

        # Connect exit signal (Ctrl+D / exit)
        self.vte.connect("child-exited", self._on_child_exited)

        # Support Ctrl+Shift+C (Copy) and Ctrl+Shift+V (Paste)
        if IS_GTK4:
            term_key_ctrl = Gtk.EventControllerKey.new()
            term_key_ctrl.connect("key-pressed", self._on_terminal_key_pressed)
            self.vte.add_controller(term_key_ctrl)
            self.scrolled_window.set_child(self.vte)
        else:
            self.scrolled_window.add(self.vte)
            self.vte.show()

        # Initial working directory
        spawn_dir = self.current_path if (self.current_path and os.path.isdir(self.current_path)) else os.path.expanduser("~")
        shell_binary = os.environ.get("SHELL", "/bin/bash")

        # Async spawn
        self._spawn_shell_async(spawn_dir, [shell_binary])

    def _on_terminal_key_pressed(self, controller, keyval, keycode, state) -> bool:
        """Handles terminal copy/paste accelerators in GTK4."""
        # Check Ctrl+Shift modifier
        ctrl_shift = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        if (state & ctrl_shift) == ctrl_shift:
            if keyval in (Gdk.KEY_C, Gdk.KEY_c):
                self.vte.copy_clipboard_format(Vte.Format.TEXT)
                return True
            elif keyval in (Gdk.KEY_V, Gdk.KEY_v):
                self.vte.paste_clipboard()
                return True
        return False

    def _spawn_shell_async(self, working_dir: str, argv: list):
        """Asynchronously spawns shell child process via VTE without blocking UI."""
        logger.info(f"Asynchronously launching shell in '{working_dir}'...")
        try:
            self.vte.spawn_async(
                Vte.PtyFlags.DEFAULT,
                working_dir,
                argv,
                None,
                GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.SEARCH_PATH,
                None,
                None,
                -1,
                None,
                self._on_spawn_completed,
                None
            )
        except TypeError:
            try:
                self.vte.spawn_async(
                    Vte.PtyFlags.DEFAULT,
                    working_dir,
                    argv,
                    None,
                    GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.SEARCH_PATH,
                    None,
                    -1,
                    None,
                    self._on_spawn_completed,
                    None
                )
            except Exception as e:
                logger.error(f"VTE spawn_async execution error: {e}")
        except Exception as e:
            logger.error(f"VTE spawn_async execution error: {e}")

    def _on_spawn_completed(self, terminal, pid, error, user_data=None):
        """Async callback triggered once the shell process has spawned."""
        if error is not None:
            logger.error(f"Failed to spawn shell: {error}")
            self.is_running = False
            self.pid = None
            return

        self.pid = pid
        self.is_running = True
        self.last_synced_path = self.current_path
        logger.info(f"Shell running (PID: {pid}).")

    def _on_child_exited(self, terminal, status):
        """
        Matrix Case 3: Ctrl+D / Exit
        Triggered when shell terminates. Resets state and hides container.
        """
        logger.info(f"Child shell process exited (status {status}).")
        self.is_running = False
        self.pid = None
        self.hide()
        self._cleanup_vte()

    def _cleanup_vte(self):
        """Detaches dead VTE widget."""
        if self.vte is not None:
            if IS_GTK4:
                if self.scrolled_window.get_child() == self.vte:
                    self.scrolled_window.set_child(None)
            else:
                if self.vte.get_parent() == self.scrolled_window:
                    self.scrolled_window.remove(self.vte)
            self.vte = None

    def toggle(self):
        """
        Toggles terminal according to the execution matrix.
        """
        if not self.is_running or self.vte is None:
            # First Run (Matrix 1) or After Exit (Matrix 4)
            self.create_and_spawn_terminal()
            self.show()
        else:
            # Toggle (Matrix 2)
            if self.is_visible:
                self.hide()
            else:
                self.show()

    def show(self):
        """Shows container, performs directory synchronization, and focuses terminal."""
        if self.container_box is None:
            return

        if IS_GTK4:
            self.container_box.set_visible(True)
        else:
            self.container_box.show_all()

        self.is_visible = True
        self.sync_directory()

        if self.vte is not None:
            self.vte.grab_focus()

    def hide(self):
        """Hides container; background shell process continues executing."""
        if self.container_box is None:
            return

        if IS_GTK4:
            self.container_box.set_visible(False)
        else:
            self.container_box.hide()

        self.is_visible = False

    def update_location(self, uri: str):
        """Updates active path on folder navigation."""
        self.current_uri = uri
        self.current_path = uri_to_path(uri)
        if self.is_visible and self.is_running:
            self.sync_directory()

    def sync_directory(self):
        """Synchronizes terminal's working directory with Nautilus active folder."""
        if not self.is_running or self.vte is None:
            return

        if not self.current_path or not os.path.isdir(self.current_path):
            return

        if self.current_path == self.last_synced_path:
            return

        logger.info(f"Directory sync -> cd {self.current_path}")
        cd_cmd = f"cd {shlex.quote(self.current_path)}\n".encode("utf-8")
        
        try:
            self.vte.feed_child(cd_cmd)
        except TypeError:
            self.vte.feed_child(cd_cmd, len(cd_cmd))
            
        self.last_synced_path = self.current_path

    def get_container(self) -> Gtk.Widget:
        """
        Returns the container widget.
        Ensures clean unparenting before Nautilus embeds it in a new location slot.
        """
        if self.container_box is not None:
            if IS_GTK4:
                parent = self.container_box.get_parent()
                if parent is not None:
                    self.container_box.unparent()
            else:
                parent = self.container_box.get_parent()
                if parent is not None:
                    parent.remove(self.container_box)
        return self.container_box


class NautilusF12TerminalExtension(GObject.GObject, Nautilus.LocationWidgetProvider if Nautilus else object):
    """
    Nautilus Python extension entrypoint implementing LocationWidgetProvider.
    """

    def __init__(self):
        super().__init__()
        self.managers = {}
        logger.info("Nautilus F12 Terminal Extension loaded.")

    def get_widget(self, uri: str, window: Gtk.Window) -> Gtk.Widget:
        """
        Called by Nautilus for each view/slot. Returns the per-window embedded widget.
        """
        if window not in self.managers:
            manager = WindowTerminalManager(window, extension_ref=self)
            self.managers[window] = manager
        else:
            manager = self.managers[window]

        manager.update_location(uri)
        return manager.get_container()
