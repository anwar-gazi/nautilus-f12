"""
VTE Terminal Widget Construction & Shortcuts
"""

import logging
from ..gi_stack import IS_GTK4, Gtk, Gdk, Pango, Vte
from ..config import DEFAULT_FONT, WORD_CHAR_EXCEPTIONS

logger = logging.getLogger("nautilus-f12")


class VteTerminalWidget:
    """
    Constructs and configures a styled Vte.Terminal widget with clipboard accelerators.
    """

    def __init__(self, font_name: str = DEFAULT_FONT):
        self.vte = Vte.Terminal.new() if hasattr(Vte.Terminal, "new") else Vte.Terminal()
        self._configure_properties(font_name)
        self._install_clipboard_shortcuts()

    def _configure_properties(self, font_name: str):
        self.vte.set_scroll_on_output(False)
        self.vte.set_scroll_on_keystroke(True)
        self.vte.set_mouse_autohide(True)
        self.vte.set_audible_bell(False)
        self.vte.set_word_char_exceptions(WORD_CHAR_EXCEPTIONS)

        try:
            font_desc = Pango.FontDescription.from_string(font_name)
            self.vte.set_font(font_desc)
        except Exception as exc:
            logger.debug(f"Failed to set font: {exc}")

    def _install_clipboard_shortcuts(self):
        """Binds Ctrl+Shift+C / Ctrl+Shift+V for copy and paste."""
        if IS_GTK4:
            controller = Gtk.EventControllerKey.new()
            controller.connect("key-pressed", self._on_key_pressed_gtk4)
            self.vte.add_controller(controller)
        else:
            self.vte.connect("key-press-event", self._on_key_press_gtk3)

    def _on_key_pressed_gtk4(self, controller, keyval, keycode, state) -> bool:
        ctrl_shift = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        if (state & ctrl_shift) == ctrl_shift:
            if keyval in (Gdk.KEY_C, Gdk.KEY_c):
                self.vte.copy_clipboard_format(Vte.Format.TEXT) if hasattr(self.vte, "copy_clipboard_format") else self.vte.copy_clipboard()
                return True
            elif keyval in (Gdk.KEY_V, Gdk.KEY_v):
                self.vte.paste_clipboard()
                return True
        return False

    def _on_key_press_gtk3(self, widget, event) -> bool:
        ctrl_shift = (Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        if (event.state & ctrl_shift) == ctrl_shift:
            if event.keyval in (Gdk.KEY_C, Gdk.KEY_c):
                self.vte.copy_clipboard_format(Vte.Format.TEXT) if hasattr(self.vte, "copy_clipboard_format") else self.vte.copy_clipboard()
                return True
            elif event.keyval in (Gdk.KEY_V, Gdk.KEY_v):
                self.vte.paste_clipboard()
                return True
        return False

    def grab_focus(self):
        self.vte.grab_focus()

    def get_widget(self) -> Vte.Terminal:
        return self.vte
