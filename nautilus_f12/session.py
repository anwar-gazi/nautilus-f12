"""
Terminal Session Coordinator
"""

import os
import logging
from typing import Optional
from .gi_stack import Gtk
from .terminal import VteTerminalWidget, ShellProcess
from .layouts import BaseLayoutStrategy, BottomPanedLayoutStrategy

logger = logging.getLogger("nautilus-f12")


class TerminalSession:
    """
    Coordinates the terminal widget, shell process lifecycle, and layout strategy for a slot.
    """

    def __init__(
        self,
        slot_widget: Gtk.Widget,
        window: Gtk.Window,
        initial_path: str,
        layout_strategy: Optional[BaseLayoutStrategy] = None,
        on_destroy_callback: Optional[callable] = None,
    ):
        self.slot = slot_widget
        self.window = window
        self.current_path = initial_path if initial_path else os.path.expanduser("~")
        self.on_destroy_callback = on_destroy_callback
        
        # State
        self.is_visible = False
        self.terminal_widget: Optional[VteTerminalWidget] = None
        self.shell_process: Optional[ShellProcess] = None
        
        # Injected layout strategy (defaults to BottomPanedLayoutStrategy)
        self.layout: BaseLayoutStrategy = layout_strategy or BottomPanedLayoutStrategy()
        
        # Mount non-destructively into slot
        self.layout.mount(self.slot, None)
        
        # Handle slot and window destruction
        self.slot.connect("destroy", self._on_slot_destroy)
        self.window.connect("destroy", self._on_window_destroy)

    def _ensure_terminal_spawned(self):
        """Creates VTE widget and spawns shell if not already active."""
        if self.terminal_widget is None or self.shell_process is None or not self.shell_process.is_running:
            self.terminal_widget = VteTerminalWidget()
            self.shell_process = ShellProcess(
                self.terminal_widget.get_widget(),
                on_exit_callback=self._on_shell_exit,
            )
            self.layout.set_child_widget(self.terminal_widget.get_widget())
            
            spawn_path = self.current_path if os.path.isdir(self.current_path) else os.path.expanduser("~")
            self.shell_process.spawn(spawn_path)

    def toggle(self):
        """Toggles terminal visibility according to the execution matrix."""
        logger.info("Toggling terminal session...")
        if self.shell_process is None or not self.shell_process.is_running:
            self._ensure_terminal_spawned()
            self.show()
        else:
            if self.is_visible:
                self.hide()
            else:
                self.show()

    def show(self):
        """Reveals terminal, synchronizes directory, and focuses input."""
        self._ensure_terminal_spawned()
        self.layout.show()
        self.is_visible = True
        
        if self.shell_process:
            self.shell_process.change_directory(self.current_path)
            
        if self.terminal_widget:
            self.terminal_widget.grab_focus()

    def hide(self):
        """Hides terminal while keeping background process alive."""
        self.layout.hide()
        self.is_visible = False

    def update_location(self, new_path: str):
        """Updates directory when user navigates inside Nautilus."""
        self.current_path = new_path
        if self.is_visible and self.shell_process and self.shell_process.is_running:
            self.shell_process.change_directory(new_path)

    def _on_shell_exit(self, status: int):
        """Matrix Case 3: Ctrl+D / Exit handling."""
        logger.info(f"Shell exited with status {status}. Resetting session.")
        self.hide()
        self.layout.set_child_widget(None)
        self.terminal_widget = None
        self.shell_process = None

    def terminate(self):
        """Terminates shell process cleanly."""
        if self.shell_process:
            self.shell_process.terminate()

    def _on_slot_destroy(self, widget):
        """Cleans up child processes and callback when the tab/slot closes."""
        self.terminate()
        if self.on_destroy_callback:
            self.on_destroy_callback(self.slot)

    def _on_window_destroy(self, widget):
        """Cleans up child processes on window close."""
        self.terminate()
