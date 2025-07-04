#!/usr/bin/env python3
"""Quick test script to verify focus behavior works correctly."""

import os
import sys
import time

# Add the basilisk directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "basilisk"))

from basilisk.send_signal import send_focus_signal


def test_focus_toggle():
	"""Test that focus signals toggle the window correctly."""
	print("Testing focus toggle behavior...")

	for i in range(10):
		print(f"Sending focus signal {i + 1}/10...")
		try:
			result = send_focus_signal()
			print(f"  Signal sent: {result}")
		except Exception as e:
			print(f"  Error: {e}")
			return False

		# Wait between each signal to observe behavior
		time.sleep(3)

	print("✅ Focus toggle test completed!")
	return True


if __name__ == "__main__":
	print("=== Focus Toggle Test ===")
	print("Instructions:")
	print("1. Start basilisk manually: python -m basilisk --log-level DEBUG")
	print("2. Observe window behavior during this test")
	print("3. Window should alternate between visible and hidden")
	print()

	input("Press Enter when basilisk is running and ready...")

	success = test_focus_toggle()

	print("\nTest summary:")
	if success:
		print("✅ Test completed successfully")
		print(
			"📝 Check that the window toggled correctly between visible/hidden"
		)
	else:
		print("❌ Test failed")

	sys.exit(0 if success else 1)
