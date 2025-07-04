#!/usr/bin/env python3
"""Simple test script to verify window focus behavior."""

import os
import sys
import time

# Add the basilisk directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "basilisk"))

from basilisk.send_signal import send_focus_signal
from basilisk.singleton_instance import SingletonInstance


def main():
	"""Test the window focus behavior."""
	print("Testing window focus behavior...")

	# Check if basilisk is running
	singleton = SingletonInstance("basilisk_test")
	if not singleton.is_running():
		print("No basilisk instance is running. Please start basilisk first.")
		return False

	print("Basilisk is running. Testing focus signals...")

	# Test sequence: send multiple focus signals
	for i in range(5):
		print(f"Sending focus signal {i + 1}/5...")
		try:
			result = send_focus_signal()
			print(f"Signal {i + 1} sent successfully: {result}")
		except Exception as e:
			print(f"Failed to send signal {i + 1}: {e}")
			return False

		# Wait between signals
		time.sleep(2)

	print("All focus signals sent successfully!")
	print("Please check if the window is properly focused with NVDA.")
	return True


if __name__ == "__main__":
	success = main()
	sys.exit(0 if success else 1)
