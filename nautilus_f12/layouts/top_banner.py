"""
Top-Banner Layout Strategy
"""

from .base import BaseLayoutStrategy
from ..gi_stack import IS_GTK4, Gtk
from ..config import DEFAULT_TERMINAL_HEIGHT


class TopBannerLayoutStrategy(BaseLayoutStrategy):
    """
    Places the terminal as a top banner directly above the folder view.
    """

    def __init__(self, min_height: int = DEFAULT_TERMINAL_HEIGHT):
        self.min_height = min_height
        self.container_box = None
        self.scrolled_window = None
        self.separator = None

    def mount(self, slot_widget: Gtk.Widget, terminal_widget: Gtk.Widget):
        self.container_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self.scrolled_window = Gtk.ScrolledWindow()
        self.scrolled_window.set_min_content_height(self.min_height)
        self.scrolled_window.set_size_request(-1, self.min_height)
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)

        if terminal_widget:
            self.set_child_widget(terminal_widget)

        if IS_GTK4:
            self.container_box.append(self.scrolled_window)
            self.container_box.append(self.separator)
            self.container_box.set_visible(False)
            slot_widget.prepend(self.container_box)
        else:
            self.container_box.pack_start(self.scrolled_window, True, True, 0)
            self.container_box.pack_start(self.separator, False, False, 0)
            self.container_box.set_no_show_all(True)
            self.container_box.hide()
            slot_widget.pack_start(self.container_box, False, False, 0)

    def set_child_widget(self, terminal_widget: Gtk.Widget):
        if not self.scrolled_window:
            return
        if IS_GTK4:
            self.scrolled_window.set_child(terminal_widget)
        else:
            old_child = self.scrolled_window.get_child()
            if old_child:
                self.scrolled_window.remove(old_child)
            if terminal_widget:
                self.scrolled_window.add(terminal_widget)
                terminal_widget.show()

    def repack(self, slot_widget: Gtk.Widget):
        pass

    def show(self):
        if not self.container_box:
            return
        if IS_GTK4:
            self.container_box.set_visible(True)
        else:
            self.container_box.set_no_show_all(False)
            self.container_box.show_all()

    def hide(self):
        if not self.container_box:
            return
        if IS_GTK4:
            self.container_box.set_visible(False)
        else:
            self.container_box.hide()
            self.container_box.set_no_show_all(True)
