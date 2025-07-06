"""Tests for the Windows IPC mechanism using pytest.

This module contains unit tests for the Windows named pipe communication
system used for inter-process communication in the application.
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
	return "test_basilisk_ipc"


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
	sys.platform != "win32", reason="Windows IPC only works on Windows"
)
def test_focus_signal_integration(test_pipe_name, received_signals):
	"""Test sending and receiving focus signals."""

	def on_focus(data):
		received_signals.append(("focus", data))

	ipc = BasiliskIpc(test_pipe_name)

	try:
		# Start receiver
		success = ipc.start_receiver({"send_focus": on_focus})
		assert success
		time.sleep(0.5)  # Give receiver time to start

		# Send signal using the low-level interface
		focus_signal = FocusSignal(timestamp=datetime.now())
		success = ipc.send_signal(focus_signal.model_dump_json())
		assert success
		time.sleep(0.5)  # Give signal time to be processed

		# Check received signal
		assert len(received_signals) == 1
		signal_type, data = received_signals[0]
		assert signal_type == "focus"
		# Data is now a Pydantic model
		assert data.signal_type == "focus"
		assert data.timestamp is not None

	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform != "win32", reason="Windows IPC only works on Windows"
)
def test_open_bskc_signal_integration(test_pipe_name, received_signals):
	"""Test sending and receiving open BSKC signals."""

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
			# Send signal using the low-level interface
			open_signal = OpenBskcSignal(file_path=test_file)
			success = ipc.send_signal(open_signal.model_dump_json())
			assert success
			time.sleep(0.5)  # Give signal time to be processed

			# Check received signal
			assert len(received_signals) == 1
			signal_type, data = received_signals[0]
			assert signal_type == "open_bskc"
			# Data is now a Pydantic model
			assert data.signal_type == "open_bskc"
			assert str(data.file_path) == test_file
		finally:
			# Clean up the temporary file

			if os.path.exists(test_file):
				os.unlink(test_file)

	finally:
		ipc.stop_receiver()


@pytest.mark.skipif(
	sys.platform != "win32", reason="Windows IPC only works on Windows"
)
def test_multiple_signals(test_pipe_name, received_signals):
	"""Test sending multiple signals in sequence."""

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


def test_receiver_stop_without_start(test_pipe_name):
	"""Test that stopping a receiver without starting doesn't cause errors."""
	ipc = BasiliskIpc(test_pipe_name)

	# This should not raise an exception
	ipc.stop_receiver()


def test_start_receiver_twice(test_pipe_name):
	"""Test that starting a receiver twice returns True and doesn't cause issues."""
	ipc = BasiliskIpc(test_pipe_name)

	try:
		# First start
		success1 = ipc.start_receiver({"send_focus": lambda x: None})
		assert success1

		# Second start should also return True
		success2 = ipc.start_receiver({"send_focus": lambda x: None})
		assert success2

	finally:
		ipc.stop_receiver()
