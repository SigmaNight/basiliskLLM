"""Module to ensure that only one instance of basiliskLLM is running at a time."""

import atexit
import os


class SingletonInstance:
	"""Class to ensure that only one instance of basiliskLLM is running at a time."""

	def __init__(self, lock_file: str):
		"""Initialize the SingletonInstance object.

		Args:
			lock_file: Path to the lock file
		"""
		self.lock_file = lock_file
		self.lock_handle = None

	def acquire(self) -> bool:
		"""Acquire the lock.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		if os.path.exists(self.lock_file):
			return False
		self.lock_handle = open(self.lock_file, 'w')
		try:
			self.lock_handle.write(str(os.getpid()))
			self.lock_handle.flush()
		except Exception:
			self.release()
			return False
		atexit.register(self.release)
		return True

	def release(self):
		"""Release the lock."""
		if self.lock_handle:
			try:
				self.lock_handle.close()
			except Exception:
				pass
			try:
				os.remove(self.lock_file)
			except Exception:
				pass

	def get_existing_pid(self) -> int | None:
		"""Get the PID of the existing instance, if any.

		Returns:
			The PID of the existing instance, or None if no instance is running.
		"""
		if os.path.exists(self.lock_file):
			with open(self.lock_file, 'r') as f:
				return int(f.read().strip())
		return None
