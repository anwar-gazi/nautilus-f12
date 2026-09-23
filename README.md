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

Built specifically to overcome Wayland security sandboxing and modern GTK4 container constraints, this extension attaches input listeners directly to the active application window hierarchy, executes shell processes asynchronously, and manages terminal lifecycles cleanly across tabs, splits, and navigation changes.

---

## 🛡️ Bulletproof Guardrails & Design Principles

* **GTK4 / Nautilus 4.0 Native Layout:** Uses GTK4 widget operations (`Gtk.Box.append()`, `Gtk.ScrolledWindow.set_child()`, `Gtk.Widget.set_visible()`). Eliminates legacy GTK3 crashes (`show_all()`, `add()`, `pack_start()`).
* **Wayland Key Capture:** Utilizes `Gtk.EventControllerKey` attached directly to top-level `NautilusWindow` instances. Global shortcut grabbers fail under Wayland; this approach ensures hotkeys trigger reliably while Nautilus is focused.
* **Non-Blocking Process Spawning:** Shell processes are launched asynchronously using `Vte.Terminal.spawn_async`. Prevents file manager freezing and UI stutters during shell startup.
* **Safe Hierarchy Unparenting:** Automatically unparents location widgets before returning them to new Nautilus slots, preventing widget hierarchy collisions during folder transitions.
* **Subprocess Safety:** Binds to window `destroy` events to automatically terminate orphaned shell processes with `SIGHUP` when Nautilus windows or tabs close.

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

## 🏗️ Architecture & Project Structure

```text
nautilus-f12/
├── nautilus_f12_terminal.py   # Primary Nautilus Python extension & lifecycle engine
├── CHANGELOG.md               # Versioned release log with timestamps
├── LICENSE                    # Proprietary commercial license
└── README.md                  # System documentation & deployment guide
```

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

2. Copy the extension script:
   ```bash
   cp nautilus_f12_terminal.py ~/.local/share/nautilus-python/extensions/
   chmod +x ~/.local/share/nautilus-python/extensions/nautilus_f12_terminal.py
   ```

3. Restart Nautilus to load the extension:
   ```bash
   nautilus -q
   ```

### Option 2: System-Wide Installation

```bash
sudo cp nautilus_f12_terminal.py /usr/share/nautilus-python/extensions/
sudo chmod 644 /usr/share/nautilus-python/extensions/nautilus_f12_terminal.py
nautilus -q
```

---

## ⌨️ Shortcuts & Usage

| Shortcut | Description |
| :--- | :--- |
| <kbd>F12</kbd> | Toggle terminal visibility (Hide / Show / Launch) |
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
