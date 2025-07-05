"""Module to ensure that only one instance of basiliskLLM is running at a time.

This module implements platform-specific locking mechanisms to prevent
multiple instances of the application from running simultaneously:
- Windows: Uses pywin32 named mutex
"""

from typing import Optional

import win32api
import win32event
import winerror

from basilisk.consts import APP_NAME

from .abstract_singleton_instance import AbstractSingletonInstance


class WindowsSingletonInstance(AbstractSingletonInstance):
	"""Class to ensure that only one instance of basiliskLLM is running at a time.

	This class implements platform-specific locking mechanisms:
	- Windows: Uses named mutex through pywin32
	- Prevents multiple instances from running simultaneously
	- Automatically releases the lock on program exit
	- Provides methods to check for existing instances and get their PIDs
	"""

	def __init__(self):
		"""Initialize the SingletonInstance object.

		Args:
			mutex_name: Name for the mutex (Windows only)
		"""
		self.mutex_handle = None

		# Create a unique mutex name for the application
		self.mutex_name = f"Global\\{APP_NAME}"

	def acquire(self) -> bool:
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
			self.register_release_on_exit()
			return True
		except Exception:
			if self.mutex_handle:
				win32api.CloseHandle(self.mutex_handle)
				self.mutex_handle = None
			return False

	def release(self):
		"""Release the Windows mutex."""
		if self.mutex_handle:
			try:
				win32event.ReleaseMutex(self.mutex_handle)
				win32api.CloseHandle(self.mutex_handle)
			except Exception:
				pass
			finally:
				self.mutex_handle = None

	def get_existing_pid(self) -> Optional[int]:
		"""Get the PID of the existing instance, if any.

		Note: On Windows with mutex-based locking, this method cannot reliably
		determine the PID of the existing instance. It returns -1 if another
		instance is detected but the PID cannot be determined.

		Returns:
			On Windows, returns -1 if another instance exists but PID cannot be determined.
		"""
		# On Windows, we can't easily get the PID from a mutex
		# We can only check if another instance exists
		try:
			test_mutex = win32event.CreateMutex(None, True, self.mutex_name)
			if win32api.GetLastError() == winerror.ERROR_ALREADY_EXISTS:
				win32api.CloseHandle(test_mutex)
				return (
					-1
				)  # Return a special value to indicate another instance exists
			else:
				win32event.ReleaseMutex(test_mutex)
				win32api.CloseHandle(test_mutex)
				return None
		except Exception:
			return None
