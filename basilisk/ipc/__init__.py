"""Inter-process communication module for Basilisk.

This module provides platform-specific IPC implementations for efficient
communication between application instances.
"""

import sys

from .ipc_model import FocusSignal, OpenBskcSignal, ShutdownSignal

if sys.platform == "win32":
	from .windows_ipc import WindowsIpc as BasiliskIpc
else:
	from .unix_ipc import UnixIpc as BasiliskIpc

__all__ = ["BasiliskIpc", "FocusSignal", "OpenBskcSignal", "ShutdownSignal"]
