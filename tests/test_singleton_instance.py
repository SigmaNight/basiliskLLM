"""Tests for the SingletonInstance module.

This module contains unit tests for the SingletonInstance implementation which ensures
that only one instance of the application runs at a time using platform-specific
locking mechanisms (Windows mutex or POSIX file locking).
"""

import os
import sys
import tempfile
import uuid
from unittest import mock

import pytest

# Patch the constants to use unique names for testing
TEST_APP_NAME = f"basiliskLLM_test_{uuid.uuid4().hex[:8]}"
TEST_LOCK_PATH = os.path.join(
	tempfile.gettempdir(), f"basilisk_test_{uuid.uuid4().hex[:8]}", "app.lock"
)

# Apply the patches before importing the module
with mock.patch("basilisk.consts.APP_NAME", TEST_APP_NAME):
	with mock.patch("basilisk.consts.FILE_LOCK_PATH", TEST_LOCK_PATH):
		from basilisk.singleton_instance import SingletonInstance


@pytest.fixture
def test_lock_file():
	"""Test lock file path fixture."""
	return TEST_LOCK_PATH


@pytest.fixture
def cleanup_lock_file():
	"""Clean up any remaining lock files and directories after test."""
	yield
	# Clean up any remaining lock files
	if os.path.exists(TEST_LOCK_PATH):
		try:
			os.remove(TEST_LOCK_PATH)
		except Exception:
			pass
	# Clean up the test directory
	test_dir = os.path.dirname(TEST_LOCK_PATH)
	if os.path.exists(test_dir):
		try:
			os.rmdir(test_dir)
		except Exception:
			pass


class TestSingletonInstanceCore:
	"""Test core functionality of SingletonInstance."""

	def test_singleton_acquire_release(self, cleanup_lock_file):
		"""Test basic acquire and release functionality."""
		instance = SingletonInstance()

		# Should be able to acquire the lock
		assert instance.acquire()

		# Should be able to release the lock
		instance.release()

	def test_singleton_multiple_instances(self, cleanup_lock_file):
		"""Test that multiple instances cannot acquire the same lock."""
		instance1 = SingletonInstance()
		instance2 = SingletonInstance()

		# First instance should acquire successfully
		assert instance1.acquire()

		# Second instance should fail to acquire
		assert not instance2.acquire()

		# Clean up
		instance1.release()
		instance2.release()

	def test_singleton_acquire_after_release(self, cleanup_lock_file):
		"""Test that a lock can be acquired after being released."""
		instance1 = SingletonInstance()
		instance2 = SingletonInstance()

		# First instance acquires
		assert instance1.acquire()

		# Second instance cannot acquire
		assert not instance2.acquire()

		# First instance releases
		instance1.release()

		# Second instance can now acquire
		assert instance2.acquire()

		# Clean up
		instance2.release()

	def test_multiple_release_calls(self, cleanup_lock_file):
		"""Test that multiple release calls don't cause errors."""
		instance = SingletonInstance()

		# Acquire the lock
		assert instance.acquire()

		# Release multiple times should not cause errors
		instance.release()
		instance.release()
		instance.release()

	def test_release_without_acquire(self, cleanup_lock_file):
		"""Test that releasing without acquiring doesn't cause errors."""
		instance = SingletonInstance()

		# Release without acquiring should not cause errors
		instance.release()

	def test_is_running_method(self, cleanup_lock_file):
		"""Test the is_running method."""
		instance1 = SingletonInstance()
		instance2 = SingletonInstance()

		# Initially no instance is running
		assert not instance1.is_running()

		# After acquiring, should detect running instance
		instance1.acquire()
		assert instance2.is_running()

		# After releasing, should not detect running instance
		instance1.release()
		assert not instance2.is_running()


