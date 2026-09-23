#!/usr/bin/env python3
"""
Nautilus F12 Terminal Extension Loader
"""

import sys
import os

# Ensure package directory is in sys.path for python3-nautilus loader
EXT_DIR = os.path.dirname(os.path.abspath(__file__))
if EXT_DIR not in sys.path:
    sys.path.insert(0, EXT_DIR)

try:
    from nautilus_f12.extension import NautilusF12Extension
except ImportError:
    # Fallback to absolute workspace path if deployed as a symlink
    WS_PATH = "/home/resgef/works/nautilus-f12"
    if WS_PATH not in sys.path:
        sys.path.insert(0, WS_PATH)
    from nautilus_f12.extension import NautilusF12Extension

__all__ = ["NautilusF12Extension"]
