"""Tests for the Windows IPC mechanism.

This module contains unit tests for the Windows named pipe communication
system used for inter-process communication in the application.
"""

import sys
import time
import unittest

from basilisk.windows_ipc import (
	WindowsSignalReceiver,
	WindowsSignalSender,
	WindowsSignalType,
	init_windows_signal_receiver,
)


class TestWindowsIPC(unittest.TestCase):
	"""Test cases for the Windows IPC mechanism."""

	def setUp(self):
		"""Set up test fixtures."""
		self.test_pipe_name = "test_basilisk_ipc"
		self.received_signals = []

	def tearDown(self):
		"""Clean up test fixtures."""
		self.received_signals.clear()

	def test_signal_type_enum(self):
		"""Test that WindowsSignalType enum has correct values."""
		self.assertEqual(WindowsSignalType.FOCUS.value, "focus")
		self.assertEqual(WindowsSignalType.OPEN_BSKC.value, "open_bskc")
		self.assertEqual(WindowsSignalType.SHUTDOWN.value, "shutdown")

	def test_signal_receiver_initialization(self):
		"""Test WindowsSignalReceiver initialization."""
		callbacks = {"on_focus": lambda x: None}
		receiver = WindowsSignalReceiver(self.test_pipe_name, callbacks)

		self.assertEqual(
			receiver.pipe_name, f"\\\\.\\pipe\\{self.test_pipe_name}"
		)
		self.assertEqual(receiver.callbacks, callbacks)
		self.assertFalse(receiver.running)
		self.assertIsNone(receiver.thread)

	def test_signal_sender_initialization(self):
		"""Test WindowsSignalSender initialization."""
		sender = WindowsSignalSender(self.test_pipe_name)
		self.assertEqual(
			sender.pipe_name, f"\\\\.\\pipe\\{self.test_pipe_name}"
		)

	@unittest.skipIf(
		sys.platform != "win32", "Windows IPC only works on Windows"
	)
	def test_focus_signal_integration(self):
		"""Test sending and receiving focus signals."""

		def on_focus(data):
			self.received_signals.append(("focus", data))

		receiver = WindowsSignalReceiver(
			self.test_pipe_name, {"on_focus": on_focus}
		)

		try:
			receiver.start()
			time.sleep(0.5)  # Give receiver time to start

			sender = WindowsSignalSender(self.test_pipe_name)
			success = sender.send_focus_signal()

			self.assertTrue(success)
			time.sleep(0.5)  # Give signal time to be processed

			self.assertEqual(len(self.received_signals), 1)
			signal_type, data = self.received_signals[0]
			self.assertEqual(signal_type, "focus")
			self.assertIn("timestamp", data)

		finally:
			receiver.stop()

	@unittest.skipIf(
		sys.platform != "win32", "Windows IPC only works on Windows"
	)
	def test_open_bskc_signal_integration(self):
		"""Test sending and receiving open BSKC signals."""

		def on_open_bskc(data):
			self.received_signals.append(("open_bskc", data))

		receiver = WindowsSignalReceiver(
			self.test_pipe_name, {"on_open_bskc": on_open_bskc}
		)

		try:
			receiver.start()
			time.sleep(0.5)  # Give receiver time to start

			sender = WindowsSignalSender(self.test_pipe_name)
			test_file = "test_conversation.bskc"
			success = sender.send_open_bskc_signal(test_file)

			self.assertTrue(success)
			time.sleep(0.5)  # Give signal time to be processed

			self.assertEqual(len(self.received_signals), 1)
			signal_type, data = self.received_signals[0]
			self.assertEqual(signal_type, "open_bskc")
			self.assertEqual(data["file_path"], test_file)

		finally:
			receiver.stop()

	@unittest.skipIf(
		sys.platform != "win32", "Windows IPC only works on Windows"
	)
	def test_multiple_signals(self):
		"""Test sending multiple signals in sequence."""

		def on_focus(data):
			self.received_signals.append(("focus", data))

		def on_open_bskc(data):
			self.received_signals.append(("open_bskc", data))

		receiver = WindowsSignalReceiver(
			self.test_pipe_name,
			{"on_focus": on_focus, "on_open_bskc": on_open_bskc},
		)

		try:
			receiver.start()
			time.sleep(0.5)  # Give receiver time to start

			sender = WindowsSignalSender(self.test_pipe_name)

			# Send focus signal
			success1 = sender.send_focus_signal()
			time.sleep(0.3)

			# Send open BSKC signal
			success2 = sender.send_open_bskc_signal("test.bskc")
			time.sleep(0.3)

			self.assertTrue(success1)
			self.assertTrue(success2)

			# Should have received both signals
			self.assertEqual(len(self.received_signals), 2)

		finally:
			receiver.stop()

	def test_init_windows_signal_receiver(self):
		"""Test the init_windows_signal_receiver function."""

		def dummy_callback(data):
			pass

		if sys.platform == "win32":
			receiver = init_windows_signal_receiver(
				self.test_pipe_name,
				send_focus=dummy_callback,
				open_bskc=dummy_callback,
			)

			self.assertIsNotNone(receiver)
			self.assertIsInstance(receiver, WindowsSignalReceiver)

			# Clean up
			receiver.stop()
		else:
			# Should return None on non-Windows platforms
			receiver = init_windows_signal_receiver(
				self.test_pipe_name, send_focus=dummy_callback
			)
			self.assertIsNone(receiver)

	def test_callback_name_mapping(self):
		"""Test that callback names are correctly mapped."""

		def dummy_callback(data):
			pass

		if sys.platform == "win32":
			receiver = init_windows_signal_receiver(
				self.test_pipe_name,
				send_focus=dummy_callback,
				open_bskc=dummy_callback,
			)

			self.assertIsNotNone(receiver)
			self.assertIn("on_focus", receiver.callbacks)
			self.assertIn("on_open_bskc", receiver.callbacks)

			# Clean up
			receiver.stop()

	def test_receiver_stop_without_start(self):
		"""Test that stopping a receiver without starting doesn't cause errors."""
		receiver = WindowsSignalReceiver(self.test_pipe_name, {})

		# This should not raise an exception
		receiver.stop()


if __name__ == "__main__":
	unittest.main()
