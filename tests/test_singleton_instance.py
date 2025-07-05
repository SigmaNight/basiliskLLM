"""Tests for the SingletonInstance class.

This module contains unit tests for the SingletonInstance class which ensures
that only one instance of the application runs at a time using Windows mutex
or file-based locking on other platforms.
"""

import os
import sys
import tempfile
import unittest

from basilisk.singleton_instance import SingletonInstance


class TestSingletonInstance(unittest.TestCase):
	"""Test cases for the SingletonInstance class."""

	def setUp(self):
		"""Set up test fixtures."""
		self.test_mutex_name = "test_basilisk_singleton"
		self.test_lock_file = os.path.join(
			tempfile.gettempdir(), "test_basilisk.lock"
		)

	def tearDown(self):
		"""Clean up test fixtures."""
		# Clean up any remaining lock files
		if os.path.exists(self.test_lock_file):
			try:
				os.remove(self.test_lock_file)
			except Exception:
				pass

	def test_singleton_acquire_release(self):
		"""Test basic acquire and release functionality."""
		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# Should be able to acquire the lock
		self.assertTrue(instance.acquire())

		# Should be able to release the lock
		instance.release()

	def test_singleton_multiple_instances(self):
		"""Test that multiple instances cannot acquire the same lock."""
		instance1 = SingletonInstance(self.test_lock_file, self.test_mutex_name)
		instance2 = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# First instance should acquire successfully
		self.assertTrue(instance1.acquire())

		# Second instance should fail to acquire
		self.assertFalse(instance2.acquire())

		# Clean up
		instance1.release()
		instance2.release()

	def test_singleton_acquire_after_release(self):
		"""Test that a lock can be acquired after being released."""
		instance1 = SingletonInstance(self.test_lock_file, self.test_mutex_name)
		instance2 = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# First instance acquires
		self.assertTrue(instance1.acquire())

		# Second instance cannot acquire
		self.assertFalse(instance2.acquire())

		# First instance releases
		instance1.release()

		# Second instance can now acquire
		self.assertTrue(instance2.acquire())

		# Clean up
		instance2.release()

	def test_get_existing_pid_windows(self):
		"""Test get_existing_pid on Windows (returns -1 when mutex exists)."""
		if sys.platform != "win32":
			self.skipTest("Test only runs on Windows")

		instance1 = SingletonInstance(self.test_lock_file, self.test_mutex_name)
		instance2 = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# No existing instance
		self.assertIsNone(instance1.get_existing_pid())

		# First instance acquires
		self.assertTrue(instance1.acquire())

		# Second instance should detect existing instance
		existing_pid = instance2.get_existing_pid()
		self.assertEqual(existing_pid, -1)  # Windows mutex returns -1

		# Clean up
		instance1.release()

	def test_get_existing_pid_file_based(self):
		"""Test get_existing_pid behavior with file-based locking."""
		# This test works on POSIX systems
		if sys.platform == "win32":
			self.skipTest("File-based PID reading not primary on Windows")

		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# No existing instance
		self.assertIsNone(instance.get_existing_pid())

		# Manually create a lock file with a PID
		with open(self.test_lock_file, "w") as f:
			f.write(str(os.getpid()))

		# Should be able to read the PID (but process is alive, so it should return the PID)
		existing_pid = instance.get_existing_pid()
		self.assertEqual(existing_pid, os.getpid())

		# Clean up
		if os.path.exists(self.test_lock_file):
			os.remove(self.test_lock_file)

	def test_stale_lock_cleanup(self):
		"""Test that stale lock files are cleaned up properly."""
		if sys.platform == "win32":
			self.skipTest("Test only relevant for POSIX systems")

		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# Create a stale lock file with a non-existent PID
		fake_pid = 999999  # Very unlikely to exist
		with open(self.test_lock_file, "w") as f:
			f.write(str(fake_pid))

		# get_existing_pid should clean up the stale lock and return None
		existing_pid = instance.get_existing_pid()
		self.assertIsNone(existing_pid)

		# Lock file should be removed
		self.assertFalse(os.path.exists(self.test_lock_file))

	def test_platform_detection(self):
		"""Test that the class correctly detects the platform."""
		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		if sys.platform == "win32":
			self.assertTrue(instance.is_windows)
		else:
			self.assertFalse(instance.is_windows)

	def test_multiple_release_calls(self):
		"""Test that multiple release calls don't cause errors."""
		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# Acquire the lock
		self.assertTrue(instance.acquire())

		# Release multiple times should not cause errors
		instance.release()
		instance.release()
		instance.release()

	def test_release_without_acquire(self):
		"""Test that releasing without acquiring doesn't cause errors."""
		instance = SingletonInstance(self.test_lock_file, self.test_mutex_name)

		# Release without acquiring should not cause errors
		instance.release()


if __name__ == "__main__":
	unittest.main()
