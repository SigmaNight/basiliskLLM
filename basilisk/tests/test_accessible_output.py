import pytest
import re
from unittest.mock import Mock, patch, MagicMock, call
import logging

from basilisk.accessible_output import AccessibleOutputHandler
import basilisk.config as config
from basilisk.completion_handler import COMMON_PATTERN

@pytest.fixture
def mock_accessible_output():
    """Mock accessible_output3 library for testing."""
    mock_output = Mock()
    mock_output.speak = Mock()
    mock_output.braille = Mock()
    return mock_output

@pytest.fixture
def mock_config(mock_config):
    """Use the shared mock_config fixture and ensure accessible output is enabled."""
    mock_config.conversation.use_accessible_output = True
    return mock_config

@pytest.fixture
def handler():
    """Create an AccessibleOutputHandler instance for testing."""
    with patch('basilisk.accessible_output.config.conf') as mock_conf:
        mock_conf.return_value.conversation.use_accessible_output = True
        with patch('accessible_output3.outputs.auto.Auto') as mock_auto:
            handler = AccessibleOutputHandler()
            yield handler

@pytest.fixture
def handler_disabled():
    """Create an AccessibleOutputHandler instance with accessible output disabled."""
    with patch('basilisk.accessible_output.config.conf') as mock_conf:
        mock_conf.return_value.conversation.use_accessible_output = False
        handler = AccessibleOutputHandler()
        yield handler

@pytest.fixture
def sample_text():
    """Sample text for testing."""
    return "Hello, this is a test message"

@pytest.fixture
def markdown_text():
    """Sample markdown text for testing cleaning functionality."""
    return """# Header
**Bold text** and *italic text* and __underlined__ and _emphasized_.
[Link text](http://example.com)
![Alt text](image.jpg)
> Blockquote text
---
Regular text"""

class TestAccessibleOutputHandlerInitialization:
    """Test AccessibleOutputHandler initialization and configuration."""

    def test_initialization_with_accessible_output_enabled(self):
        """Test initialization when accessible output is enabled."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = True
            with patch('accessible_output3.outputs.auto.Auto') as mock_auto:
                handler = AccessibleOutputHandler()

                assert handler is not None
                assert handler.speech_stream_buffer == ""
                mock_auto.assert_called_once()

    def test_initialization_with_accessible_output_disabled(self):
        """Test initialization when accessible output is disabled."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = False
            with patch('accessible_output3.outputs.auto.Auto') as mock_auto:
                handler = AccessibleOutputHandler()

                assert handler is not None
                assert handler.speech_stream_buffer == ""
                assert handler._accessible_output is None
                mock_auto.assert_not_called()

    def test_use_accessible_output_property(self, handler):
        """Test use_accessible_output property."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = True
            assert handler.use_accessible_output is True

            mock_conf.return_value.conversation.use_accessible_output = False
            assert handler.use_accessible_output is False

    def test_accessible_output_property_lazy_initialization(self):
        """Test that accessible_output property initializes when needed."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = False
            handler = AccessibleOutputHandler()

            # Initially None
            assert handler._accessible_output is None

            # Should initialize when accessed if config changes
            mock_conf.return_value.conversation.use_accessible_output = True
            with patch('accessible_output3.outputs.auto.Auto') as mock_auto:
                _ = handler.accessible_output
                mock_auto.assert_called_once()

