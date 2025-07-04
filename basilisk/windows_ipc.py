"""Module for Windows-specific inter-process communication using named pipes.

This module provides a Windows-native replacement for the file-based watchdog mechanism,
using named pipes for efficient communication between application instances.
"""

import json
import logging
import sys
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

if sys.platform == "win32":
	import pywintypes
	import win32con
	import win32file
	import win32pipe

logger = logging.getLogger(__name__)


class WindowsSignalType(Enum):
	"""Enumeration of signal types for Windows IPC."""

	FOCUS = "focus"
	OPEN_BSKC = "open_bskc"
	SHUTDOWN = "shutdown"


class WindowsSignalReceiver:
	"""Windows-specific signal receiver using named pipes.

	This class creates a named pipe server that listens for commands from other
	application instances. It replaces the file-based watchdog mechanism with
	a more Windows-native approach.
	"""

	def __init__(self, pipe_name: str, callbacks: Dict[str, Callable]):
		r"""Initialize the Windows signal receiver.

		Args:
			pipe_name: Name of the named pipe (without '\\\\.\\pipe\\' prefix)
			callbacks: Dictionary mapping signal types to callback functions
		"""
		self.pipe_name = f"\\\\.\\pipe\\{pipe_name}"
		self.callbacks = callbacks
		self.running = False
		self.thread = None
		self.pipe_handle = None

	def start(self):
		"""Start the signal receiver in a separate thread."""
		if self.running:
			return

		self.running = True
		self.thread = threading.Thread(target=self._run_server, daemon=True)
		self.thread.start()
		logger.debug(
			"Windows signal receiver started on pipe: %s", self.pipe_name
		)

	def stop(self):
		"""Stop the signal receiver."""
		if not self.running:
			return

		self.running = False

		# Send a shutdown signal to unblock the server
		try:
			self._send_signal(WindowsSignalType.SHUTDOWN, {})
		except Exception:
			pass

		if self.thread and self.thread.is_alive():
			self.thread.join(timeout=5.0)

		if self.pipe_handle:
			try:
				win32file.CloseHandle(self.pipe_handle)
			except Exception:
				pass
			self.pipe_handle = None

		logger.debug("Windows signal receiver stopped")

	def _run_server(self):
		"""Run the named pipe server loop."""
		while self.running:
			try:
				# Create the named pipe
				self.pipe_handle = win32pipe.CreateNamedPipe(
					self.pipe_name,
					win32pipe.PIPE_ACCESS_DUPLEX,
					win32pipe.PIPE_TYPE_MESSAGE
					| win32pipe.PIPE_READMODE_MESSAGE
					| win32pipe.PIPE_WAIT,
					1,  # Maximum number of instances
					65536,  # Output buffer size
					65536,  # Input buffer size
					0,  # Default timeout
					None,  # Security attributes
				)

				if self.pipe_handle == win32file.INVALID_HANDLE_VALUE:
					logger.error("Failed to create named pipe")
					break

				# Wait for a client to connect
				logger.debug("Waiting for client connection...")
				win32pipe.ConnectNamedPipe(self.pipe_handle, None)

				# Read the message
				try:
					result, data = win32file.ReadFile(self.pipe_handle, 65536)
					if result == 0:  # Success
						message = data.decode('utf-8')
						self._process_message(message)
				except pywintypes.error as e:
					if e.winerror != win32con.ERROR_BROKEN_PIPE:
						logger.error("Error reading from pipe: %s", e)

				# Disconnect the client
				win32pipe.DisconnectNamedPipe(self.pipe_handle)
				win32file.CloseHandle(self.pipe_handle)
				self.pipe_handle = None

			except Exception as e:
				logger.error("Error in named pipe server: %s", e)
				time.sleep(1)  # Wait before retrying

	def _process_message(self, message: str):
		"""Process a received message and call appropriate callbacks.

		Args:
			message: JSON-encoded message containing signal type and data
		"""
		try:
			data = json.loads(message)
			signal_type = data.get("type")
			signal_data = data.get("data", {})

			if signal_type == WindowsSignalType.SHUTDOWN.value:
				logger.debug("Received shutdown signal")
				return

			callback_name = f"on_{signal_type}"
			if callback_name in self.callbacks:
				logger.debug("Processing signal: %s", signal_type)
				callback = self.callbacks[callback_name]
				callback(signal_data)
			else:
				logger.warning("Unknown signal type: %s", signal_type)

		except json.JSONDecodeError:
			logger.error("Invalid JSON message received: %s", message)
		except Exception as e:
			logger.error("Error processing message: %s", e)

	def _send_signal(
		self, signal_type: WindowsSignalType, data: Dict[str, Any]
	):
		"""Send a signal to the named pipe (internal use).

		Args:
			signal_type: Type of signal to send
			data: Signal data
		"""
		message = json.dumps({"type": signal_type.value, "data": data})

		try:
			pipe_handle = win32file.CreateFile(
				self.pipe_name,
				win32file.GENERIC_READ | win32file.GENERIC_WRITE,
				0,
				None,
				win32file.OPEN_EXISTING,
				0,
				None,
			)

			win32file.WriteFile(pipe_handle, message.encode('utf-8'))
			win32file.CloseHandle(pipe_handle)

		except pywintypes.error as e:
			logger.error("Error sending signal: %s", e)


