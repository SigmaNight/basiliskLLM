"""Windows-specific inter-process communication using named pipes.

This module provides a Windows-native IPC implementation using named pipes
for efficient communication between application instances.
"""

import logging
import threading
import time

import pywintypes
import win32con
import win32file
import win32pipe

from .abstract_ipc import AbstractIpc

logger = logging.getLogger(__name__)


class WindowsIpc(AbstractIpc):
	"""Windows-specific IPC implementation using named pipes.

	This class provides Windows-native inter-process communication using named pipes
	for efficient communication between application instances.
	"""

	# Named pipe configuration
	PIPE_BUFFER_SIZE = 65536  # 64KB buffer for pipe I/O
	# Retry configuration for sending signals
	MAX_SEND_RETRIES = 5
	# time between retries
	RETRY_DELAY_SECONDS = 0.05

	def __init__(self, pipe_name: str):
		r"""Initialize the Windows IPC mechanism.

		Args:
			pipe_name: Name of the named pipe (without '\\\\.\\pipe\\' prefix)
		"""
		super().__init__(pipe_name)
		self.pipe_name = f"\\\\.\\pipe\\{pipe_name}"

	def _handle_connection(self, pipe_handle):
		"""Handle a client connection to the named pipe.

		Args:
			pipe_handle: Handle to the connected named pipe
		"""
		try:
			# Read the message
			result, data = win32file.ReadFile(
				pipe_handle, self.PIPE_BUFFER_SIZE
			)
			if result == 0:  # Success
				message = data.decode("utf-8")
				self._process_message(message)
		except pywintypes.error as e:
			if e.winerror != win32con.ERROR_BROKEN_PIPE:
				logger.error("Error reading from pipe: %s", e)
		finally:
			# Disconnect the client
			win32pipe.DisconnectNamedPipe(pipe_handle)
			win32file.CloseHandle(pipe_handle)

	def _run_server(self):
		"""Run the named pipe server loop with concurrent connection handling."""
		while self.running:
			try:
				# Create the named pipe with multiple instances support
				pipe_handle = win32pipe.CreateNamedPipe(
					self.pipe_name,
					win32pipe.PIPE_ACCESS_DUPLEX,
					win32pipe.PIPE_TYPE_MESSAGE
					| win32pipe.PIPE_READMODE_MESSAGE
					| win32pipe.PIPE_WAIT,
					win32pipe.PIPE_UNLIMITED_INSTANCES,  # Allow multiple instances
					self.PIPE_BUFFER_SIZE,  # Output buffer size
					self.PIPE_BUFFER_SIZE,  # Input buffer size
					0,  # Default timeout
					None,  # Security attributes
				)

				if pipe_handle == win32file.INVALID_HANDLE_VALUE:
					logger.error("Failed to create named pipe")
					break

				# Wait for a client to connect
				logger.debug("Waiting for client connection...")
				win32pipe.ConnectNamedPipe(pipe_handle, None)

				# Start handling connection in a separate thread
				connection_thread = threading.Thread(
					target=self._handle_connection,
					args=(pipe_handle,),
					daemon=True,
				)
				connection_thread.start()

			except Exception as e:
				logger.error("Error in named pipe server: %s", e)
				time.sleep(0.1)  # Wait before retrying (reduced wait time)

	def send_signal(self, data: str) -> bool:
		"""Send a signal through the named pipe.

		Args:
			data: Signal data

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		for attempt in range(self.MAX_SEND_RETRIES):
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
				win32file.WriteFile(pipe_handle, data.encode("utf-8"))
				win32file.CloseHandle(pipe_handle)

				logger.debug("Signal sent successfully: %s", data)
				return True

			except pywintypes.error as e:
				if attempt < self.MAX_SEND_RETRIES - 1:
					logger.debug(
						"Retry %d/%d for signal %s: %s",
						attempt + 1,
						self.MAX_SEND_RETRIES,
						data,
						e,
					)
					time.sleep(self.RETRY_DELAY_SECONDS)
				else:
					logger.error(
						"Error sending signal %s after %d attempts: %s",
						data,
						self.MAX_SEND_RETRIES,
						e,
					)
					return False

		return False

	def _cleanup_resources(self):
		"""Clean up platform-specific resources."""
		# No persistent pipe handle to clean up since we use per-connection handles
		pass
