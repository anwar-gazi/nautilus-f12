"""
Asynchronous Shell Process Management
"""

import os
import signal
import shlex
import logging
from typing import Callable, Optional
from ..gi_stack import GLib, Vte

logger = logging.getLogger("nautilus-f12")


class ShellProcess:
    """
    Manages the lifecycle, async spawning, signals, and command injection for a VTE terminal process.
    """

    def __init__(self, vte_terminal: Vte.Terminal, on_exit_callback: Optional[Callable[[int], None]] = None):
        self.vte = vte_terminal
        self.on_exit_callback = on_exit_callback
        self.pid: Optional[int] = None
        self.is_running = False
        self.last_synced_path: Optional[str] = None
        self._spawn_working_dir: Optional[str] = None
        
        self.vte.connect("child-exited", self._on_vte_child_exited)

    def spawn(self, working_dir: str):
        """Asynchronously spawns user shell in working_dir without blocking UI."""
        if not os.path.isdir(working_dir):
            working_dir = os.path.expanduser("~")

        self._spawn_working_dir = working_dir
        shell_binary = os.environ.get("SHELL", "/bin/bash")
        logger.info(f"Asynchronously launching shell process in '{working_dir}'...")

        try:
            self.vte.spawn_async(
                Vte.PtyFlags.DEFAULT,
                working_dir,
                [shell_binary],
                None,
                GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.SEARCH_PATH,
                None,
                None,
                -1,
                None,
                self._on_spawn_completed,
                None,
            )
        except TypeError:
            try:
                self.vte.spawn_async(
                    Vte.PtyFlags.DEFAULT,
                    working_dir,
                    [shell_binary],
                    None,
                    GLib.SpawnFlags.DEFAULT | GLib.SpawnFlags.SEARCH_PATH,
                    None,
                    -1,
                    None,
                    self._on_spawn_completed,
                    None,
                )
            except Exception as e:
                logger.error(f"VTE spawn_async execution error: {e}")
        except Exception as e:
            logger.error(f"VTE spawn_async execution error: {e}")

    def _on_spawn_completed(self, terminal, pid, error, user_data=None):
        if error is not None:
            logger.error(f"Failed to spawn shell process: {error}")
            self.is_running = False
            self.pid = None
            return

        self.pid = pid
        self.is_running = True
        self.last_synced_path = self._spawn_working_dir
        logger.info(f"Shell process active (PID: {pid}).")

    def _on_vte_child_exited(self, terminal, status: int):
        logger.info(f"Shell process terminated (PID: {self.pid}, status: {status}).")
        self.is_running = False
        self.pid = None
        if self.on_exit_callback:
            self.on_exit_callback(status)

    def change_directory(self, target_path: str):
        """Injects 'cd <path>' into the shell stdin stream."""
        if not self.is_running or not target_path or not os.path.isdir(target_path):
            return

        if target_path == self.last_synced_path:
            return

        logger.info(f"Syncing shell directory -> cd {target_path}")
        cd_cmd = f"cd {shlex.quote(target_path)}\n".encode("utf-8")

        try:
            self.vte.feed_child(cd_cmd)
        except TypeError:
            self.vte.feed_child(cd_cmd, len(cd_cmd))

        self.last_synced_path = target_path

    def terminate(self):
        """Gracefully terminates the child process with SIGHUP/SIGTERM."""
        if self.pid and self.is_running:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
            except Exception as e:
                logger.debug(f"Error terminating PID {self.pid}: {e}")
        self.is_running = False
        self.pid = None
