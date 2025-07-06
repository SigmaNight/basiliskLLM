"""Test to verify that error dialogs are properly mocked in IPC scenarios."""

import tempfile

from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal


def test_send_focus_signal_no_dialog_on_error(mock_display_error_msg):
	"""Test that send_focus_signal does not display dialog when IPC fails."""
	# This should fail since no IPC server is running
	send_focus_signal()

	# Verify that the error display function was called
	mock_display_error_msg["main"].assert_called_once_with("focus")


def test_send_open_bskc_file_signal_no_dialog_on_error(mock_display_error_msg):
	"""Test that send_open_bskc_file_signal does not display dialog when IPC fails."""
	# Create a temporary file
	with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
		test_file = tmp.name

	# This should fail since no IPC server is running
	send_open_bskc_file_signal(test_file)

	# Verify that the error display function was called
	mock_display_error_msg["main"].assert_called_once_with("open_file")


def test_multiple_signal_calls_no_dialogs(mock_display_error_msg):
	"""Test that multiple signal calls don't display dialogs."""
	# Call multiple times
	send_focus_signal()
	send_focus_signal()

	with tempfile.NamedTemporaryFile(suffix=".bskc", delete=False) as tmp:
		test_file = tmp.name

	send_open_bskc_file_signal(test_file)

	# Verify that error display was called appropriately
	assert mock_display_error_msg["main"].call_count == 3

	# Check the specific calls
	calls = mock_display_error_msg["main"].call_args_list
	assert calls[0][0] == ("focus",)
	assert calls[1][0] == ("focus",)
	assert calls[2][0] == ("open_file",)