class TestSingletonInstancePlatformSpecific:
	"""Test platform-specific functionality of SingletonInstance."""

	@pytest.mark.skipif(sys.platform != "win32", reason="Windows-specific test")
	def test_get_existing_pid_windows(self, cleanup_lock_file):
		"""Test get_existing_pid on Windows (returns -1 when mutex exists)."""
		instance1 = SingletonInstance()
		instance2 = SingletonInstance()

		# No existing instance
		assert instance1.get_existing_pid() is None

		# First instance acquires
		assert instance1.acquire()

		# Second instance should detect existing instance
		existing_pid = instance2.get_existing_pid()
		assert existing_pid == -1  # Windows mutex returns -1

		# Clean up
		instance1.release()

	@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific test")
	def test_get_existing_pid_posix(self, cleanup_lock_file):
		"""Test get_existing_pid behavior with POSIX file-based locking."""
		instance = SingletonInstance()

		# No existing instance
		assert instance.get_existing_pid() is None

		# Acquire lock and verify PID is returned
		instance.acquire()
		existing_pid = instance.get_existing_pid()
		assert existing_pid == os.getpid()

		# Clean up
		instance.release()

	@pytest.mark.skipif(sys.platform == "win32", reason="POSIX-specific test")
	def test_stale_lock_cleanup(self, cleanup_lock_file):
		"""Test that stale lock files are cleaned up properly."""
		instance = SingletonInstance()

		# Create a stale lock file with a non-existent PID
		fake_pid = 999999  # Very unlikely to exist
		os.makedirs(os.path.dirname(instance.lock_file_path), exist_ok=True)
		with open(instance.lock_file_path, "w") as f:
			f.write(str(fake_pid))

		# get_existing_pid should clean up the stale lock and return None
		existing_pid = instance.get_existing_pid()
		assert existing_pid is None

		# Lock file should be removed
		assert not os.path.exists(instance.lock_file_path)

	def test_platform_detection(self, cleanup_lock_file):
		"""Test that the class correctly uses platform-specific implementation."""
		instance = SingletonInstance()

		# Test that the correct implementation is loaded
		if sys.platform == "win32":
			assert hasattr(instance, "mutex_name")
			assert not hasattr(instance, "lock_file_path")
		else:
			assert hasattr(instance, "lock_file_path")
			assert not hasattr(instance, "mutex_name")


class TestSingletonInstanceEdgeCases:
	"""Test edge cases and error conditions for SingletonInstance."""

	def test_concurrent_access_simulation(self, cleanup_lock_file):
		"""Test concurrent access simulation by rapidly creating instances."""
		instances = []
		acquired_count = 0

		# Create multiple instances rapidly
		for i in range(5):
			instance = SingletonInstance()
			instances.append(instance)
			if instance.acquire():
				acquired_count += 1

		# Only one instance should have acquired the lock
		assert acquired_count == 1

		# Clean up all instances
		for instance in instances:
			instance.release()

	def test_atexit_registration(self, cleanup_lock_file):
		"""Test that release is properly registered with atexit."""
		instance = SingletonInstance()

		# Acquire the lock
		assert instance.acquire()

		# The register_release_on_exit should have been called
		# We can't directly test atexit registration, but we can ensure
		# that the method exists and doesn't raise an exception
		assert hasattr(instance, "register_release_on_exit")

		# Clean up
		instance.release()


