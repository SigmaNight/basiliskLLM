"""Module to ensure that only one instance of basiliskLLM is running at a time.

This module implements platform-specific locking mechanisms to prevent
multiple instances of the application from running simultaneously:
- Windows: Uses pywin32 named mutex
- POSIX: Uses fcntl file locking with proper stale lock handling
"""

import atexit
import os
import sys
from typing import Optional

if sys.platform == "win32":
	import win32api
	import win32event
	import winerror
else:
	import fcntl


class SingletonInstance:
	"""Class to ensure that only one instance of basiliskLLM is running at a time.

	This class implements platform-specific locking mechanisms:
	- Windows: Uses named mutex through pywin32
	- POSIX: Uses fcntl file locking with proper stale lock handling
	- Prevents multiple instances from running simultaneously
	- Automatically releases the lock on program exit
	- Provides methods to check for existing instances and get their PIDs
	"""

	def __init__(self, file_lock: str, mutex_name: str):
		"""Initialize the SingletonInstance object.

		Args:
			file_lock: Path to the lock file (used on all platforms)
			mutex_name: Name for the mutex (Windows only)
		"""
		self.mutex_name = mutex_name
		self.lock_file_path = file_lock
		self.mutex_handle = None
		self.lock_file_handle = None
		self.is_windows = sys.platform == "win32"

		if self.is_windows:
			# Create a unique mutex name for the application
			self.mutex_name = f"Global\\{mutex_name}"
		else:
			# Ensure the lock file directory exists for POSIX systems
			os.makedirs(os.path.dirname(file_lock), exist_ok=True)

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
		"""Acquire the lock on POSIX systems using fcntl file locking.

		This method uses proper POSIX file locking with fcntl to ensure
		atomic lock acquisition. It also handles stale lock files from
		crashed processes.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		# Try to acquire the lock
		if self._try_acquire_posix_lock():
			return True

		# Lock acquisition failed, check if it's due to existing lock
		try:
			# Check if the lock holder is still alive
			existing_pid = self._get_lock_holder_pid()
			if existing_pid and self._is_process_alive(existing_pid):
				# Valid lock holder exists
				return False
			else:
				# Stale lock file, try to remove it and retry once
				self._cleanup_stale_lock()
				return self._try_acquire_posix_lock()
		except Exception:
			return False

	def _try_acquire_posix_lock(self) -> bool:
		"""Try to acquire the POSIX lock without retry logic.

		Returns:
			True if the lock was acquired, False otherwise.
		"""
		try:
			# Open the lock file for writing
			self.lock_file_handle = open(self.lock_file_path, "w")

			# Try to acquire an exclusive lock (non-blocking)
			fcntl.flock(
				self.lock_file_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB
			)

			# Write our PID to the lock file
			self.lock_file_handle.write(str(os.getpid()))
			self.lock_file_handle.flush()

			# Register cleanup on exit
			atexit.register(self.release)
			return True

		except (IOError, OSError):
			# Lock is already held by another process or other I/O error
			self._cleanup_failed_lock_attempt()
			return False
		except Exception:
			# Unexpected error
			self._cleanup_failed_lock_attempt()
			return False

	def _get_lock_holder_pid(self) -> Optional[int]:
		"""Get the PID of the current lock holder from the lock file.

		Returns:
			The PID of the lock holder, or None if it cannot be determined.
		"""
		try:
			with open(self.lock_file_path, "r") as f:
				pid_str = f.read().strip()
				if pid_str:
					return int(pid_str)
		except (IOError, OSError, ValueError):
			pass
		return None

	def _is_process_alive(self, pid: int) -> bool:
		"""Check if a process with the given PID is still alive.

		Args:
			pid: The process ID to check.

		Returns:
			True if the process is alive, False otherwise.
		"""
		# Import errno within the method to avoid import issues on Windows
		import errno

		try:
			# Send signal 0 to check if process exists
			os.kill(pid, 0)
			return True
		except OSError as e:
			if e.errno == errno.ESRCH:
				# Process doesn't exist
				return False
			elif e.errno == errno.EPERM:
				# Process exists but we don't have permission to signal it
				return True
			else:
				# Other error, assume process exists
				return True
		except Exception:
			# Unexpected error, assume process exists
			return True

	def _cleanup_failed_lock_attempt(self):
		"""Clean up resources after a failed lock acquisition attempt."""
		if self.lock_file_handle:
			try:
				self.lock_file_handle.close()
			except Exception:
				pass
			finally:
				self.lock_file_handle = None

	def _cleanup_stale_lock(self):
		"""Clean up a stale lock file."""
		try:
			if os.path.exists(self.lock_file_path):
				os.remove(self.lock_file_path)
		except Exception:
			pass
		finally:
			self._cleanup_failed_lock_attempt()

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
				# Release the file lock
				fcntl.flock(self.lock_file_handle.fileno(), fcntl.LOCK_UN)
				self.lock_file_handle.close()
			except Exception:
				# If unlocking fails, at least close the file handle
				try:
					self.lock_file_handle.close()
				except Exception:
					pass
			finally:
				self.lock_file_handle = None

		# Remove the lock file
		try:
			if os.path.exists(self.lock_file_path):
				os.remove(self.lock_file_path)
		except Exception:
			pass

	def get_existing_pid(self) -> Optional[int]:
		"""Get the PID of the existing instance, if any.

		Note: On Windows with mutex-based locking, this method cannot reliably
		determine the PID of the existing instance. It returns -1 if another
		instance is detected but the PID cannot be determined.

		Returns:
			The PID of the existing instance, or None if no instance is running.
			On Windows, returns -1 if another instance exists but PID cannot be determined.
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
			# POSIX file-based approach with proper lock checking
			if not os.path.exists(self.lock_file_path):
				return None

			try:
				# Try to read the PID from the lock file
				with open(self.lock_file_path, "r") as f:
					pid_str = f.read().strip()
					if not pid_str:
						return None

					pid = int(pid_str)

					# Check if the process is still alive
					if self._is_process_alive(pid):
						return pid
					else:
						# Process is dead, lock file is stale
						try:
							os.remove(self.lock_file_path)
						except Exception:
							pass
						return None
			except (IOError, OSError, ValueError):
				# File is corrupted or unreadable, try to remove it
				try:
					os.remove(self.lock_file_path)
				except Exception:
					pass
				return None

	def is_running(self) -> bool:
		"""Check if another instance of the application is running.

		Returns:
			True if another instance is running, False otherwise.
		"""
		return self.get_existing_pid() is not None