class WindowsSignalSender:
	"""Windows-specific signal sender using named pipes.

	This class sends signals to a running application instance through named pipes.
	"""

	def __init__(self, pipe_name: str):
		r"""Initialize the Windows signal sender.

		Args:
			pipe_name: Name of the named pipe (without '\\\\.\\pipe\\' prefix)
		"""
		self.pipe_name = f"\\\\.\\pipe\\{pipe_name}"

	def send_focus_signal(self) -> bool:
		"""Send a focus signal to the running application.

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		return self._send_signal(
			WindowsSignalType.FOCUS, {"timestamp": time.time()}
		)

	def send_open_bskc_signal(self, file_path: str) -> bool:
		"""Send an open BSKC file signal to the running application.

		Args:
			file_path: Path to the BSKC file to open

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		return self._send_signal(
			WindowsSignalType.OPEN_BSKC, {"file_path": file_path}
		)

	def _send_signal(
		self, signal_type: WindowsSignalType, data: Dict[str, Any]
	) -> bool:
		"""Send a signal through the named pipe.

		Args:
			signal_type: Type of signal to send
			data: Signal data

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		message = json.dumps({"type": signal_type.value, "data": data})

		try:
			# Try to connect to the named pipe
			pipe_handle = win32file.CreateFile(
				self.pipe_name,
				win32file.GENERIC_READ | win32file.GENERIC_WRITE,
				0,
				None,
				win32file.OPEN_EXISTING,
				0,
				None,
			)

			# Send the message
			win32file.WriteFile(pipe_handle, message.encode('utf-8'))
			win32file.CloseHandle(pipe_handle)

			logger.debug("Signal sent successfully: %s", signal_type.value)
			return True

		except pywintypes.error as e:
			logger.error("Error sending signal %s: %s", signal_type.value, e)
			return False


def init_windows_signal_receiver(
	pipe_name: str, **callbacks: Callable
) -> Optional[WindowsSignalReceiver]:
	"""Initialize a Windows signal receiver using named pipes.

	This function creates and starts a named pipe server to receive signals from other
	application instances. It's the Windows-native replacement for the file watcher.

	Args:
		pipe_name: Name of the named pipe
		**callbacks: Callback functions for different signal types

	Returns:
		WindowsSignalReceiver instance if successful, None otherwise
	"""
	if sys.platform != "win32":
		logger.warning("Windows signal receiver only works on Windows")
		return None

	try:
		# Map callback names to expected signal handler names
		signal_callbacks = {}
		for name, callback in callbacks.items():
			# Convert send_focus -> on_focus, open_bskc -> on_open_bskc
			if name == "send_focus":
				signal_callbacks["on_focus"] = callback
			elif name == "open_bskc":
				signal_callbacks["on_open_bskc"] = callback
			else:
				signal_callbacks[f"on_{name}"] = callback

		receiver = WindowsSignalReceiver(pipe_name, signal_callbacks)
		receiver.start()
		return receiver

	except Exception as e:
		logger.error("Failed to initialize Windows signal receiver: %s", e)
		return None
