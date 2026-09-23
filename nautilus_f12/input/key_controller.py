"""
Wayland-Safe Window Key Controller
"""

import logging
from typing import Callable
from ..gi_stack import IS_GTK4, Gtk, Gdk

logger = logging.getLogger("nautilus-f12")


class WindowKeyController:
    """
    Attaches a key listener to a top-level Gtk.Window using CAPTURE phase (GTK4) or key-press-event (GTK3).
    Ensures exactly ONE callback invocation per keypress.
    """

    def __init__(self, window: Gtk.Window, target_keyval: int, callback: Callable[[], None]):
        self.window = window
        self.target_keyval = target_keyval
        self.callback = callback
        self._install()

    def _install(self):
        flag_name = f"_key_controller_installed_{self.target_keyval}"
        if hasattr(self.window, flag_name):
            return

        if IS_GTK4:
            controller = Gtk.EventControllerKey.new()
            controller.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
            controller.connect("key-pressed", self._on_key_pressed_gtk4)
            self.window.add_controller(controller)
        else:
            # Under GTK3, connect only key-press-event to prevent double-firing in the same event cycle
            self.window.connect("key-press-event", self._on_key_press_gtk3)

        setattr(self.window, flag_name, True)
        logger.info(f"Attached single key controller for keyval {self.target_keyval} to Nautilus window.")

    def _on_key_pressed_gtk4(self, controller, keyval, keycode, state) -> bool:
        if keyval == self.target_keyval:
            self.callback()
            return True
        return False

    def _on_key_press_gtk3(self, widget, event) -> bool:
        if event.keyval == self.target_keyval:
            self.callback()
            return True
        return False
