# Nautilus F12 Embedded Terminal Extension

> **Production-grade, Wayland-compatible embedded VTE terminal extension for GNOME Files (Nautilus 42+ / GTK4 & GTK3).**

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![GNOME](https://img.shields.io/badge/GNOME-42%20%7C%2043%20%7C%2044%20%7C%2045%20%7C%2046-black?logo=gnome)](https://www.gnome.org/)
[![GTK4](https://img.shields.io/badge/GTK-4.0%20%26%203.0-blue)](https://www.gtk.org/)
[![Wayland](https://img.shields.io/badge/Display-Wayland%20%7C%20X11-orange)](https://wayland.freedesktop.org/)
[![License](https://img.shields.io/badge/License-Proprietary-red)](LICENSE)

---

## ⚡ Overview

The **Nautilus F12 Embedded Terminal Extension** injects a native, drop-down terminal console directly into GNOME Files (Nautilus) windows with instantaneous directory tracking and zero GUI lag.

Built with clean architecture and SOLID design principles, this extension cleanly decouples GI version negotiation, VTE widget styling, non-blocking asynchronous process management, layout strategies, and Wayland window-level key interception.

---

## 🛡️ Modular Clean Architecture

The codebase follows the **Strategy Pattern** and strict **Separation of Concerns**:

```text
nautilus-f12/
├── nautilus_f12/
│   ├── __init__.py               # Package exports
│   ├── config.py                 # Centralized configuration & constants
│   ├── gi_stack.py               # Dual-stack GTK3/GTK4 & Nautilus 3/4 negotiator
│   ├── session.py                # High-level terminal session coordinator
│   ├── extension.py              # Nautilus LocationWidgetProvider entrypoint
│   ├── terminal/
│   │   ├── vte_widget.py         # Pure VTE widget (fonts, scrolling, clipboard shortcuts)
│   │   └── shell_process.py      # Non-blocking async process manager & directory sync
│   ├── layouts/
│   │   ├── base.py               # BaseLayoutStrategy abstract interface
│   │   ├── bottom_paned.py       # BottomPanedLayoutStrategy (Gtk.Paned with bottom dock)
│   │   └── top_banner.py         # TopBannerLayoutStrategy (Top banner placement)
│   └── input/
│       └── key_controller.py     # Wayland CAPTURE phase key listener
├── nautilus_f12_terminal.py      # Standalone extension loader
├── CHANGELOG.md                  # Versioned release log with timestamps
├── LICENSE                       # Proprietary commercial license
└── README.md                     # System documentation & deployment guide
```

### Why This Design is Clean & Extensible:
* **Layout Swapping is 1 Line of Code:** Changing between bottom dock (`BottomPanedLayoutStrategy`) and top banner (`TopBannerLayoutStrategy`) is decoupled into swappable layout strategies adhering to `BaseLayoutStrategy`.
* **Zero UI Leakage in Process Management:** `ShellProcess` manages PIDs, signals (`SIGHUP`/`SIGTERM`), async spawning, and `cd` stream feeding without knowing anything about GTK widget layouts.
* **Universal GI Stack Negotiation:** `gi_stack.py` isolates version requirements, preventing `Gtk 3.0` vs `Gtk 4.0` PyGObject namespace clashes across Ubuntu 22.04 LTS and modern GNOME 43+ distributions.
* **Wayland Key Event Interception:** `WindowKeyController` attaches `Gtk.EventControllerKey` with `Gtk.PropagationPhase.CAPTURE` directly on the window to ensure <kbd>F12</kbd> triggers reliably regardless of child focus.

---

## 🔄 Execution Matrix

| Trigger | Action | Process State | Directory Sync |
| :--- | :--- | :--- | :--- |
| **`F12` (First Run)** | Injects VTE container into active view | Spawns fresh shell asynchronously | Initialized to active Nautilus directory path |
| **`F12` (Toggle Hide/Show)** | Toggles visibility (`set_visible`) | Persists in background | Automatically sends `cd <active_path>` on Reveal |
| **`Ctrl+D` / `exit`** | Closes shell | Process cleanly reaped; state reset | N/A |
| **`F12` (After Exit)** | Resets state and reveals | Spawns **new** shell instance | Synchronized to active Nautilus directory path |
| **Folder Navigation** | Updates active path reference | Persists running shell | Syncs immediately if visible, or upon next reveal |

---

## 🛠️ System Prerequisites & Dependencies

Install the required GObject Introspection bindings and Nautilus Python wrapper for your distribution:

### Ubuntu / Debian (22.04 LTS, 24.04 LTS, Debian 12+)
```bash
sudo apt update
sudo apt install -y python3-nautilus gir1.2-gtk-4.0 gir1.2-vte-2.91 python3-gi
```

### Fedora (37+)
```bash
sudo dnf install -y nautilus-python gtk4 vte291-gtk4 python3-gobject
```

### Arch Linux
```bash
sudo pacman -S --needed python-nautilus gtk4 vte4 python-gobject
```

---

## 🚀 Deployment & Installation

### Option 1: Per-User Installation (Recommended)

1. Create the user extensions directory if it does not already exist:
   ```bash
   mkdir -p ~/.local/share/nautilus-python/extensions
   ```

2. Copy the extension package and loader:
   ```bash
   cp -r nautilus_f12 ~/.local/share/nautilus-python/extensions/
   cp nautilus_f12_terminal.py ~/.local/share/nautilus-python/extensions/
   chmod +x ~/.local/share/nautilus-python/extensions/nautilus_f12_terminal.py
   ```

3. Restart Nautilus to load the extension:
   ```bash
   nautilus -q
   ```

### Option 2: System-Wide Installation

```bash
sudo cp -r nautilus_f12 /usr/share/nautilus-python/extensions/
sudo cp nautilus_f12_terminal.py /usr/share/nautilus-python/extensions/
sudo chmod 644 /usr/share/nautilus-python/extensions/nautilus_f12_terminal.py
nautilus -q
```

---

## ⌨️ Shortcuts & Usage

| Shortcut | Description |
| :--- | :--- |
| <kbd>F12</kbd> | Toggle bottom terminal visibility (Hide / Show / Launch) |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>C</kbd> | Copy selected text to clipboard |
| <kbd>Ctrl</kbd> + <kbd>Shift</kbd> + <kbd>V</kbd> | Paste text from clipboard into terminal |
| <kbd>Ctrl</kbd> + <kbd>D</kbd> or `exit` | Terminate active shell process and close terminal |

---

## 🔍 Debugging & Logs

To inspect extension loading and runtime diagnostic output:

```bash
# Kill active instances and launch Nautilus in verbose debug mode
nautilus -q
NAUTILUS_PYTHON_DEBUG=misc nautilus
```

---

## 🔒 License & Copyright

**PROPRIETARY AND CONFIDENTIAL COMMERCIAL SOFTWARE**

Copyright (c) 2026 **Minhajul Anwar** (`minhaj.me.bd@gmail.com`). All Rights Reserved.

- This software is **private and non-redistributable**.
- No unauthorized copying, reverse engineering, sublicensing, or sharing of this codebase is permitted.
- To purchase a commercial license or request deployment rights, contact **Minhajul Anwar** at `minhaj.me.bd@gmail.com`.
- See the full [LICENSE](LICENSE) file for complete legal terms.
