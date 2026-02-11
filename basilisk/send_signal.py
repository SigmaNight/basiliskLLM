"""Module for sending signals to a running basiliskLLM application.

This module provides a unified interface for sending signals to a running
application instance using platform-specific IPC mechanisms.
"""

import logging

from basilisk.consts import APP_NAME
from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal

logger = logging.getLogger(__name__)


def _display_error_msg_windows(message: str):
	"""Display error message on Windows using pywin32.

	Args:
		message: The error message to display
	"""
	import win32api
	import win32con

	win32api.MessageBox(
		0, message, APP_NAME, win32con.MB_ICONERROR | win32con.MB_OK
	)


def _display_error_msg_macos(message: str):
	"""Display error message on macOS using osascript.

	Args:
		message: The error message to display
	"""
	import subprocess

	try:
		subprocess.run(
			[
				"osascript",
				"-e",
				'display dialog "%s" with title "%s" with icon stop buttons {"OK"} default button "OK"'
				% (message.replace('"', '\\"'), APP_NAME),
			],
			check=True,
		)
	except subprocess.CalledProcessError, FileNotFoundError:
		# Fallback to logging
		logger.error("ERROR: %s", message)


def _display_error_msg_linux(message: str):
	"""Display error message on Linux using zenity or kdialog.

	Args:
		message: The error message to display
	"""
	import subprocess

	try:
		# Try to use zenity (common on Linux)
		subprocess.run(
			[
				"zenity",
				"--error",
				"--title",
				APP_NAME,
				"--text",
				message,
				"--width",
				"400",
			],
			check=True,
		)
	except subprocess.CalledProcessError, FileNotFoundError:
		try:
			# Try to use kdialog (KDE)
			subprocess.run(
				["kdialog", "--error", message, "--title", APP_NAME], check=True
			)
		except subprocess.CalledProcessError, FileNotFoundError:
			# Fallback to logging
			logger.error("ERROR: %s", message)


def display_signal_error_msg(signal_type: str, error_details: str = ""):
	"""Display a message box indicating that a signal could not be sent.

	Args:
		signal_type: Type of signal that failed (e.g., "focus", "open file")
		error_details: Optional additional error details

	Notes:
		- Uses platform-specific message display methods
		- Windows: MessageBox with error icon via pywin32
		- macOS: osascript with native error dialog
		- Unix/Linux: zenity/kdialog with error styling
		- Fallback: logging for systems without GUI tools
		- Message includes signal type and error guidance
	"""
	import sys

	message_dict = {
		"focus": f"Unable to send focus signal to {APP_NAME}. The application may not be running or may be unresponsive.",
		"open_file": f"Unable to send file opening signal to {APP_NAME}. The application may not be running or may be unresponsive.",
	}
	message = message_dict.get(
		signal_type,
		f"Unable to send signal to {APP_NAME}. The application may not be running or may be unresponsive.",
	)

	if error_details:
		message += f"\n\nTechnical details: {error_details}"

	if sys.platform == "win32":
		_display_error_msg_windows(message)
	elif sys.platform == "darwin":
		_display_error_msg_macos(message)
	else:
		_display_error_msg_linux(message)


def send_focus_signal() -> None:
	"""Send a focus signal to the running application.

	This uses the platform-specific IPC mechanism (named pipes on Windows,
	Unix domain sockets on Unix-like systems).

	If the signal cannot be sent, displays an error message to the user.
	"""
	try:
		ipc = BasiliskIpc("basilisk_ipc")
		if ipc.send_signal(FocusSignal().model_dump_json()):
			return
		else:
			# Signal sending failed
			logger.error("Failed to send focus signal via IPC")
			display_signal_error_msg("focus")
	except Exception as e:
		logger.error("Failed to send focus signal via IPC: %s", e)
		display_signal_error_msg("focus", str(e))


def send_open_bskc_file_signal(bskc_file: str) -> None:
	"""Send a signal to open a BSKC file in the running application.

	Args:
		bskc_file: The path of the BSKC file to be opened.

	This uses the platform-specific IPC mechanism (named pipes on Windows,
	Unix domain sockets on Unix-like systems).

	If the signal cannot be sent, displays an error message to the user.
	"""
	try:
		ipc = BasiliskIpc("basilisk_ipc")
		signal = OpenBskcSignal(file_path=bskc_file)
		if ipc.send_signal(signal.model_dump_json()):
			return
		else:
			# Signal sending failed
			logger.error("Failed to send open BSKC signal via IPC")
			display_signal_error_msg("open_file")
	except Exception as e:
		logger.error("Failed to send open BSKC signal via IPC: %s", e)
		display_signal_error_msg("open_file", str(e))
