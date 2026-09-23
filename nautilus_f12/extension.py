"""
Nautilus Extension Entrypoint & Anchor
"""

import os
import logging
from .gi_stack import GObject, Gtk, Gdk, Gio, GLib, Nautilus
from .config import SLOT_CONTAINER_NAMES
from .session import TerminalSession
from .layouts import BottomPanedLayoutStrategy
from .input import WindowKeyController

logger = logging.getLogger("nautilus-f12")


def uri_to_path(file_or_uri) -> str:
    """Converts FileInfo or URI string to local path."""
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
            logger.debug(f"URI conversion error: {exc}")
    return os.path.expanduser("~")


def find_slot_container(widget: Gtk.Widget) -> Gtk.Widget:
    """Traverses widget tree upwards to locate NautilusWindowSlot."""
    curr = widget
    while curr:
        name = curr.get_name() if hasattr(curr, "get_name") else ""
        type_name = type(curr).__name__
        if name in SLOT_CONTAINER_NAMES or type_name in SLOT_CONTAINER_NAMES:
            return curr
        curr = curr.get_parent() if hasattr(curr, "get_parent") else None
    return None


class TerminalAnchor(Gtk.EventBox if hasattr(Gtk, "EventBox") else Gtk.Box):
    """
    Zero-size anchor widget inserted into the location bar by Nautilus.
    Discovers the parent slot and binds the TerminalSession.
    """

    def __init__(self, uri_or_file, window: Gtk.Window, extension):
        super().__init__()
        self.uri_or_file = uri_or_file
        self.window = window
        self.extension = extension
        self.path = uri_to_path(uri_or_file)

        if hasattr(self, "connect_after"):
            self.connect_after("parent-set", self._on_parent_set)
        else:
            self.connect("notify::parent", self._on_parent_set)

    def _on_parent_set(self, widget, old_parent=None):
        if old_parent and not self.get_parent():
            return
        GLib.idle_add(self.extension.bind_slot_session, self)


class NautilusF12Extension(GObject.GObject, Nautilus.LocationWidgetProvider):
    """
    Main Nautilus LocationWidgetProvider Extension.
    """

    def __init__(self):
        super().__init__()
        self.sessions = {}
        logger.info("Nautilus F12 Extension loaded.")

    def bind_slot_session(self, anchor: TerminalAnchor):
        slot = find_slot_container(anchor)
        if not slot:
            return

        # Ensure window-level F12 key listener is installed
        if not hasattr(anchor.window, "_f12_key_controller"):
            anchor.window._f12_key_controller = WindowKeyController(
                anchor.window,
                Gdk.KEY_F12,
                lambda: self.toggle_active_session_for_window(anchor.window),
            )

        if slot in self.sessions:
            session = self.sessions[slot]
            session.update_location(anchor.path)
        else:
            session = TerminalSession(
                slot_widget=slot,
                window=anchor.window,
                initial_path=anchor.path,
                layout_strategy=BottomPanedLayoutStrategy(),
                on_destroy_callback=self._on_slot_destroyed,
            )
            self.sessions[slot] = session
            logger.info("Bound TerminalSession to active NautilusWindowSlot.")

    def toggle_active_session_for_window(self, window: Gtk.Window):
        """Finds the currently visible/mapped tab session in the window and toggles it."""
        window_sessions = [s for s in self.sessions.values() if s.window == window]
        if not window_sessions:
            return

        # Locate the session whose slot is currently visible/mapped (active tab)
        active_session = None
        for s in window_sessions:
            if s.slot.get_mapped():
                active_session = s
                break

        if not active_session:
            active_session = window_sessions[-1]

        active_session.toggle()

    def _on_slot_destroyed(self, slot_widget: Gtk.Widget):
        """Removes session reference when tab closes."""
        if slot_widget in self.sessions:
            del self.sessions[slot_widget]
            logger.info("Cleaned up session for closed Nautilus slot.")

    def get_widget(self, uri_or_file, window: Gtk.Window) -> Gtk.Widget:
        """Called by Nautilus when loading a directory view."""
        return TerminalAnchor(uri_or_file, window, self)
