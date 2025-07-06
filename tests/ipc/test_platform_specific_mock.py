"""Test to verify platform-specific error functions are also mocked."""


def test_platform_specific_functions_mocked(mock_display_error_msg):
	"""Test that platform-specific error functions are properly mocked."""
	# Import the platform-specific functions
	from basilisk.send_signal import (
		_display_error_msg_linux,
		_display_error_msg_macos,
		_display_error_msg_windows,
	)

	# Test calling each function directly
	_display_error_msg_windows("Test Windows message")
	_display_error_msg_macos("Test macOS message")
	_display_error_msg_linux("Test Linux message")

	# Verify all were mocked
	mock_display_error_msg["windows"].assert_called_once_with(
		"Test Windows message"
	)
	mock_display_error_msg["macos"].assert_called_once_with(
		"Test macOS message"
	)
	mock_display_error_msg["linux"].assert_called_once_with(
		"Test Linux message"
	)


def test_platform_detection_with_mock(mock_display_error_msg):
	"""Test that platform-specific calls are mocked regardless of actual platform."""
	from basilisk.send_signal import display_signal_error_msg

	# Call the main function which will determine the platform
	display_signal_error_msg("focus", "Test error details")

	# Verify the main function was called (which is what we actually mock)
	mock_display_error_msg["main"].assert_called_once_with(
		"focus", "Test error details"
	)

	# The platform-specific functions should not be called since we mock the main function
	# This ensures no system calls happen regardless of the platform
	assert not mock_display_error_msg["windows"].called
	assert not mock_display_error_msg["macos"].called
	assert not mock_display_error_msg["linux"].called
