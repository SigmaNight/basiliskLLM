#!/usr/bin/env python3
"""Debug script to test window focus and restoration issues."""

import os
import subprocess
import sys
import time

# Add the basilisk directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "basilisk"))

from basilisk.send_signal import SignalType, send_signal
from basilisk.singleton_instance import SingletonInstance


def test_window_focus_issue():
	"""Test to reproduce the window focus issue."""
	print("Testing window focus and restoration...")

	# Test 1: Check if first instance is running
	print("\n1. Checking if first instance is running...")
	singleton = SingletonInstance("basilisk_test")
	if singleton.is_running():
		print("   ✓ First instance is running")
	else:
		print("   ✗ First instance is not running")
		return False

	# Test 2: Send focus signal
	print("\n2. Sending focus signal...")
	try:
		result = send_signal(SignalType.FOCUS)
		print(f"   Signal sent, result: {result}")
		time.sleep(2)  # Give time for window to respond
	except Exception as e:
		print(f"   ✗ Failed to send focus signal: {e}")
		return False

	# Test 3: Test multiple focus signals
	print("\n3. Testing multiple focus signals...")
	for i in range(3):
		print(f"   Sending focus signal {i + 1}/3...")
		try:
			result = send_signal(SignalType.FOCUS)
			print(f"   Signal {i + 1} sent, result: {result}")
			time.sleep(1)
		except Exception as e:
			print(f"   ✗ Failed to send focus signal {i + 1}: {e}")

	return True


def test_multiple_instances():
	"""Test multiple instance launching."""
	print("\n4. Testing multiple instance launches...")

	# Try to start multiple instances
	instances = []
	for i in range(3):
		print(f"   Starting instance {i + 1}...")
		try:
			# Start basilisk with a small delay
			proc = subprocess.Popen(
				[sys.executable, "-m", "basilisk", "--log-level", "DEBUG"],
				cwd=os.path.dirname(__file__),
			)
			instances.append(proc)
			time.sleep(0.5)  # Small delay between launches
		except Exception as e:
			print(f"   ✗ Failed to start instance {i + 1}: {e}")

	# Wait a bit for all instances to start
	time.sleep(5)

	# Check which instances are still running
	running_count = 0
	for i, proc in enumerate(instances):
		if proc.poll() is None:
			running_count += 1
			print(f"   Instance {i + 1}: still running")
		else:
			print(
				f"   Instance {i + 1}: terminated with code {proc.returncode}"
			)

	print(f"   Total running instances: {running_count}")

	# Clean up
	for proc in instances:
		if proc.poll() is None:
			proc.terminate()
			proc.wait()

	return running_count == 1  # Should only have one instance running


def main():
	"""Main test function."""
	print("=== BasiliskLLM Focus and Restoration Debug Test ===")

	# Check if basilisk is already running
	singleton = SingletonInstance("basilisk_test")
	if not singleton.is_running():
		print("No basilisk instance is running. Please start basilisk first.")
		return False

	# Run focus tests
	if not test_window_focus_issue():
		print("\n❌ Window focus test failed")
		return False

	# Run multiple instance test
	if not test_multiple_instances():
		print("\n❌ Multiple instance test failed")
		return False

	print("\n✅ All tests completed successfully!")
	return True


if __name__ == "__main__":
	success = main()
	sys.exit(0 if success else 1)