class TestTextCleaning:
    """Test text cleaning functionality for markdown removal."""

    def test_clean_steps_property_cached(self, handler):
        """Test that clean_steps property is cached."""
        steps1 = handler.clean_steps
        steps2 = handler.clean_steps
        assert steps1 is steps2  # Should be the same object due to caching

    def test_clean_steps_structure(self, handler):
        """Test that clean_steps returns properly structured data."""
        steps = handler.clean_steps
        assert isinstance(steps, list)
        assert len(steps) > 0

        for step in steps:
            assert isinstance(step, tuple)
            assert len(step) == 2
            # First element should be regex pattern or string
            assert isinstance(step[0], (re.Pattern, str))
            # Second element should be replacement string
            assert isinstance(step[1], str)

    def test_clear_for_speak_bold_text(self, handler):
        """Test removal of bold markdown."""
        text = "This is **bold** text"
        result = handler.clear_for_speak(text)
        assert result == "This is bold text"

        text = "This is __bold__ text"
        result = handler.clear_for_speak(text)
        assert result == "This is bold text"

    def test_clear_for_speak_italic_text(self, handler):
        """Test removal of italic markdown."""
        text = "This is *italic* text"
        result = handler.clear_for_speak(text)
        assert result == "This is italic text"

        text = "This is _italic_ text"
        result = handler.clear_for_speak(text)
        assert result == "This is italic text"

    def test_clear_for_speak_links(self, handler):
        """Test removal of link markdown."""
        text = "Visit [Google](https://google.com) for search"
        result = handler.clear_for_speak(text)
        assert result == "Visit Google for search"

    def test_clear_for_speak_images(self, handler):
        """Test removal of image markdown."""
        text = "Here is an image: ![Alt text](image.jpg)"
        result = handler.clear_for_speak(text)
        assert result == "Here is an image: Alt text"

        text = "Here is an image: ![](image.jpg)"
        result = handler.clear_for_speak(text)
        assert result == "Here is an image: "

    def test_clear_for_speak_headers(self, handler):
        """Test removal of header markdown."""
        text = "# Header 1\n## Header 2\n### Header 3"
        result = handler.clear_for_speak(text)
        assert result == "Header 1\nHeader 2\nHeader 3"

    def test_clear_for_speak_blockquotes(self, handler):
        """Test removal of blockquote markdown."""
        text = "> This is a quote\n> Another line"
        result = handler.clear_for_speak(text)
        assert result == "This is a quote\nAnother line"

    def test_clear_for_speak_horizontal_rules(self, handler):
        """Test removal of horizontal rules."""
        text = "Text above\n---\nText below"
        result = handler.clear_for_speak(text)
        assert result == "Text above\n\nText below"

    def test_clear_for_speak_complex_markdown(self, handler, markdown_text):
        """Test cleaning complex markdown with multiple elements."""
        result = handler.clear_for_speak(markdown_text)

        # Should remove all markdown formatting
        assert "**" not in result
        assert "*" not in result
        assert "__" not in result
        assert "_" not in result
        assert "[" not in result
        assert "]" not in result
        assert "(" not in result
        assert ")" not in result
        assert "#" not in result
        assert ">" not in result
        assert "---" not in result

        # Should preserve actual text content
        assert "Header" in result
        assert "Bold text" in result
        assert "italic text" in result
        assert "Link text" in result
        assert "Alt text" in result
        assert "Blockquote text" in result
        assert "Regular text" in result

    def test_clear_for_speak_empty_string(self, handler):
        """Test cleaning empty string."""
        result = handler.clear_for_speak("")
        assert result == ""

    def test_clear_for_speak_plain_text(self, handler):
        """Test cleaning plain text without markdown."""
        text = "This is plain text with no markdown"
        result = handler.clear_for_speak(text)
        assert result == text