class TestSingletonInstanceIntegration:
	"""Integration tests combining functionality from all singleton test files."""

	def test_comprehensive_singleton_workflow(self, cleanup_lock_file):
		"""Test comprehensive singleton workflow covering all use cases."""
		instance1 = SingletonInstance()
		instance2 = SingletonInstance()

		# Phase 1: Initial acquisition
		assert instance1.acquire(), "First instance should acquire lock"
		assert not instance2.acquire(), (
			"Second instance should not acquire lock"
		)

		# Phase 2: Check existing instance detection
		existing_pid = instance2.get_existing_pid()
		if sys.platform == "win32":
			assert existing_pid == -1, (
				"Windows should return -1 for existing instance"
			)
		else:
			assert existing_pid == os.getpid(), (
				"POSIX should return current PID"
			)

		# Phase 3: Test is_running method
		assert instance2.is_running(), "Should detect running instance"

		# Phase 4: Release and re-acquire
		instance1.release()
		assert not instance2.is_running(), (
			"Should not detect running instance after release"
		)
		assert instance2.acquire(), (
			"Second instance should acquire after first releases"
		)

		# Cleanup
		instance2.release()

	@pytest.mark.skipif(
		sys.platform == "win32", reason="POSIX-specific comprehensive test"
	)
	def test_posix_file_locking_comprehensive(self, cleanup_lock_file):
		"""Test comprehensive POSIX file locking behavior."""
		instance = SingletonInstance()

		# Test 1: Basic file locking
		assert instance.acquire(), "Should acquire POSIX lock"
		assert os.path.exists(instance.lock_file_path), "Lock file should exist"

		# Test 2: Verify PID in lock file
		with open(instance.lock_file_path, "r") as f:
			pid_in_file = int(f.read().strip())
		assert pid_in_file == os.getpid(), (
			"Lock file should contain current PID"
		)

		# Test 3: Verify lock is active
		existing_pid = instance.get_existing_pid()
		assert existing_pid == os.getpid(), (
			"Should return current PID for active lock"
		)

		# Test 4: Release and cleanup
		instance.release()
		assert not os.path.exists(instance.lock_file_path), (
			"Lock file should be removed after release"
		)

	@pytest.mark.skipif(
		sys.platform == "win32", reason="POSIX-specific stale lock test"
	)
	def test_stale_lock_comprehensive_cleanup(self, cleanup_lock_file):
		"""Test comprehensive stale lock cleanup behavior."""
		instance = SingletonInstance()

		# Create directory structure if needed
		os.makedirs(os.path.dirname(instance.lock_file_path), exist_ok=True)

		# Test 1: Create stale lock with non-existent PID
		fake_pid = 999999
		with open(instance.lock_file_path, "w") as f:
			f.write(str(fake_pid))

		# Test 2: Verify stale lock is detected and cleaned
		existing_pid = instance.get_existing_pid()
		assert existing_pid is None, "Stale lock should be detected and cleaned"
		assert not os.path.exists(instance.lock_file_path), (
			"Stale lock file should be removed"
		)

		# Test 3: Should be able to acquire after stale cleanup
		assert instance.acquire(), "Should acquire lock after stale cleanup"

		# Cleanup
		instance.release()

	def test_rapid_acquisition_attempts(self, cleanup_lock_file):
		"""Test rapid acquisition attempts to verify thread safety."""
		instances = []
		acquisition_results = []

		# Create multiple instances and try to acquire rapidly
		for i in range(10):
			instance = SingletonInstance()
			instances.append(instance)
			result = instance.acquire()
			acquisition_results.append(result)

		# Only one should have succeeded
		successful_acquisitions = sum(acquisition_results)
		assert successful_acquisitions == 1, (
			"Only one instance should acquire lock"
		)

		# Clean up all instances
		for instance in instances:
			instance.release()

	def test_lock_persistence_across_instances(self, cleanup_lock_file):
		"""Test that lock persists across different instance objects."""
		# Create and acquire with first instance
		instance1 = SingletonInstance()
		assert instance1.acquire()

		# Create new instance and test lock is still held
		instance2 = SingletonInstance()
		assert not instance2.acquire()
		assert instance2.is_running()

		# Release first instance
		instance1.release()

		# New instance should now be able to acquire
		assert not instance2.is_running()
		assert instance2.acquire()

		# Cleanup
		instance2.release()

	def test_error_handling_robustness(self, cleanup_lock_file):
		"""Test error handling and robustness of singleton implementation."""
		instance = SingletonInstance()

		# Test multiple releases without errors
		instance.release()  # Should not raise exception
		instance.release()  # Should not raise exception

		# Test acquire/release cycle multiple times
		for i in range(3):
			assert instance.acquire(), f"Acquisition {i + 1} should succeed"
			instance.release()

		# Test that after all operations, system is clean
		assert not instance.is_running()

	@pytest.mark.skipif(
		sys.platform == "win32", reason="POSIX-specific directory test"
	)
	def test_lock_file_directory_creation(self, cleanup_lock_file):
		"""Test that lock file directory is created if it doesn't exist."""
		instance = SingletonInstance()

		# Remove the directory if it exists
		lock_dir = os.path.dirname(instance.lock_file_path)
		if os.path.exists(lock_dir):
			import shutil

			shutil.rmtree(lock_dir)

		# Directory should be created when acquiring lock
		assert instance.acquire()
		assert os.path.exists(lock_dir), "Lock directory should be created"
		assert os.path.exists(instance.lock_file_path), (
			"Lock file should be created"
		)

		# Cleanup
		instance.release()

	def test_concurrent_instance_simulation(self, cleanup_lock_file):
		"""Simulate concurrent instance creation and acquisition."""
		# This simulates what would happen if multiple processes
		# tried to start the application simultaneously

		master_instance = SingletonInstance()
		slave_instances = []

		# Master acquires first
		assert master_instance.acquire()

		# Create multiple slave instances
		for i in range(5):
			slave = SingletonInstance()
			slave_instances.append(slave)

			# Each slave should fail to acquire
			assert not slave.acquire(), f"Slave {i} should not acquire lock"
			assert slave.is_running(), (
				f"Slave {i} should detect running instance"
			)

		# Master releases
		master_instance.release()

		# Now one slave should be able to acquire
		acquisition_count = 0
		for slave in slave_instances:
			if slave.acquire():
				acquisition_count += 1

		assert acquisition_count == 1, (
			"Exactly one slave should acquire after master release"
		)

		# Cleanup all slaves
		for slave in slave_instances:
			slave.release()
