"""Module to ensure that only one instance of basiliskLLM is running at a time.

This module implements platform-specific locking mechanisms to prevent
multiple instances of the application from running simultaneously:
"""

import atexit
from abc import ABC, abstractmethod


class AbstractSingletonInstance(ABC):
	"""Class to ensure that only one instance of basiliskLLM is running at a time.

	This class defines the interface for singleton instance management.
	"""

	@abstractmethod
	def acquire(self) -> bool:
		"""Acquire the lock.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		pass

	@abstractmethod
	def release(self):
		"""Release the lock."""
		pass

	def register_release_on_exit(self):
		"""Register the release method to be called on program exit."""
		atexit.register(self.release)

	@abstractmethod
	def get_existing_pid(self) -> int | None:
		"""Get the PID of the existing instance if it exists.

		Returns:
			The PID of the existing instance, or None if no instance is running.
		"""
		pass

	def is_running(self) -> bool:
		"""Check if another instance of the application is running.

		Returns:
			True if another instance is running, False otherwise.
		"""
		return self.get_existing_pid() is not None