class TestHandleMethod:
    """Test the main handle method for accessible output."""

    def test_handle_basic_speech(self, handler, sample_text):
        """Test basic speech output."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(sample_text)
            mock_output.speak.assert_called_once()

    def test_handle_with_braille(self, handler, sample_text):
        """Test speech and braille output."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(sample_text, braille=True)
            mock_output.speak.assert_called_once()
            mock_output.braille.assert_called_once_with(sample_text)

    def test_handle_with_clear_for_speak_disabled(self, handler, markdown_text):
        """Test handle with clear_for_speak disabled."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(markdown_text, clear_for_speak=False)
            mock_output.speak.assert_called_once_with(markdown_text)

    def test_handle_with_clear_for_speak_enabled(self, handler, markdown_text):
        """Test handle with clear_for_speak enabled."""
        with patch.object(handler, 'accessible_output') as mock_output:
            with patch.object(handler, 'clear_for_speak') as mock_clear:
                mock_clear.return_value = "cleaned text"
                handler.handle(markdown_text, clear_for_speak=True)
                mock_clear.assert_called_once_with(markdown_text)
                mock_output.speak.assert_called_once_with("cleaned text")

    def test_handle_force_initialization(self, handler_disabled, sample_text):
        """Test force initialization when accessible output is disabled."""
        with patch.object(handler_disabled, '_init_accessible_output') as mock_init:
            handler_disabled.handle(sample_text, force=True)
            mock_init.assert_called_once_with(True)

    def test_handle_empty_text(self, handler):
        """Test handle with empty text."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle("")
            mock_output.speak.assert_not_called()
            mock_output.braille.assert_not_called()

    def test_handle_whitespace_only_text(self, handler):
        """Test handle with whitespace-only text."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle("   \n\t  ")
            mock_output.speak.assert_not_called()
            mock_output.braille.assert_not_called()

    def test_handle_non_string_input(self, handler):
        """Test handle with non-string input."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(123)
            mock_output.speak.assert_not_called()
            mock_output.braille.assert_not_called()

    def test_handle_none_input(self, handler):
        """Test handle with None input."""
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(None)
            mock_output.speak.assert_not_called()
            mock_output.braille.assert_not_called()

    def test_handle_speech_exception(self, handler, sample_text):
        """Test graceful handling of speech exceptions."""
        with patch.object(handler, 'accessible_output') as mock_output:
            mock_output.speak.side_effect = Exception("Speech failed")
            with patch('basilisk.accessible_output.log') as mock_log:
                handler.handle(sample_text)
                mock_log.error.assert_called()

    def test_handle_braille_exception(self, handler, sample_text):
        """Test graceful handling of braille exceptions."""
        with patch.object(handler, 'accessible_output') as mock_output:
            mock_output.braille.side_effect = Exception("Braille failed")
            with patch('basilisk.accessible_output.log') as mock_log:
                handler.handle(sample_text, braille=True)
                mock_log.error.assert_called()
                # Speech should still work
                mock_output.speak.assert_called_once()

    def test_handle_disabled_accessible_output_no_force(self, handler_disabled, sample_text):
        """Test handle when accessible output is disabled without force."""
        with patch.object(handler_disabled, 'accessible_output') as mock_output:
            handler_disabled.handle(sample_text)
            mock_output.speak.assert_not_called()

