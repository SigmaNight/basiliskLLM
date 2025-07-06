"""Tests for the new IPC architecture using pytest."""

import os
import sys
import tempfile
import time
from datetime import datetime

import pytest

from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal


class TestBasiliskIpc:
	"""Test cases for the unified IPC interface."""

	@pytest.fixture
	def ipc(self):
		"""Create an IPC instance for testing."""
		ipc_instance = BasiliskIpc("test_basilisk_ipc")
		yield ipc_instance
		# Cleanup
		if hasattr(ipc_instance, "stop_receiver"):
			ipc_instance.stop_receiver()
		# Clean up Unix socket files on Unix systems
		if sys.platform != "win32":
			socket_path = "/tmp/basilisk_test_basilisk_ipc.sock"
			if os.path.exists(socket_path):
				os.unlink(socket_path)

	@pytest.fixture
	def callback_tracker(self):
		"""Create a callback tracker for testing."""

		class CallbackTracker:
			def __init__(self):
				self.called = False
				self.data = None
				self.call_count = 0

			def callback(self, data):
				self.called = True
				self.data = data
				self.call_count += 1

			def counting_callback(self, data):
				self.call_count += 1

		return CallbackTracker()

	@pytest.fixture
	def temp_bskc_file(self):
		"""Create a temporary BSKC file for testing."""
		with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
			file_path = tmp.name
		yield file_path
		# Cleanup
		if os.path.exists(file_path):
			os.unlink(file_path)

	def test_start_receiver(self, ipc, callback_tracker):
		"""Test starting the IPC receiver."""
		callbacks = {"send_focus": callback_tracker.callback}
		result = ipc.start_receiver(callbacks)
		assert result is True
		assert ipc.is_running() is True

	def test_stop_receiver(self, ipc, callback_tracker):
		"""Test stopping the IPC receiver."""
		callbacks = {"send_focus": callback_tracker.callback}
		ipc.start_receiver(callbacks)
		assert ipc.is_running() is True

		ipc.stop_receiver()
		time.sleep(0.1)  # Allow time for shutdown
		assert ipc.is_running() is False

	def test_send_focus_signal(self, ipc, callback_tracker):
		"""Test sending a focus signal."""
		# Start receiver
		callbacks = {"send_focus": callback_tracker.callback}
		ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Send signal using the low-level interface
		focus_signal = FocusSignal(timestamp=datetime.now())
		result = ipc.send_signal(focus_signal.model_dump_json())
		assert result is True

		# Wait for callback
		time.sleep(0.1)
		assert callback_tracker.called is True
		# The callback data should be a Pydantic model with signal_type and timestamp
		assert callback_tracker.data is not None
		assert callback_tracker.data.signal_type == "focus"

	def test_send_open_bskc_signal(self, ipc, callback_tracker, temp_bskc_file):
		"""Test sending an open BSKC signal."""
		# Start receiver
		callbacks = {"open_bskc": callback_tracker.callback}
		ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Send signal using the low-level interface
		open_signal = OpenBskcSignal(file_path=temp_bskc_file)
		result = ipc.send_signal(open_signal.model_dump_json())
		assert result is True

		# Wait for callback
		time.sleep(0.1)
		assert callback_tracker.called is True
		# The callback data should be a Pydantic model with signal_type and file_path
		assert callback_tracker.data is not None
		assert callback_tracker.data.signal_type == "open_bskc"
		assert str(callback_tracker.data.file_path) == temp_bskc_file

	def test_send_signal_no_receiver(self, ipc):
		"""Test sending a signal when no receiver is running."""
		# Don't start receiver
		focus_signal = FocusSignal(timestamp=datetime.now())
		result = ipc.send_signal(focus_signal.model_dump_json())
		assert result is False

	def test_multiple_signals(self, ipc, callback_tracker):
		"""Test sending multiple signals in sequence."""
		# Start receiver
		callbacks = {"send_focus": callback_tracker.counting_callback}
		ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Send multiple signals
		for i in range(3):
			focus_signal = FocusSignal(timestamp=datetime.now())
			result = ipc.send_signal(focus_signal.model_dump_json())
			assert result is True
			time.sleep(0.05)

		# Wait for all callbacks
		time.sleep(0.2)
		assert callback_tracker.call_count == 3

	@pytest.mark.parametrize("signal_count", [1, 3, 5])
	def test_multiple_signals_parametrized(
		self, ipc, callback_tracker, signal_count
	):
		"""Test sending multiple signals with different counts."""
		# Start receiver
		callbacks = {"send_focus": callback_tracker.counting_callback}
		ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Send multiple signals
		for i in range(signal_count):
			focus_signal = FocusSignal(timestamp=datetime.now())
			result = ipc.send_signal(focus_signal.model_dump_json())
			assert result is True
			time.sleep(0.05)

		# Wait for all callbacks
		time.sleep(0.2)
		assert callback_tracker.call_count == signal_count
