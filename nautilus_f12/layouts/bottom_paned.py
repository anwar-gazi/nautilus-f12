"""
Non-Destructive Bottom-Docked Layout Strategy
"""

import logging
from .base import BaseLayoutStrategy
from ..gi_stack import IS_GTK4, Gtk
from ..config import DEFAULT_TERMINAL_HEIGHT

logger = logging.getLogger("nautilus-f12")


class BottomPanedLayoutStrategy(BaseLayoutStrategy):
    """
    Non-destructively packs the terminal at the bottom of the active NautilusWindowSlot.
    Preserves all existing Nautilus view widgets to avoid white-space and geometry issues.
    """

    def __init__(self, min_height: int = DEFAULT_TERMINAL_HEIGHT):
        self.min_height = min_height
        self.bottom_box = None
        self.scrolled_window = None
        self.separator = None
        self.slot = None

    def mount(self, slot_widget: Gtk.Widget, terminal_widget: Gtk.Widget):
        self.slot = slot_widget
        self.bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_min_content_height(self.min_height)
        self.scrolled_window.set_size_request(-1, self.min_height)

        if terminal_widget:
            self.set_child_widget(terminal_widget)

        if IS_GTK4:
            self.bottom_box.append(self.separator)
            self.bottom_box.append(self.scrolled_window)
            self.bottom_box.set_visible(False)
            if hasattr(self.slot, "append"):
                self.slot.append(self.bottom_box)
            elif hasattr(self.slot, "pack_end"):
                self.slot.pack_end(self.bottom_box, False, False, 0)
        else:
            self.bottom_box.pack_start(self.separator, False, False, 0)
            self.bottom_box.pack_start(self.scrolled_window, True, True, 0)
            self.bottom_box.set_no_show_all(True)
            self.bottom_box.hide()
            if hasattr(self.slot, "pack_end"):
                self.slot.pack_end(self.bottom_box, False, False, 0)
            elif hasattr(self.slot, "add"):
                self.slot.add(self.bottom_box)

    def set_child_widget(self, terminal_widget: Gtk.Widget):
        if not self.scrolled_window:
            return
        if IS_GTK4:
            self.scrolled_window.set_child(terminal_widget)
        else:
            old_child = self.scrolled_window.get_child() if hasattr(self.scrolled_window, "get_child") else None
            if not old_child and hasattr(self.scrolled_window, "get_children"):
                children = self.scrolled_window.get_children()
                old_child = children[0] if children else None
            if old_child:
                self.scrolled_window.remove(old_child)
            if terminal_widget:
                self.scrolled_window.add(terminal_widget)
                terminal_widget.show()

    def repack(self, slot_widget: Gtk.Widget):
        pass

    def show(self):
        if not self.bottom_box:
            return
        if IS_GTK4:
            self.bottom_box.set_visible(True)
        else:
            self.bottom_box.set_no_show_all(False)
            self.bottom_box.show_all()

    def hide(self):
        if not self.bottom_box:
            return
        if IS_GTK4:
            self.bottom_box.set_visible(False)
        else:
            self.bottom_box.hide()
            self.bottom_box.set_no_show_all(True)
