"""Module for sending signals to a running basiliskLLM application.

This module provides a unified interface for sending signals to a running
application instance using platform-specific IPC mechanisms.
"""

import logging

from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal

logger = logging.getLogger(__name__)


def send_focus_signal():
	"""Send a focus signal to the running application.

	This uses the platform-specific IPC mechanism (named pipes on Windows,
	Unix domain sockets on Unix-like systems).
	"""
	try:
		ipc = BasiliskIpc("basilisk_ipc")
		if ipc.send_signal(FocusSignal().model_dump_json()):
			return
	except Exception as e:
		logger.error("Failed to send focus signal via IPC: %s", e)


def send_open_bskc_file_signal(bskc_file: str):
	"""Send a signal to open a BSKC file in the running application.

	Args:
		bskc_file: The path of the BSKC file to be opened.

	This uses the platform-specific IPC mechanism (named pipes on Windows,
	Unix domain sockets on Unix-like systems).
	"""
	try:
		ipc = BasiliskIpc("basilisk_ipc")
		signal = OpenBskcSignal(file_path=bskc_file)
		if ipc.send_signal(signal.model_dump_json()):
			return
	except Exception as e:
		logger.error("Failed to send open BSKC signal via IPC: %s", e)
