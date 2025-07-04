"""Module to ensure that only one instance of basiliskLLM is running at a time.

This module implements a Windows-specific mutex-based locking mechanism to prevent
multiple instances of the application from running simultaneously. It uses pywin32
to create and manage a named mutex for single instance enforcement.
"""

import atexit
import os
import sys
from typing import Optional

if sys.platform == "win32":
	import win32api
	import win32event
	import winerror


class SingletonInstance:
	"""Class to ensure that only one instance of basiliskLLM is running at a time.

	This class implements a platform-specific locking mechanism:
	- On Windows: Uses named mutex through pywin32
	- On other platforms: Falls back to file-based locking
	- Prevents multiple instances from running simultaneously
	- Automatically releases the lock on program exit
	- Provides methods to check for existing instances
	"""

	def __init__(self, mutex_name: str):
		"""Initialize the SingletonInstance object.

		Args:
			mutex_name: Name for the mutex (Windows) or path for lock file (other platforms)
		"""
		self.mutex_name = mutex_name
		self.mutex_handle = None
		self.lock_file_handle = None
		self.is_windows = sys.platform == "win32"

		if self.is_windows:
			# Create a unique mutex name for the application
			self.mutex_name = (
				f"Global\\{mutex_name.replace('\\', '_').replace('/', '_')}"
			)
		else:
			# Use the provided path as lock file path for non-Windows systems
			self.lock_file_path = mutex_name

	def acquire(self) -> bool:
		"""Acquire the lock.

		This method attempts to create a mutex (Windows) or lock file (other platforms).
		It handles errors during lock acquisition and automatically registers cleanup
		on program exit.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		if self.is_windows:
			return self._acquire_windows()
		else:
			return self._acquire_posix()

	def _acquire_windows(self) -> bool:
		"""Acquire the mutex on Windows using pywin32.

		Returns:
			True if the mutex was acquired, False if another instance is already running.
		"""
		try:
			# Create or open the named mutex
			self.mutex_handle = win32event.CreateMutex(
				None, True, self.mutex_name
			)

			# Check if the mutex already existed
			if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
				# Another instance is already running
				win32api.CloseHandle(self.mutex_handle)
				self.mutex_handle = None
				return False

			# Successfully acquired the mutex
			atexit.register(self.release)
			return True

		except Exception:
			if self.mutex_handle:
				win32api.CloseHandle(self.mutex_handle)
				self.mutex_handle = None
			return False

	def _acquire_posix(self) -> bool:
		"""Acquire the lock on POSIX systems using file locking.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		try:
			if os.path.exists(self.lock_file_path):
				return False

			self.lock_file_handle = open(self.lock_file_path, 'w')
			self.lock_file_handle.write(str(os.getpid()))
			self.lock_file_handle.flush()

			atexit.register(self.release)
			return True

		except Exception:
			self.release()
			return False

	def release(self):
		"""Release the lock.

		This method releases the mutex (Windows) or removes the lock file (other platforms).
		"""
		if self.is_windows:
			self._release_windows()
		else:
			self._release_posix()

	def _release_windows(self):
		"""Release the Windows mutex."""
		if self.mutex_handle:
			try:
				win32event.ReleaseMutex(self.mutex_handle)
				win32api.CloseHandle(self.mutex_handle)
			except Exception:
				pass
			finally:
				self.mutex_handle = None

	def _release_posix(self):
		"""Release the POSIX lock file."""
		if self.lock_file_handle:
			try:
				self.lock_file_handle.close()
			except Exception:
				pass
			finally:
				self.lock_file_handle = None

		try:
			if hasattr(self, 'lock_file_path'):
				os.remove(self.lock_file_path)
		except Exception:
			pass

	def get_existing_pid(self) -> Optional[int]:
		"""Get the PID of the existing instance, if any.

		Note: On Windows with mutex-based locking, this method cannot reliably
		determine the PID of the existing instance. It returns None if another
		instance is detected but the PID cannot be determined.

		Returns:
			The PID of the existing instance (POSIX only), or None if no instance
			is running or PID cannot be determined.
		"""
		if self.is_windows:
			# On Windows, we can't easily get the PID from a mutex
			# We can only check if another instance exists
			try:
				test_mutex = win32event.CreateMutex(None, True, self.mutex_name)
				if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
					win32api.CloseHandle(test_mutex)
					return -1  # Return a special value to indicate another instance exists
				else:
					win32event.ReleaseMutex(test_mutex)
					win32api.CloseHandle(test_mutex)
					return None
			except Exception:
				return None
		else:
			# POSIX file-based approach
			if os.path.exists(self.lock_file_path):
				try:
					with open(self.lock_file_path, 'r') as f:
						return int(f.read().strip())
				except Exception:
					return None
			return None

	def is_running(self) -> bool:
		"""Check if another instance of the application is running.

		Returns:
			True if another instance is running, False otherwise.
		"""
		return self.get_existing_pid() is not None
