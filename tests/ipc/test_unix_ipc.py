"""Tests for the Unix IPC mechanism using pytest.

This module contains unit tests for the Unix domain socket communication
system used for inter-process communication in the application on Unix/Linux systems.
"""

import os
import sys
import tempfile
import time
from datetime import datetime

import pytest

from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal


@pytest.fixture
def test_pipe_name():
	"""Fixture providing a test pipe name."""
	return f"test_basilisk_unix_ipc_{os.getpid()}"


@pytest.fixture
def received_signals():
	"""Fixture providing a list to collect received signals."""
	signals = []
	yield signals
	signals.clear()


def test_basilisk_ipc_initialization(test_pipe_name):
	"""Test BasiliskIpc initialization."""
	ipc = BasiliskIpc(test_pipe_name)
	assert ipc is not None
	assert not ipc.is_running()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_unix_socket_cleanup(test_pipe_name):
	"""Test that Unix socket files are properly cleaned up."""
	ipc = BasiliskIpc(test_pipe_name)
	
	# Extract socket path (this is Unix specific)
	socket_path = f"/tmp/basilisk_{test_pipe_name}.sock"
	
	# Socket file should not exist initially
	assert not os.path.exists(socket_path)
	
	# Start receiver
	success = ipc.start_receiver({"send_focus": lambda x: None})
	assert success
	time.sleep(0.1)  # Give time to start
	
	# Socket file should exist while running
	assert os.path.exists(socket_path)
	
	# Stop receiver
	ipc.stop_receiver()
	time.sleep(0.1)  # Give time to cleanup
	
	# Socket file should be cleaned up
	assert not os.path.exists(socket_path)


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_focus_signal_integration(test_pipe_name, received_signals):
	"""Test sending and receiving focus signals on Unix."""

	def on_focus(data):
		received_signals.append(("focus", data))

	ipc = BasiliskIpc(test_pipe_name)

	try:
		# Start receiver
		success = ipc.start_receiver({"send_focus": on_focus})
		assert success
		time.sleep(0.5)  # Give receiver time to start

		# Send focus signal
		focus_signal = FocusSignal(timestamp=datetime.now())
		success = ipc.send_signal(focus_signal.model_dump_json())
		time.sleep(0.3)  # Give time for signal processing

		assert success
		assert len(received_signals) == 1
		assert received_signals[0][0] == "focus"

	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_open_bskc_signal_integration(test_pipe_name, received_signals):
	"""Test sending and receiving open BSKC signals on Unix."""

	def on_open_bskc(data):
		received_signals.append(("open_bskc", data))

	ipc = BasiliskIpc(test_pipe_name)

	try:
		# Start receiver
		success = ipc.start_receiver({"open_bskc": on_open_bskc})
		assert success
		time.sleep(0.5)  # Give receiver time to start

		# Create a temporary test file
		with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
			test_file = tmp.name

		try:
			# Send open BSKC signal
			open_signal = OpenBskcSignal(file_path=test_file)
			success = ipc.send_signal(open_signal.model_dump_json())
			time.sleep(0.3)  # Give time for signal processing

			assert success
			assert len(received_signals) == 1
			assert received_signals[0][0] == "open_bskc"

		finally:
			# Clean up the temporary file
			if os.path.exists(test_file):
				os.unlink(test_file)

	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_multiple_signals(test_pipe_name, received_signals):
	"""Test sending multiple signals in sequence on Unix."""

	def on_focus(data):
		received_signals.append(("focus", data))

	def on_open_bskc(data):
		received_signals.append(("open_bskc", data))

	ipc = BasiliskIpc(test_pipe_name)

	try:
		# Start receiver with multiple callbacks
		success = ipc.start_receiver(
			{"send_focus": on_focus, "open_bskc": on_open_bskc}
		)
		assert success
		time.sleep(0.5)  # Give receiver time to start

		# Send focus signal
		focus_signal = FocusSignal(timestamp=datetime.now())
		success1 = ipc.send_signal(focus_signal.model_dump_json())
		time.sleep(0.3)

		# Create a temporary test file for BSKC signal
		with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
			test_file = tmp.name

		try:
			# Send open BSKC signal
			open_signal = OpenBskcSignal(file_path=test_file)
			success2 = ipc.send_signal(open_signal.model_dump_json())
			time.sleep(0.3)

			assert success1
			assert success2

			# Should have received both signals
			assert len(received_signals) == 2
		finally:
			# Clean up the temporary file
			if os.path.exists(test_file):
				os.unlink(test_file)

	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_unix_socket_permissions(test_pipe_name):
	"""Test Unix socket file permissions and ownership."""
	ipc = BasiliskIpc(test_pipe_name)
	
	# Extract socket path
	socket_path = f"/tmp/basilisk_{test_pipe_name}.sock"
	
	try:
		# Start receiver
		success = ipc.start_receiver({"send_focus": lambda x: None})
		assert success
		time.sleep(0.1)
		
		# Check socket file exists and permissions
		assert os.path.exists(socket_path)
		
		# Check that the socket is accessible
		stat_info = os.stat(socket_path)
		assert stat_info.st_uid == os.getuid()  # Should be owned by current user
		
	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_unix_socket_error_handling(test_pipe_name):
	"""Test error handling in Unix socket operations."""
	ipc = BasiliskIpc(test_pipe_name)
	
	# Test sending signal without receiver
	focus_signal = FocusSignal(timestamp=datetime.now())
	result = ipc.send_signal(focus_signal.model_dump_json())
	# Should return False when no receiver is running
	assert result is False


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_receiver_stop_without_start(test_pipe_name):
	"""Test that stopping a receiver without starting doesn't cause errors."""
	ipc = BasiliskIpc(test_pipe_name)
	
	# Should not raise any exceptions
	ipc.stop_receiver()
	assert not ipc.is_running()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"  
)
def test_start_receiver_twice(test_pipe_name):
	"""Test that starting a receiver twice returns True and doesn't cause issues."""
	ipc = BasiliskIpc(test_pipe_name)
	
	try:
		# First start should succeed
		result1 = ipc.start_receiver({"send_focus": lambda x: None})
		assert result1 is True
		assert ipc.is_running()
		
		# Second start should also return True (already running)
		result2 = ipc.start_receiver({"send_focus": lambda x: None})
		assert result2 is True
		assert ipc.is_running()
		
	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform == "win32", reason="Unix IPC only works on Unix/Linux"
)
def test_concurrent_senders(test_pipe_name, received_signals):
	"""Test multiple concurrent senders to the same Unix socket."""
	
	def on_focus(data):
		received_signals.append(("focus", data))

	ipc = BasiliskIpc(test_pipe_name)

	try:
		# Start receiver
		success = ipc.start_receiver({"send_focus": on_focus})
		assert success
		time.sleep(0.5)

		# Send multiple signals quickly
		focus_signal = FocusSignal(timestamp=datetime.now())
		signal_data = focus_signal.model_dump_json()
		
		results = []
		for _ in range(5):
			result = ipc.send_signal(signal_data)
			results.append(result)
			time.sleep(0.05)  # Small delay to avoid overwhelming

		# Wait for processing
		time.sleep(0.5)

		# All sends should succeed
		assert all(results)
		# Should receive all signals
		assert len(received_signals) == 5

	finally:
		ipc.stop_receiver()