"""
Nautilus F12 Configuration & Constants
"""

DEFAULT_TERMINAL_HEIGHT = 240
DEFAULT_FONT = "Monospace 10"
DEFAULT_TOGGLE_KEY = "F12"
WORD_CHAR_EXCEPTIONS = "-#%&+,./:=?@_~"

EXPAND_VIEW_WIDGET_NAMES = [
    "GtkOverlay",
    "NautilusCanvasView",
    "NautilusViewIconController",
    "NautilusListView",
    "NautilusFilesView",
    "GtkScrolledWindow",
    "AdwToastOverlay",
]

# Explicit slot container identifiers (excludes generic GtkBox so traversal finds the actual slot)
SLOT_CONTAINER_NAMES = [
    "NautilusWindowSlot",
    "NautilusWindowSlotView",
]
