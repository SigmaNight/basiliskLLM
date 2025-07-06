"""Migration tests to ensure backward compatibility during IPC transition."""

import os
import time

import pytest

from basilisk.ipc import BasiliskIpc
from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal


class TestIpcMigration:
	"""Test cases to verify backward compatibility during IPC migration."""

	@pytest.fixture(autouse=True)
	def setup_ipc(self):
		"""Set up test fixtures."""
		self.ipc = BasiliskIpc("basilisk_ipc")
		self.callback_called = False
		self.callback_data = None
		yield
		# Clean up
		if hasattr(self.ipc, "stop_receiver"):
			self.ipc.stop_receiver()

	def _test_callback(self, data):
		"""Test callback function."""
		self.callback_called = True
		self.callback_data = data

	def test_send_focus_signal_integration(self):
		"""Test that send_focus_signal works with new IPC architecture."""
		# Start IPC receiver
		callbacks = {"send_focus": self._test_callback}
		self.ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Use the public API
		send_focus_signal()

		# Wait for callback
		time.sleep(0.1)
		assert self.callback_called

	def test_send_open_bskc_signal_integration(self, tmp_path):
		"""Test that send_open_bskc_file_signal works with new IPC architecture."""
		# Start IPC receiver
		callbacks = {"open_bskc": self._test_callback}
		self.ipc.start_receiver(callbacks)

		# Wait for receiver to start
		time.sleep(0.1)

		# Use the public API
		test_file_path = os.path.join(tmp_path, "file.bskc")
		with open(test_file_path, "w") as f:
			f.write("Test content for BSKC file")
		send_open_bskc_file_signal(test_file_path)

		# Wait for callback
		time.sleep(0.1)
		assert self.callback_called
		if (
			isinstance(self.callback_data, dict)
			and "file_path" in self.callback_data
		):
			assert self.callback_data["file_path"] == test_file_path

	def test_fallback_to_file_method(self):
		"""Test that the fallback to file method still works when IPC fails."""
		# Don't start IPC receiver to force fallback

		# These should not raise exceptions and should fall back to file method
		try:
			send_focus_signal()
			send_open_bskc_file_signal("/test/path/file.bskc")
		except Exception as e:
			pytest.fail(f"Fallback method failed: {e}")


if __name__ == "__main__":
	pytest.main([__file__])
