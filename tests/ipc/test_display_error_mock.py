"""Test for display_signal_error_msg mock functionality."""


def test_display_signal_error_msg_is_mocked(mock_display_error_msg):
	"""Test that display_signal_error_msg is properly mocked."""
	# Import the function after the mock is in place
	from basilisk.send_signal import display_signal_error_msg

	# Call the function directly - this should call the mock
	display_signal_error_msg("test", "test details")

	# Verify the mock was called
	mock_display_error_msg["main"].assert_called_once_with(
		"test", "test details"
	)


def test_send_focus_signal_uses_mocked_display(mock_display_error_msg):
	"""Test that send_focus_signal uses the mocked display function when it fails."""
	from basilisk.send_signal import send_focus_signal

	# This will fail to send the signal (since no IPC server is running)
	# but should not display any error dialogs
	send_focus_signal()

	# The mock should have been called due to the failure
	assert mock_display_error_msg["main"].called


def test_mock_prevents_system_calls(mock_display_error_msg):
	"""Test that the mock prevents actual system calls."""
	from basilisk.send_signal import display_signal_error_msg

	# Call the function multiple times
	for i in range(3):
		display_signal_error_msg("focus", f"test error {i}")

	# Verify all calls were intercepted
	assert mock_display_error_msg["main"].call_count == 3

	# Verify no platform-specific calls were made
	# (since we're mocking the main function, not the platform-specific ones)
	assert not mock_display_error_msg["windows"].called
	assert not mock_display_error_msg["macos"].called
	assert not mock_display_error_msg["linux"].called
