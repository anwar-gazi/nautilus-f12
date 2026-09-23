"""
GObject Introspection Version Negotiator & Compatibility Layer
"""

import logging
import gi

logger = logging.getLogger("nautilus-f12")

IS_GTK4 = False
try:
    gi.require_version("Nautilus", "4.0")
    gi.require_version("Gtk", "4.0")
    try:
        gi.require_version("Vte", "3.91")
    except ValueError:
        gi.require_version("Vte", "2.91")
    IS_GTK4 = True
    logger.info("Loaded Nautilus 4.0 / GTK4 stack.")
except ValueError:
    gi.require_version("Nautilus", "3.0")
    gi.require_version("Gtk", "3.0")
    gi.require_version("Vte", "2.91")
    IS_GTK4 = False
    logger.info("Loaded Nautilus 3.0 / GTK3 stack.")

from gi.repository import GObject, Gtk, Gdk, GLib, Gio, Pango, Vte, Nautilus


def get_widget_children(widget: Gtk.Widget) -> list:
    """Safely retrieves children of a widget across both GTK3 and GTK4."""
    children = []
    if not widget:
        return children

    if hasattr(widget, "get_first_child"):
        child = widget.get_first_child()
        while child:
            children.append(child)
            child = child.get_next_sibling()
    elif hasattr(widget, "get_children"):
        children = widget.get_children()
    return children


__all__ = [
    "IS_GTK4",
    "GObject",
    "Gtk",
    "Gdk",
    "GLib",
    "Gio",
    "Pango",
    "Vte",
    "Nautilus",
    "get_widget_children",
]
