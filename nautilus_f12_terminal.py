#!/usr/bin/env python3
"""
Nautilus F12 Embedded Terminal Extension (Bottom-Docked)
Target Environment: Ubuntu 22.04+ | GNOME 42+ (GTK4 / GTK3) | Wayland / X11 | python3-nautilus

Architecture & Key Features:
- Bottom-Docked UI: Automatically wraps the active Nautilus slot in a Gtk.Paned with the
  file browser on top and the resizable embedded VTE terminal at the BOTTOM.
- Dual-Stack Version Negotiation: Dynamically supports Nautilus 4.0 + GTK4 and Nautilus 3.0 + GTK3
  without PyGObject namespace collision.
- Wayland CAPTURE Key Controller: Intercepts F12 keypresses on the NautilusWindow before child views consume them.
- Non-Blocking Async Spawn: Uses Vte.Terminal.spawn_async to prevent UI lockup during shell start.
- Process State & Synchronization: Auto cd on directory navigation/reveal and clean reset on Ctrl+D / exit.
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

_EXPAND_VIEW_WIDGETS = [
    "GtkOverlay",
    "NautilusCanvasView",
    "NautilusViewIconController",
    "NautilusListView",
    "NautilusFilesView",
    "GtkScrolledWindow",
    "AdwToastOverlay",
]


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


def find_parent_by_name(widget, target_names):
    """Walks widget tree upwards looking for a container matching target class/widget names."""
    curr = widget
    while curr:
        name = curr.get_name() if hasattr(curr, "get_name") else ""
        type_name = type(curr).__name__
        if name in target_names or type_name in target_names:
            return curr
        curr = curr.get_parent() if hasattr(curr, "get_parent") else None
    return None


class SlotTerminalManager:
    """
    Manages an embedded bottom-docked VTE terminal for a NautilusWindowSlot.
    """

    def __init__(self, slot_widget, window: Gtk.Window, initial_path: str):
        self.slot = slot_widget
        self.window = window
        self.current_path = initial_path if initial_path else os.path.expanduser("~")
        self.last_synced_path = None
        
        # State
        self.vte = None
        self.pid = None
        self.is_running = False
        self.is_visible = False
        
        # UI Widgets
        self.paned = None
        self.top_vbox = None
        self.bottom_box = None
        self.scrolled_window = None
        self.separator = None
        
        self._inject_bottom_paned()
        self._install_key_controller()
        self._connect_window_signals()

    def _inject_bottom_paned(self):
        """Wraps slot children in a Gtk.Paned with the terminal placed at the BOTTOM."""
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.top_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_min_content_height(240)
        self.scrolled_window.set_size_request(-1, 240)
        
        # Assemble bottom panel
        if IS_GTK4:
            self.bottom_box.append(self.separator)
            self.bottom_box.append(self.scrolled_window)
            self.bottom_box.set_visible(False)
            
            self.paned.set_start_child(self.top_vbox)
            self.paned.set_end_child(self.bottom_box)
            self.paned.set_resize_start_child(True)
            self.paned.set_shrink_start_child(False)
            self.paned.set_resize_end_child(False)
            self.paned.set_shrink_end_child(False)
        else:
            self.bottom_box.pack_start(self.separator, False, False, 0)
            self.bottom_box.pack_start(self.scrolled_window, True, True, 0)
            self.bottom_box.set_no_show_all(True)
            self.bottom_box.hide()
            
            # pack1 = Top (File view), pack2 = Bottom (Terminal)
            self.paned.pack1(self.top_vbox, resize=True, shrink=False)
            self.paned.pack2(self.bottom_box, resize=False, shrink=False)

        # Move existing file views from slot into top_vbox
        children = self.slot.get_children() if hasattr(self.slot, "get_children") else []
        for child in children:
            if child != self.paned:
                self.slot.remove(child)
                if IS_GTK4:
                    self.top_vbox.append(child)
                else:
                    expand = child.get_name() in _EXPAND_VIEW_WIDGETS or True
                    self.top_vbox.pack_start(child, expand, expand, 0)

        # Place paned into slot
        if IS_GTK4:
            self.slot.append(self.paned)
        else:
            self.slot.pack_start(self.paned, True, True, 0)
            self.paned.show()
            self.top_vbox.show_all()

    def repack_slot_views(self):
        """Moves any newly created file view widgets inside top_vbox so they stay above the terminal."""
        if not self.slot or not self.top_vbox:
            return
            
        children = self.slot.get_children() if hasattr(self.slot, "get_children") else []
        for child in children:
            if child != self.paned:
                self.slot.remove(child)
                if IS_GTK4:
                    self.top_vbox.append(child)
                else:
                    self.top_vbox.pack_start(child, True, True, 0)
                    child.show_all()

    def _install_key_controller(self):
        """Binds F12 key listener to the top-level Nautilus window using CAPTURE phase."""
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
                    logger.debug(f"EventControllerKey fallback: {e}")
            self.window.connect("key-press-event", self._on_key_press_gtk3)
            
        self.window._f12_terminal_controller_installed = True
        logger.info("Attached F12 key listener to Nautilus window.")

    def _connect_window_signals(self):
        """Connects window destruction to clean up child shell processes."""
        self.window.connect("destroy", self._on_window_destroy)

    def _on_window_destroy(self, widget):
        """Kills active shell process when the parent Nautilus window closes."""
        logger.info("Nautilus window destroyed. Cleaning up shell process...")
        self._terminate_shell_process()

    def _terminate_shell_process(self):
        """Terminates shell process via SIGHUP/SIGTERM."""
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
        """Instantiates Vte.Terminal at bottom and spawns shell asynchronously."""
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

        # Shortcuts (Ctrl+Shift+C / Ctrl+Shift+V)
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
        logger.info(f"Asynchronously launching bottom terminal in '{working_dir}'...")
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
        logger.info(f"Bottom terminal shell running (PID: {pid}).")

    def _on_child_exited(self, terminal, status):
        """Handles shell process exit."""
        logger.info(f"Bottom terminal shell process exited (status {status}).")
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
        """Toggles terminal visibility."""
        logger.info("Toggling bottom terminal...")
        if not self.is_running or self.vte is None:
            self.create_and_spawn_terminal()
            self.show()
        else:
            if self.is_visible:
                self.hide()
            else:
                self.show()

    def show(self):
        """Reveals bottom terminal, syncs cwd, and transfers keyboard focus."""
        if self.bottom_box is None:
            return

        if IS_GTK4:
            self.bottom_box.set_visible(True)
        else:
            self.bottom_box.set_no_show_all(False)
            self.bottom_box.show_all()

        self.is_visible = True
        self.sync_directory()

        if self.vte is not None:
            self.vte.grab_focus()

    def hide(self):
        """Hides bottom terminal; background shell remains running."""
        if self.bottom_box is None:
            return

        if IS_GTK4:
            self.bottom_box.set_visible(False)
        else:
            self.bottom_box.hide()
            self.bottom_box.set_no_show_all(True)

        self.is_visible = False

    def update_location(self, file_or_uri):
        """Updates active path on folder navigation and moves new view widgets into top vbox."""
        self.current_path = uri_to_path(file_or_uri)
        self.repack_slot_views()
        if self.is_visible and self.is_running:
            self.sync_directory()

    def sync_directory(self):
        """Sends 'cd <current_path>' to active shell if directory changed."""
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


class TerminalAnchor(Gtk.EventBox if hasattr(Gtk, "EventBox") else Gtk.Box):
    """
    Lightweight anchor widget inserted by LocationWidgetProvider.
    Locates the active NautilusWindowSlot and injects the bottom-docked terminal.
    """

    def __init__(self, uri, window, extension):
        super().__init__()
        self.uri = uri
        self.nautilus_window = window
        self.extension = extension
        self.path = uri_to_path(uri)

        # Trigger on insertion
        if hasattr(self, "connect_after"):
            self.connect_after("parent-set", self._on_parent_set)
        else:
            self.connect("notify::parent", self._on_parent_set)

    def _on_parent_set(self, widget, old_parent=None):
        if old_parent and not self.get_parent():
            return
        GLib.idle_add(self.extension.create_or_update_slot_terminal, self)


class NautilusF12TerminalExtension(GObject.GObject, Nautilus.LocationWidgetProvider):
    """
    Nautilus Python extension entrypoint implementing LocationWidgetProvider.
    """

    def __init__(self):
        super().__init__()
        self.slot_managers = {}
        logger.info("Nautilus F12 Terminal Extension loaded (Bottom-Docked).")

    def create_or_update_slot_terminal(self, anchor: TerminalAnchor):
        """Locates NautilusWindowSlot from anchor and mounts or updates the bottom terminal."""
        slot = find_parent_by_name(anchor, ["NautilusWindowSlot", "NautilusWindowSlotView", "GtkBox"])
        if not slot:
            return

        if slot in self.slot_managers:
            manager = self.slot_managers[slot]
            manager.update_location(anchor.uri)
        else:
            manager = SlotTerminalManager(slot, anchor.nautilus_window, anchor.path)
            self.slot_managers[slot] = manager
            logger.info("Injected bottom terminal panel into active NautilusWindowSlot.")

    def get_widget(self, uri_or_file, window: Gtk.Window) -> Gtk.Widget:
        """Returns the lightweight anchor widget to track active view slot."""
        return TerminalAnchor(uri_or_file, window, self)
