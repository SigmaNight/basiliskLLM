#!/usr/bin/env python3
"""Test script for the refactored SingletonInstance class.

This script tests the singleton functionality with Windows mutex-based locking.
"""

from basilisk.singleton_instance import SingletonInstance


def test_singleton():
	"""Test the singleton instance functionality."""
	print("Testing SingletonInstance with Windows mutex...")

	# Use a test mutex name
	test_mutex_name = "basilisk_test_mutex"

	# Create first instance
	instance1 = SingletonInstance(test_mutex_name)
	print("Attempting to acquire lock with instance1...")

	if instance1.acquire():
		print("✓ Instance1 successfully acquired the lock")

		# Try to create a second instance
		instance2 = SingletonInstance(test_mutex_name)
		print("Attempting to acquire lock with instance2...")

		if not instance2.acquire():
			print("✓ Instance2 correctly failed to acquire the lock")

			# Check existing instance
			existing_pid = instance2.get_existing_pid()
			if existing_pid:
				if existing_pid == -1:
					print("✓ Detected existing instance (Windows mutex)")
				else:
					print(
						f"✓ Detected existing instance with PID: {existing_pid}"
					)
			else:
				print("✗ Failed to detect existing instance")
		else:
			print("✗ Instance2 incorrectly acquired the lock")

		# Release the first instance
		print("Releasing instance1...")
		instance1.release()

		# Now try to acquire with instance2
		print("Attempting to acquire lock with instance2 after release...")
		if instance2.acquire():
			print("✓ Instance2 successfully acquired the lock after release")
			instance2.release()
		else:
			print("✗ Instance2 failed to acquire the lock after release")

	else:
		print("✗ Instance1 failed to acquire the lock")

	print("Test completed.")


if __name__ == "__main__":
	test_singleton()
