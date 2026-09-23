# Changelog

All notable changes to the **Nautilus F12 Embedded Terminal Extension** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.0] - (23-09-2026 09:38 AM GMT+6)

### Added
- **Bottom-Docked Split Layout Architecture (`Gtk.Paned`)**:
  - Moved the terminal from the top location bar into the bottom of the active `NautilusWindowSlot`.
  - Re-architected widget hierarchy using vertical `Gtk.Paned`: top pane houses the file browser view, and bottom pane embeds the resizable `Vte.Terminal`.
  - Added lightweight `TerminalAnchor` to automatically detect slot insertion, relocate file view widgets into the top pane, and inject the bottom terminal.
  - Added a horizontal separator bar and interactive resize handle between the file list and the bottom terminal console.

---

## [1.1.1] - (23-09-2026 09:35 AM GMT+6)

### Fixed
- **PyGObject Dynamic Namespace Negotiation Conflict**:
  - Resolved `ValueError` / `RepositoryError` caused by requesting `Gtk 4.0` while running on Ubuntu 22.04 LTS's `gir1.2-nautilus-3.0` package.
  - Implemented coupled dual-stack version probing (`Nautilus 4.0 + Gtk 4.0 + Vte 3.91` with fallback to `Nautilus 3.0 + Gtk 3.0 + Vte 2.91`).
- **Wayland Key Event Interception**:
  - Configured `Gtk.PropagationPhase.CAPTURE` on `Gtk.EventControllerKey` so <kbd>F12</kbd> keypresses are reliably captured before child views or search entries consume them.
- **GTK3 Visibility & Packing Toggle**:
  - Added `set_no_show_all` / `show_all` handling for GTK3 runtime environments alongside GTK4 `set_visible`.

---

## [1.1.0] - (23-09-2026 09:27 AM GMT+6)

### Added
- **Production Documentation & Deployment Guide (`README.md`)**:
  - Authored comprehensive project documentation covering GTK4 architectural principles, Wayland event handling, execution matrix, system dependency commands across Ubuntu/Debian/Fedora/Arch, deployment instructions, keybindings, and debugging workflows.
- **Commercial Licensing Terms (`LICENSE`)**:
  - Published proprietary and confidential commercial license establishing clear intellectual property protection and licensing terms.
- **Repository Environment Configurations**:
  - Added `.gitignore` configured for Python development to prevent committing bytecode, cached artifacts, and editor temporary files.

---

## [1.0.0] - (23-09-2026 09:25 AM GMT+6)

### Added
- **Core Nautilus Python Extension (`nautilus_f12_terminal.py`)**:
  - Implemented `Nautilus.LocationWidgetProvider` extension class with automatic multi-window tracking (`WindowTerminalManager`).
  - Added GObject Introspection dynamic negotiation supporting both modern GTK4/Nautilus 4.0 APIs and backward-compatible GTK3 fallbacks.
- **GTK4 Native Layout & Packing Engine**:
  - Replaced legacy container APIs with GTK4-native primitives (`Gtk.Box.append()`, `Gtk.ScrolledWindow.set_child()`, `Gtk.Widget.set_visible()`).
  - Added safe widget unparenting (`unparent()`) before returning location containers to prevent GTK hierarchy reparenting collisions during Nautilus directory navigation.
- **Wayland-Safe Event Delivery**:
  - Integrated `Gtk.EventControllerKey` attached directly to top-level `NautilusWindow` instances to capture <kbd>F12</kbd> keypresses reliably under Wayland and X11 compositors without requiring global hotkey permissions.
  - Added terminal-level shortcut accelerators for clipboard operations (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>V</kbd>).
- **Asynchronous VTE Shell Spawning & Process Lifecycle**:
  - Built non-blocking child shell spawning utilizing `Vte.Terminal.spawn_async` with `GLib.SpawnFlags.SEARCH_PATH` to guarantee zero GUI freezing.
  - Connected `child-exited` signals to detect <kbd>Ctrl</kbd>+<kbd>D</kbd> and `exit` commands, automatically clearing dead subprocess states and resetting VTE instances for subsequent clean re-spawns.
  - Added parent window `destroy` signal handlers to safely terminate orphaned shell processes with `SIGHUP` when closing Nautilus tabs/windows.
- **Active Directory Synchronization**:
  - Built bidirectional directory sync parsing Nautilus GVFS URIs (`Gio.File.new_for_uri()`) to local paths.
  - Implemented automated `cd <path>` injection into the active VTE child stream via `feed_child()` upon terminal reveal (<kbd>F12</kbd>) and folder navigation.
