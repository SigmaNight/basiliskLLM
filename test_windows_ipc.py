#!/usr/bin/env python3
"""Test script for the Windows IPC mechanism.

This script tests the Windows named pipe communication between application instances.
"""

import sys
import time

from basilisk.windows_ipc import WindowsSignalReceiver, WindowsSignalSender


def test_callback_focus(data):
	"""Test callback for focus signals."""
	print(f"✓ Focus signal received: {data}")


def test_callback_open_bskc(data):
	"""Test callback for open BSKC signals."""
	print(f"✓ Open BSKC signal received: {data}")


def test_windows_ipc():
	"""Test the Windows IPC mechanism."""
	if sys.platform != "win32":
		print("❌ Test skipped: Windows IPC only works on Windows")
		return

	print("Testing Windows IPC mechanism...")

	# Create receiver with callbacks
	receiver = WindowsSignalReceiver(
		"test_basilisk_ipc",
		{
			"on_focus": test_callback_focus,
			"on_open_bskc": test_callback_open_bskc,
		},
	)

	try:
		# Start the receiver
		receiver.start()
		print("✓ Signal receiver started")

		# Give the receiver time to initialize
		time.sleep(1)

		# Create sender
		sender = WindowsSignalSender("test_basilisk_ipc")

		# Test focus signal
		print("Sending focus signal...")
		if sender.send_focus_signal():
			print("✓ Focus signal sent successfully")
		else:
			print("❌ Failed to send focus signal")

		# Test open BSKC signal
		print("Sending open BSKC signal...")
		if sender.send_open_bskc_signal("test_file.bskc"):
			print("✓ Open BSKC signal sent successfully")
		else:
			print("❌ Failed to send open BSKC signal")

		# Give time for signals to be processed
		time.sleep(2)

	finally:
		# Stop the receiver
		receiver.stop()
		print("✓ Signal receiver stopped")

	print("Test completed.")


if __name__ == "__main__":
	test_windows_ipc()
