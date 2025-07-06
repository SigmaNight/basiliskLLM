"""Documentation for the display_signal_error_msg mock functionality.

This module explains how the display_signal_error_msg mock works and how to use it in tests.

## Purpose

The mock prevents error dialogs from being displayed during tests, which would otherwise:
- Interrupt the test execution
- Require manual intervention to close dialogs
- Potentially cause tests to hang in CI/CD environments

## How it works

The mock is automatically applied to all tests via the `mock_display_error_msg` fixture in conftest.py.
This fixture mocks the following functions:

1. `basilisk.send_signal.display_signal_error_msg` - Main error display function
2. `basilisk.send_signal._display_error_msg_windows` - Windows-specific error display
3. `basilisk.send_signal._display_error_msg_macos` - macOS-specific error display
4. `basilisk.send_signal._display_error_msg_linux` - Linux-specific error display

## Usage in tests

### Basic usage (automatic)

The mock is applied automatically to all tests. No special setup is needed:

```python
def test_some_ipc_functionality():
    # This will not display any error dialogs
    send_focus_signal()
    # Test continues normally
```

### Advanced usage (accessing the mock)

If you need to verify that error functions were called:

```python
def test_error_handling(mock_display_error_msg):
    # Call function that should trigger an error
    send_focus_signal()

    # Verify the error display was called
    mock_display_error_msg["main"].assert_called_once_with("focus")
```

### Mock structure

The `mock_display_error_msg` fixture returns a dictionary with the following keys:
- `"main"`: Mock for `display_signal_error_msg`
- `"windows"`: Mock for `_display_error_msg_windows`
- `"macos"`: Mock for `_display_error_msg_macos`
- `"linux"`: Mock for `_display_error_msg_linux`

## Notes

- The mock is applied with `autouse=True`, so it's active for all tests
- The main function mock prevents platform-specific functions from being called
- Platform-specific mocks are provided for completeness and direct testing
- All mocks are reset between tests automatically
"""
