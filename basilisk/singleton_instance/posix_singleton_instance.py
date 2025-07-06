"""Module to ensure that only one instance of basiliskLLM is running at a time.

This module implements platform-specific locking mechanisms to prevent
multiple instances of the application from running simultaneously:
- POSIX: Uses fcntl file locking with proper stale lock handling
"""

import errno
import fcntl
import os

from basilisk.consts import FILE_LOCK_PATH

from .abstract_singleton_instance import AbstractSingletonInstance


class PosixSingletonInstance(AbstractSingletonInstance):
	"""Class to ensure that only one instance of basiliskLLM is running at a time.

	This class implements platform-specific locking mechanisms:
	- POSIX: Uses fcntl file locking with proper stale lock handling
	- Prevents multiple instances from running simultaneously
	- Automatically releases the lock on program exit
	- Provides methods to check for existing instances and get their PIDs
	"""

	def __init__(self):
		"""Initialize the SingletonInstance object.

		Args:
			file_lock: Path to the lock file (used on posix platforms)
		"""
		super().__init__()
		self.lock_file_path = FILE_LOCK_PATH
		self.lock_file_handle = None
		os.makedirs(os.path.dirname(self.lock_file_path), exist_ok=True)

	def acquire(self) -> bool:
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
			self.register_release_on_exit()
			return True

		except (IOError, OSError):
			# Lock is already held by another process or other I/O error
			self._cleanup_failed_lock_attempt()
			return False
		except Exception:
			# Unexpected error
			self._cleanup_failed_lock_attempt()
			return False

	def _get_lock_holder_pid(self) -> int | None:
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

	def release(self) -> None:
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

	def get_existing_pid(self) -> int | None:
		"""Get the PID of the existing instance, if any.

		Returns:
			The PID of the existing instance, or None if no instance is running.
		"""
		# POSIX file-based approach with proper lock checking
		if not os.path.exists(self.lock_file_path):
			return None

		pid = self._get_lock_holder_pid()
		if pid is None:
			return None

		# Check if the process is still alive
		if self._is_process_alive(pid):
			return pid
		else:
			return None
