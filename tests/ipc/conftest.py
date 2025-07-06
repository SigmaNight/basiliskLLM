"""IPC-specific fixtures for pytest."""

import os
import sys
import tempfile

import pytest

from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal


@pytest.fixture
def ipc_pipe_name():
	"""Provide a unique pipe name for IPC tests."""
	return f"test_basilisk_ipc_{os.getpid()}"


@pytest.fixture
def ipc_with_cleanup(ipc_pipe_name):
	"""Create an IPC instance with proper cleanup."""
	ipc = BasiliskIpc(ipc_pipe_name)
	yield ipc
	# Cleanup
	if hasattr(ipc, "stop_receiver"):
		ipc.stop_receiver()
	# Clean up Unix socket files on Unix systems
	if sys.platform != "win32":
		socket_path = f"/tmp/basilisk_{ipc_pipe_name}.sock"
		if os.path.exists(socket_path):
			os.unlink(socket_path)


@pytest.fixture
def signal_factory():
	"""Factory for creating test signals."""

	class SignalFactory:
		def create_focus_signal(self):
			from datetime import datetime

			return FocusSignal(timestamp=datetime.now())

		def create_open_bskc_signal(self, file_path):
			return OpenBskcSignal(file_path=file_path)

		def create_focus_json(self):
			return self.create_focus_signal().model_dump_json()

		def create_open_bskc_json(self, file_path):
			return self.create_open_bskc_signal(file_path).model_dump_json()

	return SignalFactory()


@pytest.fixture
def multiple_temp_bskc_files():
	"""Create multiple temporary BSKC files for testing."""
	files = []
	for i in range(5):
		with tempfile.NamedTemporaryFile(
			suffix=f"_test_{i}.bskc", delete=False
		) as tmp:
			files.append(tmp.name)
	yield files
	# Cleanup
	for file_path in files:
		if os.path.exists(file_path):
			os.unlink(file_path)


@pytest.fixture
def callback_manager():
	"""Advanced callback manager for complex IPC tests."""

	class CallbackManager:
		def __init__(self):
			self.callbacks = {}
			self.call_history = []
			self.signal_counts = {}

		def register_callback(self, signal_type, callback_func):
			"""Register a callback for a specific signal type."""
			self.callbacks[signal_type] = callback_func

		def create_tracking_callback(self, signal_type):
			"""Create a callback that tracks calls."""

			def tracking_callback(data):
				self.call_history.append((signal_type, data))
				self.signal_counts[signal_type] = (
					self.signal_counts.get(signal_type, 0) + 1
				)

			return tracking_callback

		def get_call_count(self, signal_type):
			"""Get the number of times a signal type was called."""
			return self.signal_counts.get(signal_type, 0)

		def get_latest_call(self, signal_type):
			"""Get the latest call for a signal type."""
			for call_signal_type, data in reversed(self.call_history):
				if call_signal_type == signal_type:
					return data
			return None

		def clear_history(self):
			"""Clear call history."""
			self.call_history.clear()
			self.signal_counts.clear()

	return CallbackManager()


@pytest.fixture
def temp_bskc_file():
	"""Create a temporary BSKC file for testing."""
	with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
		file_path = tmp.name
	yield file_path
	# Cleanup
	if os.path.exists(file_path):
		os.unlink(file_path)
