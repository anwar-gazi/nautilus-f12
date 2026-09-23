#!/usr/bin/env python3
"""
Nautilus F12 Embedded Terminal Extension
Target Environment: Ubuntu 22.04+ | GNOME 42+ (GTK4 / GTK3) | Wayland / X11 | python3-nautilus

Bulletproof Guardrails & Architecture:
- Dual-Stack Version Negotiation: Dynamically binds to Nautilus 4.0 + GTK4 or Nautilus 3.0 + GTK3
  without causing PyGObject namespace conflicts.
- Wayland CAPTURE Key Controller: Intercepts F12 during the capture phase on the top-level NautilusWindow.
- Asynchronous VTE Process Spawning: Non-blocking Vte.Terminal.spawn_async prevents UI freezing.
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

# Dynamically negotiate GI namespace versions to avoid Gtk 3.0 vs 4.0 collisions
IS_GTK4 = False
try:
    gi.require_version("Nautilus", "4.0")
    gi.require_version("Gtk", "4.0")
    try:
        gi.require_version("Vte", "3.91")
    except ValueError:
        gi.require_version("Vte", "2.91")
    IS_GTK4 = True
    logger.info("Initializing with Nautilus 4.0 / GTK4 stack.")
except ValueError:
    gi.require_version("Nautilus", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("Vte", "2.91")
    IS_GTK4 = False
    logger.info("Initializing with Nautilus 3.0 / GTK3 stack.")

from gi.repository import GObject, Gtk, Gdk, GLib, Gio, Pango, Vte, Nautilus


def uri_to_path(file_or_uri) -> str:
    """Safely converts a Nautilus FileInfo or GVFS URI to a local filesystem path."""
    if not file_or_uri:
        return os.path.expanduser("~")
    
    uri = None
    if hasattr(file_or_uri, "get_uri"):
        uri = file_or_uri.get_uri()
    elif isinstance(file_or_uri, str):
        uri = file_or_uri
    else:
        uri = str(file_or_uri)

    if uri and uri.startswith("file://"):
        try:
            gfile = Gio.File.new_for_uri(uri)
            path = gfile.get_path()
            if path and os.path.isdir(path):
                return path
        except Exception as exc:
            logger.debug(f"Failed to convert URI {uri} to path: {exc}")
            
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
        """Constructs UI container tree."""
        self.container_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_min_content_height(240)
        self.scrolled_window.set_size_request(-1, 240)
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        if IS_GTK4:
            self.container_box.set_visible(False)
            self.scrolled_window.set_vexpand(False)
            self.scrolled_window.set_hexpand(True)
            self.container_box.append(self.scrolled_window)
            self.container_box.append(self.separator)
        else:
            self.container_box.set_no_show_all(True)
            self.container_box.hide()
            self.container_box.pack_start(self.scrolled_window, True, True, 0)
            self.container_box.pack_start(self.separator, False, False, 0)

    def _install_key_controller(self):
        """
        Binds F12 key listener to the top-level Nautilus window using CAPTURE phase.
        Ensures Wayland compliance and guarantees F12 triggers regardless of focused child.
        """
        if hasattr(self.window, "_f12_terminal_controller_installed"):
            return
        
        if IS_GTK4:
            controller = Gtk.EventControllerKey.new()
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            controller.connect("key-pressed", self._on_key_pressed_gtk4)
            self.window.add_controller(controller)
        else:
            if hasattr(Gtk, "EventControllerKey"):
                try:
                    controller = Gtk.EventControllerKey.new(self.window)
                    controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
                    controller.connect("key-pressed", self._on_key_pressed_gtk3_controller)
                    self._key_controller = controller
                except Exception as e:
                    logger.debug(f"EventControllerKey setup fallback: {e}")
            self.window.connect("key-press-event", self._on_key_press_gtk3)
            
        self.window._f12_terminal_controller_installed = True
        logger.info("Attached F12 key listener to Nautilus window.")

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

    def _on_key_pressed_gtk4(self, controller, keyval, keycode, state) -> bool:
        """GTK4 key-pressed handler for F12."""
        if keyval == Gdk.KEY_F12:
            self.toggle()
            return True
        return False

    def _on_key_pressed_gtk3_controller(self, controller, keyval, keycode, state) -> bool:
        """GTK3 EventControllerKey handler for F12."""
        if keyval == Gdk.KEY_F12:
            self.toggle()
            return True
        return False

    def _on_key_press_gtk3(self, widget, event) -> bool:
        """GTK3 key-press-event signal fallback for F12."""
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
            term_key_ctrl.connect("key-pressed", self._on_terminal_key_pressed_gtk4)
            self.vte.add_controller(term_key_ctrl)
            self.scrolled_window.set_child(self.vte)
        else:
            self.vte.connect("key-press-event", self._on_terminal_key_press_gtk3)
            self.scrolled_window.add(self.vte)
            self.vte.show()

        # Initial working directory
        spawn_dir = self.current_path if (self.current_path and os.path.isdir(self.current_path)) else os.path.expanduser("~")
        shell_binary = os.environ.get("SHELL", "/bin/bash")

        # Async spawn
        self._spawn_shell_async(spawn_dir, [shell_binary])

    def _on_terminal_key_pressed_gtk4(self, controller, keyval, keycode, state) -> bool:
        """Handles terminal copy/paste accelerators in GTK4."""
        ctrl_shift = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        if (state & ctrl_shift) == ctrl_shift:
            if keyval in (Gdk.KEY_C, Gdk.KEY_c):
                self.vte.copy_clipboard_format(Vte.Format.TEXT) if hasattr(self.vte, "copy_clipboard_format") else self.vte.copy_clipboard()
                return True
            elif keyval in (Gdk.KEY_V, Gdk.KEY_v):
                self.vte.paste_clipboard()
                return True
        return False

    def _on_terminal_key_press_gtk3(self, widget, event) -> bool:
        """Handles terminal copy/paste accelerators in GTK3."""
        ctrl_shift = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        if (event.state & ctrl_shift) == ctrl_shift:
            if event.keyval in (Gdk.KEY_C, Gdk.KEY_c):
                self.vte.copy_clipboard_format(Vte.Format.TEXT) if hasattr(self.vte, "copy_clipboard_format") else self.vte.copy_clipboard()
                return True
            elif event.keyval in (Gdk.KEY_V, Gdk.KEY_v):
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
        logger.info("Toggling Nautilus F12 Terminal...")
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
            self.container_box.set_no_show_all(False)
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
            self.container_box.set_no_show_all(True)

        self.is_visible = False

    def update_location(self, file_or_uri):
        """Updates active path on folder navigation."""
        self.current_uri = file_or_uri
        self.current_path = uri_to_path(file_or_uri)
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
            parent = self.container_box.get_parent()
            if parent is not None:
                if IS_GTK4:
                    self.container_box.unparent()
                else:
                    parent.remove(self.container_box)
        return self.container_box


class NautilusF12TerminalExtension(GObject.GObject, Nautilus.LocationWidgetProvider):
    """
    Nautilus Python extension entrypoint implementing LocationWidgetProvider.
    """

    def __init__(self):
        super().__init__()
        self.managers = {}
        logger.info("Nautilus F12 Terminal Extension loaded.")

    def get_widget(self, uri_or_file, window: Gtk.Window) -> Gtk.Widget:
        """
        Called by Nautilus for each view/slot. Returns the per-window embedded widget.
        """
        if window not in self.managers:
            manager = WindowTerminalManager(window, extension_ref=self)
            self.managers[window] = manager
        else:
            manager = self.managers[window]

        manager.update_location(uri_or_file)
        return manager.get_container()
