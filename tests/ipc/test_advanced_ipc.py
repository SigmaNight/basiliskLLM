"""Advanced IPC tests using pytest features."""

import time

import pytest

from basilisk.ipc import OpenBskcSignal


class TestAdvancedIpc:
	"""Advanced test cases for IPC functionality."""

	@pytest.mark.parametrize(
		"pipe_name",
		[
			"test_pipe_1",
			"test_pipe_2",
			"special-pipe_name",
			"pipe_with_numbers_123",
		],
	)
	def test_ipc_with_different_pipe_names(self, pipe_name):
		"""Test IPC with different pipe names."""
		from basilisk.ipc import BasiliskIpc

		ipc = BasiliskIpc(pipe_name)
		assert ipc.pipe_name.endswith(pipe_name)
		assert not ipc.is_running()

	@pytest.mark.parametrize("signal_count", [1, 5, 10])
	def test_multiple_signals_performance(
		self, ipc_with_cleanup, callback_manager, signal_factory, signal_count
	):
		"""Test performance with multiple signals."""
		# Create tracking callback
		focus_callback = callback_manager.create_tracking_callback("focus")

		# Start receiver
		ipc_with_cleanup.start_receiver({"send_focus": focus_callback})
		time.sleep(0.1)

		# Send multiple signals
		start_time = time.time()
		for i in range(signal_count):
			signal_json = signal_factory.create_focus_json()
			result = ipc_with_cleanup.send_signal(signal_json)
			assert result is True

		# Wait for all callbacks
		time.sleep(0.2)
		end_time = time.time()

		# Verify all signals were received
		assert callback_manager.get_call_count("focus") == signal_count

		# Performance assertion (should be fast)
		duration = end_time - start_time
		assert duration < 5.0  # Should complete within 5 seconds

	def test_signal_ordering(
		self, ipc_with_cleanup, callback_manager, signal_factory, temp_bskc_file
	):
		"""Test that signals are processed in order."""
		# Create callbacks that track order
		received_signals = []

		def focus_callback(data):
			received_signals.append(("focus", data.timestamp))

		def open_bskc_callback(data):
			received_signals.append(("open_bskc", str(data.file_path)))

		# Start receiver
		ipc_with_cleanup.start_receiver(
			{"send_focus": focus_callback, "open_bskc": open_bskc_callback}
		)
		time.sleep(0.1)

		# Send signals in specific order
		focus_signal1 = signal_factory.create_focus_signal()
		open_bskc_signal = signal_factory.create_open_bskc_signal(
			temp_bskc_file
		)
		focus_signal2 = signal_factory.create_focus_signal()

		ipc_with_cleanup.send_signal(focus_signal1.model_dump_json())
		time.sleep(0.05)
		ipc_with_cleanup.send_signal(open_bskc_signal.model_dump_json())
		time.sleep(0.05)
		ipc_with_cleanup.send_signal(focus_signal2.model_dump_json())

		# Wait for all callbacks
		time.sleep(0.2)

		# Verify order
		assert len(received_signals) == 3
		assert received_signals[0][0] == "focus"
		assert received_signals[1][0] == "open_bskc"
		assert received_signals[2][0] == "focus"

	@pytest.mark.slow
	def test_long_running_ipc(
		self, ipc_with_cleanup, callback_manager, signal_factory
	):
		"""Test IPC stability over time."""
		focus_callback = callback_manager.create_tracking_callback("focus")

		# Start receiver
		ipc_with_cleanup.start_receiver({"send_focus": focus_callback})
		time.sleep(0.1)

		# Send signals over time
		for i in range(10):
			signal_json = signal_factory.create_focus_json()
			result = ipc_with_cleanup.send_signal(signal_json)
			assert result is True
			time.sleep(0.1)  # Small delay between signals

		# Wait for all callbacks
		time.sleep(0.5)

		# Verify all signals were received
		assert callback_manager.get_call_count("focus") == 10

	def test_error_resilience(
		self, ipc_with_cleanup, callback_manager, signal_factory
	):
		"""Test that IPC is resilient to errors."""
		error_count = 0

		def error_callback(data):
			nonlocal error_count
			error_count += 1
			if error_count == 2:  # Raise error on second call
				raise ValueError("Test error")

		# Start receiver
		ipc_with_cleanup.start_receiver({"send_focus": error_callback})
		time.sleep(0.1)

		# Send multiple signals, some will cause errors
		for i in range(5):
			signal_json = signal_factory.create_focus_json()
			result = ipc_with_cleanup.send_signal(signal_json)
			assert result is True
			time.sleep(0.05)

		# Wait for all callbacks
		time.sleep(0.2)

		# Verify that IPC is still working after errors
		assert ipc_with_cleanup.is_running()
		assert error_count == 5  # All callbacks were called

	@pytest.mark.parametrize("file_extension", [".bskc", ".json", ".txt"])
	def test_different_file_types(
		self, ipc_with_cleanup, callback_manager, file_extension
	):
		"""Test with different file types."""
		import tempfile

		# Create temporary file with specific extension
		with tempfile.NamedTemporaryFile(
			suffix=file_extension, delete=False
		) as tmp:
			temp_file = tmp.name

		try:
			open_bskc_callback = callback_manager.create_tracking_callback(
				"open_bskc"
			)

			# Start receiver
			ipc_with_cleanup.start_receiver({"open_bskc": open_bskc_callback})
			time.sleep(0.1)

			# Send signal
			signal = OpenBskcSignal(file_path=temp_file)
			result = ipc_with_cleanup.send_signal(signal.model_dump_json())
			assert result is True

			# Wait for callback
			time.sleep(0.1)

			# Verify callback was called
			assert callback_manager.get_call_count("open_bskc") == 1
			latest_call = callback_manager.get_latest_call("open_bskc")
			assert str(latest_call.file_path) == temp_file

		finally:
			# Cleanup
			import os

			if os.path.exists(temp_file):
				os.unlink(temp_file)

	def test_concurrent_receivers(
		self, ipc_pipe_name, callback_manager, signal_factory
	):
		"""Test behavior with multiple IPC instances."""
		from basilisk.ipc import BasiliskIpc

		# Create two IPC instances with different pipe names
		ipc1 = BasiliskIpc(f"{ipc_pipe_name}_1")
		ipc2 = BasiliskIpc(f"{ipc_pipe_name}_2")

		try:
			# Create callbacks
			callback1 = callback_manager.create_tracking_callback("focus_1")
			callback2 = callback_manager.create_tracking_callback("focus_2")

			# Start both receivers
			ipc1.start_receiver({"send_focus": callback1})
			ipc2.start_receiver({"send_focus": callback2})
			time.sleep(0.1)

			# Send signal to first IPC
			signal_json = signal_factory.create_focus_json()
			result1 = ipc1.send_signal(signal_json)
			assert result1 is True

			# Send signal to second IPC
			result2 = ipc2.send_signal(signal_json)
			assert result2 is True

			# Wait for callbacks
			time.sleep(0.2)

			# Verify that each IPC received only its own signal
			assert callback_manager.get_call_count("focus_1") == 1
			assert callback_manager.get_call_count("focus_2") == 1

		finally:
			# Cleanup
			ipc1.stop_receiver()
			ipc2.stop_receiver()

	@pytest.mark.integration
	def test_full_workflow(
		self, ipc_with_cleanup, callback_manager, signal_factory, temp_bskc_file
	):
		"""Test a complete IPC workflow."""
		# Track all signals
		all_signals = []

		def universal_callback(data):
			all_signals.append(data)

		# Start receiver with multiple callbacks
		ipc_with_cleanup.start_receiver(
			{"send_focus": universal_callback, "open_bskc": universal_callback}
		)
		time.sleep(0.1)

		# Simulate a real workflow
		# 1. Send focus signal
		focus_signal = signal_factory.create_focus_signal()
		ipc_with_cleanup.send_signal(focus_signal.model_dump_json())
		time.sleep(0.05)

		# 2. Send open file signal
		open_signal = signal_factory.create_open_bskc_signal(temp_bskc_file)
		ipc_with_cleanup.send_signal(open_signal.model_dump_json())
		time.sleep(0.05)

		# 3. Send another focus signal
		focus_signal2 = signal_factory.create_focus_signal()
		ipc_with_cleanup.send_signal(focus_signal2.model_dump_json())

		# Wait for all callbacks
		time.sleep(0.2)

		# Verify workflow
		assert len(all_signals) == 3
		assert all_signals[0].signal_type == "focus"
		assert all_signals[1].signal_type == "open_bskc"
		assert all_signals[2].signal_type == "focus"
		assert str(all_signals[1].file_path) == temp_bskc_file
