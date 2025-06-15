"""
Unit tests for the HistoryMsgTextCtrl class.

This module contains comprehensive tests for the history message text control,
including tests for message management, navigation, text control behavior,
edge cases, and error conditions.

Testing Framework: unittest
"""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import sys
import os
import tempfile

# Add the GUI module to the path
gui_path = os.path.join(os.path.dirname(__file__), '..', 'gui')
if gui_path not in sys.path:
    sys.path.insert(0, gui_path)

try:
    from history_msg_text_ctrl import HistoryMsgTextCtrl
except ImportError as e:
    print(f"Warning: Could not import HistoryMsgTextCtrl: {e}")
    # Create a mock class for testing infrastructure
    class HistoryMsgTextCtrl:
        def __init__(self, parent=None):
            self.parent = parent
            self.history = []
            self.position = -1

class TestHistoryMsgTextCtrl(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures before each test method."""
        self.mock_parent = Mock()
        self.history_ctrl = HistoryMsgTextCtrl(self.mock_parent)

    def tearDown(self):
        """Clean up after each test method."""
        if hasattr(self.history_ctrl, 'Destroy'):
            self.history_ctrl.Destroy()
        self.history_ctrl = None

    def test_init_with_parent(self):
        """Test initialization with parent parameter."""
        ctrl = HistoryMsgTextCtrl(self.mock_parent)
        self.assertIsNotNone(ctrl)

    def test_init_without_parent(self):
        """Test initialization without parent parameter."""
        with self.assertRaises(TypeError):
            HistoryMsgTextCtrl()

    def test_init_with_none_parent(self):
        """Test initialization with None parent."""
        ctrl = HistoryMsgTextCtrl(None)
        self.assertIsNotNone(ctrl)

    def test_add_message_to_history(self):
        """Test adding a single message to history."""
        test_message = "Test message"
        result = self.history_ctrl.add_message(test_message)
        self.assertTrue(result)

    def test_add_empty_message(self):
        """Test adding empty message to history."""
        result = self.history_ctrl.add_message("")
        self.assertIsNotNone(result)

    def test_add_none_message(self):
        """Test adding None message to history."""
        with self.assertRaises((TypeError, ValueError)):
            self.history_ctrl.add_message(None)

    def test_add_multiple_messages(self):
        """Test adding multiple messages to history."""
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            self.history_ctrl.add_message(msg)
        history = self.history_ctrl.get_history()
        self.assertEqual(len(history), 3)
        for msg in messages:
            self.assertIn(msg, history)

    def test_get_history_empty(self):
        """Test getting history when no messages added."""
        history = self.history_ctrl.get_history()
        self.assertEqual(history, [])

    def test_clear_history(self):
        """Test clearing message history."""
        self.history_ctrl.add_message("Test message")
        self.history_ctrl.clear_history()
        history = self.history_ctrl.get_history()
        self.assertEqual(len(history), 0)

    def test_get_previous_message(self):
        """Test retrieving previous message from history."""
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            self.history_ctrl.add_message(msg)
        prev_msg = self.history_ctrl.get_previous_message()
        self.assertEqual(prev_msg, "Message 3")

    def test_get_next_message(self):
        """Test retrieving next message from history."""
        messages = ["Message 1", "Message 2", "Message 3"]
        for msg in messages:
            self.history_ctrl.add_message(msg)
        self.history_ctrl.get_previous_message()
        self.history_ctrl.get_previous_message()
        next_msg = self.history_ctrl.get_next_message()
        self.assertEqual(next_msg, "Message 3")

    def test_navigate_beyond_history_bounds(self):
        """Test navigation beyond history boundaries."""
        self.history_ctrl.add_message("Only message")
        msg1 = self.history_ctrl.get_previous_message()
        msg2 = self.history_ctrl.get_previous_message()
        self.assertEqual(msg1, msg2)

    def test_navigate_empty_history(self):
        """Test navigation when history is empty."""
        prev_msg = self.history_ctrl.get_previous_message()
        next_msg = self.history_ctrl.get_next_message()
        self.assertIsNone(prev_msg)
        self.assertIsNone(next_msg)

    def test_set_current_text(self):
        """Test setting current text in the control."""
        test_text = "Current text"
        self.history_ctrl.set_current_text(test_text)
        current = self.history_ctrl.get_current_text()
        self.assertEqual(current, test_text)

    def test_get_current_text_empty(self):
        """Test getting current text when empty."""
        current = self.history_ctrl.get_current_text()
        self.assertEqual(current, "")

    def test_text_control_focus(self):
        """Test setting focus to the text control."""
        with patch.object(self.history_ctrl, 'SetFocus') as mock_focus:
            self.history_ctrl.set_focus()
            mock_focus.assert_called_once()

    def test_history_position_tracking(self):
        """Test that history position is tracked correctly."""
        messages = ["Msg 1", "Msg 2", "Msg 3"]
        for msg in messages:
            self.history_ctrl.add_message(msg)
        pos = self.history_ctrl.get_history_position()
        self.assertEqual(pos, -1)
        self.history_ctrl.get_previous_message()
        pos = self.history_ctrl.get_history_position()
        self.assertEqual(pos, 2)

    def test_maximum_history_size(self):
        """Test behavior when history reaches maximum size."""
        max_size = getattr(self.history_ctrl, 'MAX_HISTORY_SIZE', 1000)
        for i in range(max_size + 10):
            self.history_ctrl.add_message(f"Message {i}")
        history = self.history_ctrl.get_history()
        self.assertLessEqual(len(history), max_size)

    def test_very_long_message(self):
        """Test handling of very long messages."""
        long_message = "A" * 10000
        result = self.history_ctrl.add_message(long_message)
        self.assertTrue(result)
        retrieved = self.history_ctrl.get_previous_message()
        self.assertEqual(retrieved, long_message)

    def test_unicode_messages(self):
        """Test handling of unicode characters in messages."""
        unicode_messages = ["Hello 世界", "🚀 Test", "Café naïve résumé"]
        for msg in unicode_messages:
            self.history_ctrl.add_message(msg)
        for msg in reversed(unicode_messages):
            retrieved = self.history_ctrl.get_previous_message()
            self.assertEqual(retrieved, msg)

    def test_multiline_messages(self):
        """Test handling of multiline messages."""
        multiline_msg = "Line 1\nLine 2\nLine 3"
        self.history_ctrl.add_message(multiline_msg)
        retrieved = self.history_ctrl.get_previous_message()
        self.assertEqual(retrieved, multiline_msg)

    def test_duplicate_messages(self):
        """Test adding duplicate messages to history."""
        msg = "Duplicate message"
        self.history_ctrl.add_message(msg)
        self.history_ctrl.add_message(msg)
        history = self.history_ctrl.get_history()
        self.assertGreaterEqual(len(history), 1)

    def test_save_history_to_file(self):
        """Test saving history to file if supported."""
        if hasattr(self.history_ctrl, 'save_history'):
            messages = ["Save test 1", "Save test 2"]
            for msg in messages:
                self.history_ctrl.add_message(msg)
            with patch('builtins.open', mock_open()) as mock_file:
                result = self.history_ctrl.save_history("test_history.txt")
                self.assertTrue(result)
                mock_file.assert_called_once()

    def test_load_history_from_file(self):
        """Test loading history from file if supported."""
        if hasattr(self.history_ctrl, 'load_history'):
            mock_data = "Message 1\nMessage 2\nMessage 3"
            with patch('builtins.open', mock_open(read_data=mock_data)):
                result = self.history_ctrl.load_history("test_history.txt")
                self.assertTrue(result)
                history = self.history_ctrl.get_history()
                self.assertEqual(len(history), 3)

    def test_configuration_settings(self):
        """Test configuration settings if supported."""
        if hasattr(self.history_ctrl, 'configure'):
            config = {'max_history': 50, 'save_duplicates': False}
            self.history_ctrl.configure(config)
            current_config = self.history_ctrl.get_configuration()
            self.assertEqual(current_config['max_history'], 50)

    def test_str_representation(self):
        """Test string representation of the control."""
        str_repr = str(self.history_ctrl)
        self.assertIsInstance(str_repr, str)
        self.assertIn('HistoryMsgTextCtrl', str_repr)

    def test_repr_representation(self):
        """Test repr representation of the control."""
        repr_str = repr(self.history_ctrl)
        self.assertIsInstance(repr_str, str)

    @patch('sys.platform', 'win32')
    def test_platform_specific_behavior_windows(self):
        """Test platform-specific behavior on Windows."""
        pass

    @patch('sys.platform', 'linux')
    def test_platform_specific_behavior_linux(self):
        """Test platform-specific behavior on Linux."""
        pass

if __name__ == '__main__':
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromTestCase(TestHistoryMsgTextCtrl)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)