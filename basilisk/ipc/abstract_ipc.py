"""Abstract base class for inter-process communication mechanisms.

This module provides the abstract interface for IPC implementations across different platforms.
"""

import abc
import logging
import threading
from typing import Callable, Dict

from pydantic import ValidationError

from .ipc_model import IPCModels, ShutdownSignal

logger = logging.getLogger(__name__)


class AbstractIpc(abc.ABC):
	"""Abstract base class for inter-process communication.

	This class defines the interface that all IPC implementations must follow.
	Concrete implementations should inherit from this class and implement the
	abstract methods for their specific platform.
	"""

	def __init__(self, pipe_name: str):
		"""Initialize the IPC mechanism.

		Args:
			pipe_name: Name of the communication channel (pipe, socket, etc.)
		"""
		self.pipe_name = pipe_name
		self.callbacks = {}
		self.running = False
		self.thread = None

	def start_receiver(self, callbacks: Dict[str, Callable]) -> bool:
		"""Start the IPC receiver to listen for incoming signals.

		Args:
			callbacks: Dictionary mapping signal types to callback functions

		Returns:
			True if the receiver was started successfully, False otherwise
		"""
		if self.running:
			return True

		try:
			# Map callback names to expected signal handler names
			self.callbacks = self._map_callbacks(callbacks)
			self.running = True
			self.thread = threading.Thread(target=self._run_server, daemon=True)
			self.thread.start()
			logger.debug("IPC receiver started")
			return True

		except Exception as e:
			logger.error("Failed to start IPC receiver: %s", e)
			return False

	def stop_receiver(self) -> None:
		"""Stop the IPC receiver."""
		if not self.running:
			return

		self.running = False

		# Send a shutdown signal to unblock the server
		try:
			self.send_signal(ShutdownSignal().model_dump_json())
		except Exception:
			pass

		# Wait for thread to finish
		if self.thread and self.thread.is_alive():
			self.thread.join(timeout=5.0)

		# Platform-specific cleanup
		self._cleanup_resources()

		logger.debug("IPC receiver stopped")

	def is_running(self) -> bool:
		"""Check if the IPC receiver is currently running.

		Returns:
			True if the receiver is running, False otherwise
		"""
		return self.running

	def _map_callbacks(
		self, callbacks: Dict[str, Callable]
	) -> Dict[str, Callable]:
		"""Map callback names to expected signal handler names.

		Args:
			callbacks: Dictionary mapping callback names to functions

		Returns:
			Dictionary with properly mapped callback names
		"""
		signal_callbacks = {}
		for name, callback in callbacks.items():
			# Convert send_focus -> on_focus, open_bskc -> on_open_bskc
			if name == "send_focus":
				signal_callbacks["on_focus"] = callback
			elif name == "open_bskc":
				signal_callbacks["on_open_bskc"] = callback
			else:
				signal_callbacks[f"on_{name}"] = callback
		return signal_callbacks

	def _process_message(self, message: str):
		"""Process a received message and call appropriate callbacks.

		Args:
			message: JSON-encoded message containing signal type and data
		"""
		try:
			ipc_model = IPCModels.validate_json(message)

			if isinstance(ipc_model, ShutdownSignal):
				logger.debug("Received shutdown signal")
				return

			callback_name = f"on_{ipc_model.signal_type}"
			if callback_name in self.callbacks:
				logger.debug("Processing signal: %s", ipc_model.signal_type)
				callback = self.callbacks[callback_name]
				callback(ipc_model)
			else:
				logger.warning("Unknown signal type: %s", ipc_model.signal_type)
		except ValidationError as ve:
			logger.error("Invalid JSON message received: %s", ve)
		except Exception as e:
			logger.error("Error processing message: %s", e)

	@abc.abstractmethod
	def _run_server(self):
		"""Run the platform-specific server loop."""
		pass

	@abc.abstractmethod
	def send_signal(self, data: str) -> bool:
		"""Send a signal through the platform-specific mechanism.

		Args:
			data: Signal data

		Returns:
			True if the signal was sent successfully, False otherwise
		"""
		pass

	@abc.abstractmethod
	def _cleanup_resources(self):
		"""Clean up platform-specific resources."""
		pass
