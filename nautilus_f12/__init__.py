"""
Nautilus F12 Embedded Terminal Extension Package
"""

from .extension import NautilusF12Extension
from .session import TerminalSession
from .layouts import BottomPanedLayoutStrategy, TopBannerLayoutStrategy

__all__ = [
    "NautilusF12Extension",
    "TerminalSession",
    "BottomPanedLayoutStrategy",
    "TopBannerLayoutStrategy",
]
