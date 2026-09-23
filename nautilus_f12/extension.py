"""
Nautilus Extension Entrypoint & Anchor
"""

import os
import logging
from .gi_stack import GObject, Gtk, Gdk, Gio, Nautilus
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


class NautilusF12Extension(GObject.GObject, Nautilus.LocationWidgetProvider):
    """
    Main Nautilus LocationWidgetProvider Extension.
    """

    def __init__(self):
        super().__init__()
        self.window_sessions = {}
        logger.info("Nautilus F12 Extension loaded.")

    def get_or_create_window_session(self, window: Gtk.Window, path: str) -> TerminalSession:
        if window not in self.window_sessions:
            # Install window-level key controller
            WindowKeyController(
                window,
                Gdk.KEY_F12,
                lambda: self.toggle_window_session(window),
            )
            session = TerminalSession(
                window=window,
                initial_path=path,
                layout_strategy=BottomPanedLayoutStrategy(),
                on_destroy_callback=self._on_window_destroyed,
            )
            self.window_sessions[window] = session
            logger.info("Created non-destructive bottom-docked session for NautilusWindow.")
        return self.window_sessions[window]

    def toggle_window_session(self, window: Gtk.Window):
        if window in self.window_sessions:
            self.window_sessions[window].toggle()

    def _on_window_destroyed(self, window: Gtk.Window):
        if window in self.window_sessions:
            del self.window_sessions[window]
            logger.info("Cleaned up session for closed NautilusWindow.")

    def get_widget(self, uri_or_file, window: Gtk.Window) -> Gtk.Widget:
        """
        Invoked by Nautilus on navigation.
        Updates path and returns None so Nautilus allocates ZERO space in the top location bar.
        """
        path = uri_to_path(uri_or_file)
        session = self.get_or_create_window_session(window, path)
        session.update_location(path)
        return None
