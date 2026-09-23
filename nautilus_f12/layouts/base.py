"""
Abstract Base Layout Strategy
"""

from abc import ABC, abstractmethod
from ..gi_stack import Gtk


class BaseLayoutStrategy(ABC):
    """
    Interface for terminal placement and slot widget tree layout strategies.
    """

    @abstractmethod
    def mount(self, slot_widget: Gtk.Widget, terminal_widget: Gtk.Widget):
        """Mounts terminal widget into slot hierarchy."""
        pass

    @abstractmethod
    def show(self):
        """Reveals the terminal container."""
        pass

    @abstractmethod
    def hide(self):
        """Hides the terminal container."""
        pass

    @abstractmethod
    def repack(self, slot_widget: Gtk.Widget):
        """Repacks new slot children on directory navigation."""
        pass

    @abstractmethod
    def set_child_widget(self, terminal_widget: Gtk.Widget):
        """Updates or replaces the inner terminal widget."""
        pass
