"""
Bottom-Docked Paned Layout Strategy
"""

import logging
from .base import BaseLayoutStrategy
from ..gi_stack import IS_GTK4, Gtk, get_widget_children
from ..config import DEFAULT_TERMINAL_HEIGHT, EXPAND_VIEW_WIDGET_NAMES

logger = logging.getLogger("nautilus-f12")


class BottomPanedLayoutStrategy(BaseLayoutStrategy):
    """
    Docks the terminal at the BOTTOM of the NautilusWindowSlot using a vertical Gtk.Paned.
    Top pane = Nautilus file browser view.
    Bottom pane = Resizable embedded terminal console.
    """

    def __init__(self, min_height: int = DEFAULT_TERMINAL_HEIGHT):
        self.min_height = min_height
        self.paned = None
        self.top_vbox = None
        self.bottom_box = None
        self.scrolled_window = None
        self.separator = None

    def mount(self, slot_widget: Gtk.Widget, terminal_widget: Gtk.Widget):
        self.paned = Gtk.Paned(orientation=Gtk.Orientation.VERTICAL)
        self.top_vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.bottom_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_min_content_height(self.min_height)
        self.scrolled_window.set_size_request(-1, self.min_height)

        if terminal_widget:
            self.set_child_widget(terminal_widget)

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

            self.paned.pack1(self.top_vbox, resize=True, shrink=False)
            self.paned.pack2(self.bottom_box, resize=False, shrink=False)

        # Relocate existing view children from slot into top_vbox
        children = get_widget_children(slot_widget)
        for child in children:
            if child != self.paned:
                slot_widget.remove(child)
                if IS_GTK4:
                    self.top_vbox.append(child)
                else:
                    expand = child.get_name() in EXPAND_VIEW_WIDGET_NAMES or True
                    self.top_vbox.pack_start(child, expand, expand, 0)

        # Place paned into slot
        if IS_GTK4:
            slot_widget.append(self.paned)
        else:
            slot_widget.pack_start(self.paned, True, True, 0)
            self.paned.show()
            self.top_vbox.show_all()

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
        """Packs any newly navigated folder view into top_vbox."""
        if not slot_widget or not self.top_vbox:
            return
        children = get_widget_children(slot_widget)
        for child in children:
            if child != self.paned:
                slot_widget.remove(child)
                if IS_GTK4:
                    self.top_vbox.append(child)
                else:
                    self.top_vbox.pack_start(child, True, True, 0)
                    child.show_all()

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
