"""Unix-specific inter-process communication using Unix domain sockets.

This module provides a Unix-native IPC implementation using Unix domain sockets
for efficient communication between application instances.
"""

import logging
import os
import socket
import threading

from .abstract_ipc import AbstractIpc

logger = logging.getLogger(__name__)


class UnixIpc(AbstractIpc):
	"""Unix-specific IPC implementation using Unix domain sockets.

	This class provides Unix-native inter-process communication using Unix domain sockets
	for efficient communication between application instances.
	"""

	def __init__(self, pipe_name: str):
		"""Initialize the Unix IPC mechanism.

		Args:
			pipe_name: Name of the Unix domain socket
		"""
		super().__init__(pipe_name)
		# Create socket path in temporary directory
		self.socket_path = f"/tmp/basilisk_{pipe_name}.sock"
		self.server_socket = None

	def _run_server(self):
		"""Run the Unix domain socket server loop."""
		try:
			# Remove existing socket file if it exists
			if os.path.exists(self.socket_path):
				os.unlink(self.socket_path)

			# Create and bind the socket
			self.server_socket = socket.socket(
				socket.AF_UNIX, socket.SOCK_STREAM
			)
			self.server_socket.bind(self.socket_path)
			self.server_socket.listen(1)

			# Set socket timeout to allow periodic checks of running flag
			self.server_socket.settimeout(1.0)

			logger.debug("Unix socket server listening on %s", self.socket_path)

			while self.running:
				try:
					# Accept connections
					client_socket, _ = self.server_socket.accept()

					# Handle the connection in a separate thread
					threading.Thread(
						target=self._handle_client,
						args=(client_socket,),
						daemon=True,
					).start()

				except socket.timeout:
					# Timeout is normal, just continue the loop
					continue
				except Exception as e:
					if self.running:
						logger.error("Error accepting connection: %s", e)
					break

		except Exception as e:
			logger.error("Error in Unix socket server: %s", e)
		finally:
			if self.server_socket:
				self.server_socket.close()

	def _handle_client(self, client_socket):
		"""Handle a client connection.

		Args:
			client_socket: The client socket connection
		"""
		try:
			# Receive the message
			data = client_socket.recv(65536)
			if data:
				message = data.decode("utf-8")
				self._process_message(message)

		except Exception as e:
			logger.error("Error handling client: %s", e)
		finally:
			client_socket.close()

	def send_signal(self, data: str) -> bool:
		"""Send a signal through the Unix domain socket.

		Args:
			data: Signal data

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		try:
			# Create and connect to the socket
			client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
			client_socket.connect(self.socket_path)

			# Send the message
			client_socket.send(data.encode("utf-8"))
			client_socket.close()

			logger.debug("Signal sent successfully: %s", data)
			return True

		except (socket.error, ConnectionRefusedError, FileNotFoundError) as e:
			logger.error("Error sending signal %s: %s", data, e)
			return False

	def _cleanup_resources(self):
		"""Clean up platform-specific resources."""
		if self.server_socket:
			try:
				self.server_socket.close()
			except Exception:
				pass
			self.server_socket = None

		# Clean up socket file
		if os.path.exists(self.socket_path):
			try:
				os.unlink(self.socket_path)
			except Exception:
				pass
