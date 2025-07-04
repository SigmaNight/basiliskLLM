"""Module for sending signals to a running basiliskLLM application.

This module provides both Windows-native (named pipes) and fallback (file-based)
methods for sending signals to a running application instance.
"""

import sys
import time

from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE

# Import Windows IPC only on Windows
if sys.platform == "win32":
	from basilisk.windows_ipc import WindowsSignalSender


def send_focus_signal():
	"""Send a focus signal to the running application.

	On Windows, this uses named pipes for efficient IPC.
	On other platforms, it falls back to file-based signaling.
	"""
	if sys.platform == "win32":
		try:
			sender = WindowsSignalSender("basilisk_ipc")
			if sender.send_focus_signal():
				return
		except Exception:
			# Fall back to file-based method if Windows IPC fails
			pass

	# Fallback to file-based method
	with open(FOCUS_FILE, 'w') as f:
		f.write(str(time.time()))


def send_open_bskc_file_signal(bskc_file: str):
	"""Send a signal to open a BSKC file in the running application.

	Args:
		bskc_file: The path of the BSKC file to be opened.

	On Windows, this uses named pipes for efficient IPC.
	On other platforms, it falls back to file-based signaling.
	"""
	if sys.platform == "win32":
		try:
			sender = WindowsSignalSender("basilisk_ipc")
			if sender.send_open_bskc_signal(bskc_file):
				return
		except Exception:
			# Fall back to file-based method if Windows IPC fails
			pass

	# Fallback to file-based method
	with open(OPEN_BSKC_FILE, 'w') as f:
		f.write(bskc_file)