class TestStreamBuffer:
    """Test speech stream buffer functionality."""

    def test_handle_stream_buffer_empty_input(self, handler):
        """Test stream buffer with empty input."""
        handler.speech_stream_buffer = "previous text"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer("")
            mock_handle.assert_called_once_with("previous text", clear_for_speak=True)
            assert handler.speech_stream_buffer == ""

    def test_handle_stream_buffer_none_input(self, handler):
        """Test stream buffer with None input."""
        handler.speech_stream_buffer = "previous text"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer(None)
            mock_handle.assert_called_once_with("previous text", clear_for_speak=True)
            assert handler.speech_stream_buffer == ""

    def test_handle_stream_buffer_non_string_input(self, handler):
        """Test stream buffer with non-string input."""
        handler.speech_stream_buffer = "previous text"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer(123)
            mock_handle.assert_called_once_with("previous text", clear_for_speak=True)
            assert handler.speech_stream_buffer == ""

    def test_handle_stream_buffer_no_punctuation(self, handler):
        """Test stream buffer with text containing no punctuation."""
        handler.speech_stream_buffer = "previous"
        handler.handle_stream_buffer(" text without punctuation")
        assert handler.speech_stream_buffer == "previous text without punctuation"

    def test_handle_stream_buffer_with_punctuation(self, handler):
        """Test stream buffer with text containing punctuation."""
        handler.speech_stream_buffer = "Hello"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer(" world! This continues")
            mock_handle.assert_called_once_with("Hello world!", clear_for_speak=True)
            assert handler.speech_stream_buffer == "This continues"

    def test_handle_stream_buffer_multiple_punctuation(self, handler):
        """Test stream buffer with multiple punctuation marks."""
        handler.speech_stream_buffer = "Start"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer(" sentence. Another sentence! Final.")
            # Should use the last punctuation match
            mock_handle.assert_called_once_with("Start sentence. Another sentence! Final.", clear_for_speak=True)
            assert handler.speech_stream_buffer == ""

    def test_handle_stream_buffer_with_newline(self, handler):
        """Test stream buffer with newline characters."""
        handler.speech_stream_buffer = "Line one"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer("\nLine two continues")
            mock_handle.assert_called_once_with("Line one\n", clear_for_speak=True)
            assert handler.speech_stream_buffer == "Line two continues"

    def test_handle_stream_buffer_regex_patterns(self, handler):
        """Test stream buffer with various regex patterns from COMMON_PATTERN."""
        test_cases = [
            ("Hello.", ""),
            ("Hello!", ""),
            ("Hello?", ""),
            ("Hello;", ""),
            ("Hello:", ""),
            ("Hello,", " continues"),
            ("Hello\n", "next line"),
        ]

        for input_text, expected_remaining in test_cases:
            handler.speech_stream_buffer = ""
            full_input = input_text + expected_remaining
            with patch.object(handler, 'handle') as mock_handle:
                handler.handle_stream_buffer(full_input)
                if expected_remaining:
                    mock_handle.assert_called_once_with(input_text, clear_for_speak=True)
                    assert handler.speech_stream_buffer.strip() == expected_remaining.strip()
                else:
                    mock_handle.assert_called_once_with(input_text, clear_for_speak=True)
                    assert handler.speech_stream_buffer == ""

    def test_handle_stream_buffer_regex_error(self, handler):
        """Test stream buffer handles regex errors gracefully."""
        handler.speech_stream_buffer = "start"
        with patch('basilisk.accessible_output.RE_SPEECH_STREAM_BUFFER.finditer') as mock_finditer:
            mock_finditer.side_effect = re.error("Regex error")
            with patch('basilisk.accessible_output.log') as mock_log:
                handler.handle_stream_buffer(" new text")
                mock_log.error.assert_called()
                # Should fallback to concatenating
                assert handler.speech_stream_buffer == "start new text"

    def test_handle_stream_buffer_empty_buffer_flush(self, handler):
        """Test flushing empty buffer."""
        handler.speech_stream_buffer = ""
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer("")
            mock_handle.assert_not_called()

    def test_handle_stream_buffer_leading_whitespace_removal(self, handler):
        """Test that leading whitespace is removed from remaining buffer."""
        handler.speech_stream_buffer = "Hello"
        with patch.object(handler, 'handle') as mock_handle:
            handler.handle_stream_buffer(" world!    This has spaces")
            mock_handle.assert_called_once_with("Hello world!", clear_for_speak=True)
            assert handler.speech_stream_buffer == "This has spaces"  # Leading spaces stripped

