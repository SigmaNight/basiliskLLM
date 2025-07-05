#!/usr/bin/env python3
"""Test script to verify the improved POSIX singleton behavior.

This script demonstrates the enhanced singleton instance mechanism with:
- Proper fcntl file locking on POSIX systems
- Stale lock file cleanup
- Process aliveness checking
- Atomic lock acquisition
"""

import os
import sys
import tempfile

# Add the basilisk module to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from basilisk.singleton_instance import SingletonInstance


def test_basic_functionality():
	"""Test basic singleton functionality."""
	print("Testing basic singleton functionality...")

	test_lock_file = os.path.join(
		tempfile.gettempdir(), "test_basilisk_posix.lock"
	)
	test_mutex_name = "test_basilisk_posix"

	# Clean up any existing lock file
	if os.path.exists(test_lock_file):
		os.remove(test_lock_file)

	instance = SingletonInstance(test_lock_file, test_mutex_name)

	# Should be able to acquire the lock
	assert instance.acquire(), "Failed to acquire lock"
	print("✓ Successfully acquired lock")

	# Should be able to get our own PID (on POSIX systems)
	if not instance.is_windows:
		existing_pid = instance.get_existing_pid()
		assert existing_pid == os.getpid(), (
			f"Expected PID {os.getpid()}, got {existing_pid}"
		)
		print(f"✓ Lock holder PID correctly reported as {existing_pid}")

	# Should be able to release the lock
	instance.release()
	print("✓ Successfully released lock")

	# Lock file should be cleaned up
	if not instance.is_windows:
		assert not os.path.exists(test_lock_file), (
			"Lock file was not cleaned up"
		)
		print("✓ Lock file properly cleaned up")


def test_stale_lock_cleanup():
	"""Test that stale lock files are properly cleaned up."""
	if sys.platform == "win32":
		print("Skipping stale lock cleanup test on Windows")
		return

	print("\nTesting stale lock cleanup...")

	test_lock_file = os.path.join(
		tempfile.gettempdir(), "test_basilisk_stale.lock"
	)
	test_mutex_name = "test_basilisk_stale"

	# Clean up any existing lock file
	if os.path.exists(test_lock_file):
		os.remove(test_lock_file)

	# Create a stale lock file with a non-existent PID
	fake_pid = 999999  # Very unlikely to exist
	with open(test_lock_file, "w") as f:
		f.write(str(fake_pid))

	instance = SingletonInstance(test_lock_file, test_mutex_name)

	# get_existing_pid should clean up the stale lock and return None
	existing_pid = instance.get_existing_pid()
	assert existing_pid is None, (
		f"Expected None for stale lock, got {existing_pid}"
	)
	print("✓ Stale lock properly detected and cleaned up")

	# Lock file should be removed
	assert not os.path.exists(test_lock_file), "Stale lock file was not removed"
	print("✓ Stale lock file properly removed")

	# Should now be able to acquire the lock
	assert instance.acquire(), "Failed to acquire lock after stale cleanup"
	print("✓ Successfully acquired lock after stale cleanup")

	instance.release()


def test_multiple_instances():
	"""Test that multiple instances cannot acquire the same lock."""
	print("\nTesting multiple instance prevention...")

	test_lock_file = os.path.join(
		tempfile.gettempdir(), "test_basilisk_multi.lock"
	)
	test_mutex_name = "test_basilisk_multi"

	# Clean up any existing lock file
	if os.path.exists(test_lock_file):
		os.remove(test_lock_file)

	instance1 = SingletonInstance(test_lock_file, test_mutex_name)
	instance2 = SingletonInstance(test_lock_file, test_mutex_name)

	# First instance should acquire successfully
	assert instance1.acquire(), "First instance failed to acquire lock"
	print("✓ First instance successfully acquired lock")

	# Second instance should fail to acquire
	assert not instance2.acquire(), "Second instance should not acquire lock"
	print("✓ Second instance correctly failed to acquire lock")

	# First instance releases
	instance1.release()
	print("✓ First instance released lock")

	# Second instance can now acquire
	assert instance2.acquire(), (
		"Second instance failed to acquire after first released"
	)
	print("✓ Second instance successfully acquired lock after first released")

	instance2.release()


def main():
	"""Run all tests."""
	print("Testing improved POSIX singleton mechanism...")
	print(f"Platform: {sys.platform}")
	print(f"Python version: {sys.version}")
	print()

	try:
		test_basic_functionality()
		test_stale_lock_cleanup()
		test_multiple_instances()

		print(
			"\n✅ All tests passed! The improved singleton mechanism is working correctly."
		)

	except Exception as e:
		print(f"\n❌ Test failed: {e}")
		import traceback

		traceback.print_exc()
		sys.exit(1)


if __name__ == "__main__":
	main()