class TestErrorHandlingAndEdgeCases:
    """Test error handling and edge cases."""

    def test_init_accessible_output_exception(self):
        """Test initialization when accessible_output3 raises exception."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = True
            with patch('accessible_output3.outputs.auto.Auto') as mock_auto:
                mock_auto.side_effect = Exception("Failed to initialize")
                with patch('basilisk.accessible_output.log') as mock_log:
                    handler = AccessibleOutputHandler()
                    # Should handle exception gracefully
                    assert handler is not None

    def test_handle_very_long_text(self, handler):
        """Test handling very long text."""
        long_text = "a" * 10000
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(long_text)
            mock_output.speak.assert_called_once()

    def test_handle_unicode_text(self, handler):
        """Test handling unicode characters."""
        unicode_text = "Hello 世界 🌍 مرحبا Привет"
        with patch.object(handler, 'accessible_output') as mock_output:
            handler.handle(unicode_text)
            mock_output.speak.assert_called_once()

    def test_clear_for_speak_regex_edge_cases(self, handler):
        """Test clear_for_speak with regex edge cases."""
        edge_cases = [
            "**nested **bold** text**",
            "*italic with *nested* italic*",
            "[link with [nested] link](url)",
            "![image with ![nested] image](url)",
            "# Header with **bold** and *italic*",
            "> Quote with **bold** and [link](url)",
        ]

        for text in edge_cases:
            result = handler.clear_for_speak(text)
            # Should not raise exceptions
            assert isinstance(result, str)

    def test_logging_messages(self, handler):
        """Test that appropriate log messages are generated."""
        with patch('basilisk.accessible_output.log') as mock_log:
            # Test debug logging for clean_steps
            _ = handler.clean_steps
            mock_log.debug.assert_called_with("Initializing clean steps")

            # Test error logging for speech failure
            with patch.object(handler, 'accessible_output') as mock_output:
                mock_output.speak.side_effect = Exception("Speech error")
                handler.handle("test")
                mock_log.error.assert_called_with("Failed to output text to screen reader", exc_info=mock_output.speak.side_effect)

    def test_measure_time_decorator(self):
        """Test that _init_accessible_output is decorated with measure_time."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            mock_conf.return_value.conversation.use_accessible_output = True
            with patch('accessible_output3.outputs.auto.Auto'):
                handler = AccessibleOutputHandler()
                # Check that the method has the measure_time decorator applied
                assert hasattr(handler._init_accessible_output, '__wrapped__')

class TestIntegrationScenarios:
    """Test integration scenarios and real-world usage patterns."""

    def test_typical_conversation_flow(self, handler):
        """Test typical conversation flow with streaming."""
        # Simulate a typical conversation with streaming text
        text_chunks = [
            "Hello",
            " user,",
            " how can I",
            " help you",
            " today?",
            "",  # End stream
        ]

        with patch.object(handler, 'handle') as mock_handle:
            for chunk in text_chunks:
                handler.handle_stream_buffer(chunk)

            # Should have called handle once when the question mark was encountered
            mock_handle.assert_called_once_with("Hello user, how can I help you today?", clear_for_speak=True)

    def test_mixed_handle_and_stream_usage(self, handler):
        """Test mixing direct handle calls with stream buffer usage."""
        with patch.object(handler, 'accessible_output') as mock_output:
            # Direct handle call
            handler.handle("Direct message")

            # Stream some text
            handler.handle_stream_buffer("Streaming")
            handler.handle_stream_buffer(" text.")

            # Another direct handle call
            handler.handle("Another direct message")

            # Should have made appropriate calls
            assert mock_output.speak.call_count >= 2

    def test_configuration_changes_during_runtime(self, handler):
        """Test behavior when configuration changes during runtime."""
        with patch('basilisk.accessible_output.config.conf') as mock_conf:
            # Initially enabled
            mock_conf.return_value.conversation.use_accessible_output = True
            with patch.object(handler, 'accessible_output') as mock_output:
                handler.handle("Test message 1")
                mock_output.speak.assert_called()

            # Disable during runtime
            mock_conf.return_value.conversation.use_accessible_output = False
            with patch.object(handler, 'accessible_output') as mock_output:
                handler.handle("Test message 2")
                # Should not call speak when disabled
                mock_output.speak.assert_not_called()

if __name__ == "__main__":
    pytest.main([__file__, "-v"])