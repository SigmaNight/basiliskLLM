"""Comprehensive unit tests for basilisk.completion_handler module.

This test suite covers all functionality of CompletionHandler including:
- Initialization with various callback configurations
- Streaming and non-streaming completion handling
- Error scenarios and exception handling
- Threading behavior and concurrency
- Buffer management and stream processing
- External dependency mocking

Testing framework: pytest (version ^8.4.0)
"""

import pytest
import threading
import time
from unittest.mock import Mock, MagicMock, patch, call, AsyncMock
from typing import Optional, Any, Generator

from basilisk.completion_handler import CompletionHandler, COMMON_PATTERN, RE_STREAM_BUFFER
from basilisk.conversation.conversation_model import (
    Conversation,
    Message,
    MessageBlock,
    MessageRoleEnum,
    SystemMessage,
)

@pytest.fixture
def mock_engine():
    """Mock BaseEngine for testing."""
    engine = Mock()
    engine.completion.return_value = "mock_response"
    engine.completion_response_with_stream.return_value = iter(["chunk1", "chunk2", "chunk3"])
    engine.completion_response_without_stream.return_value = Mock()
    return engine

@pytest.fixture
def sample_conversation():
    """Sample conversation for testing."""
    conversation = Mock(spec=Conversation)
    conversation.messages = [
        Message(role=MessageRoleEnum.USER, content="Test message")
    ]
    return conversation

@pytest.fixture
def sample_message_block():
    """Sample MessageBlock for testing."""
    block = Mock(spec=MessageBlock)
    block.response = Mock()
    block.response.content = ""
    block.response.citations = None
    return block

@pytest.fixture
def sample_system_message():
    """Sample SystemMessage for testing."""
    return Mock(spec=SystemMessage)

@pytest.fixture
def callback_mocks():
    """Dictionary of callback mocks for CompletionHandler."""
    return {
        'on_completion_start': Mock(),
        'on_completion_end': Mock(),
        'on_stream_chunk': Mock(),
        'on_error': Mock(),
        'on_stream_start': Mock(),
        'on_stream_finish': Mock(),
        'on_non_stream_finish': Mock(),
    }

class TestCompletionHandlerInitialization:
    """Test CompletionHandler initialization scenarios."""
    
    def test_initialization_with_no_callbacks(self):
        """Test CompletionHandler initializes correctly with no callbacks."""
        handler = CompletionHandler()
        
        assert handler.on_completion_start is None
        assert handler.on_completion_end is None
        assert handler.on_stream_chunk is None
        assert handler.on_error is None
        assert handler.on_stream_start is None
        assert handler.on_stream_finish is None
        assert handler.on_non_stream_finish is None
        assert handler.task is None
        assert handler._stop_completion is False
        assert handler.last_time == 0
        assert handler.stream_buffer == ""
    
    def test_initialization_with_all_callbacks(self, callback_mocks):
        """Test CompletionHandler initializes correctly with all callbacks."""
        handler = CompletionHandler(**callback_mocks)
        
        assert handler.on_completion_start == callback_mocks['on_completion_start']
        assert handler.on_completion_end == callback_mocks['on_completion_end']
        assert handler.on_stream_chunk == callback_mocks['on_stream_chunk']
        assert handler.on_error == callback_mocks['on_error']
        assert handler.on_stream_start == callback_mocks['on_stream_start']
        assert handler.on_stream_finish == callback_mocks['on_stream_finish']
        assert handler.on_non_stream_finish == callback_mocks['on_non_stream_finish']
    
    def test_initialization_with_partial_callbacks(self):
        """Test CompletionHandler initializes correctly with partial callbacks."""
        on_start = Mock()
        on_error = Mock()
        
        handler = CompletionHandler(
            on_completion_start=on_start,
            on_error=on_error
        )
        
        assert handler.on_completion_start == on_start
        assert handler.on_error == on_error
        assert handler.on_completion_end is None
        assert handler.on_stream_chunk is None

class TestCompletionHandlerExecution:
    """Test CompletionHandler execution scenarios."""
    
    @patch('basilisk.completion_handler.threading.Thread')
    @patch('basilisk.completion_handler.logger')
    def test_start_completion_non_streaming_success(self, mock_logger, mock_thread, 
                                                   mock_engine, sample_conversation, 
                                                   sample_message_block, callback_mocks):
        """Test successful non-streaming completion."""
        handler = CompletionHandler(**callback_mocks)
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        handler.start_completion(
            engine=mock_engine,
            system_message=None,
            conversation=sample_conversation,
            new_block=sample_message_block,
            stream=False
        )
        
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        callback_mocks['on_completion_start'].assert_called_once()
        assert handler._stop_completion is False

    @patch('basilisk.completion_handler.threading.Thread')
    def test_start_completion_streaming_success(self, mock_thread, mock_engine, 
                                               sample_conversation, sample_message_block, 
                                               callback_mocks):
        """Test successful streaming completion."""
        handler = CompletionHandler(**callback_mocks)
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        handler.start_completion(
            engine=mock_engine,
            system_message=None,
            conversation=sample_conversation,
            new_block=sample_message_block,
            stream=True
        )
        
        mock_thread.assert_called_once()
        mock_thread_instance.start.assert_called_once()
        callback_mocks['on_completion_start'].assert_called_once()

    @patch('basilisk.completion_handler.threading.Thread')
    def test_start_completion_with_kwargs(self, mock_thread, mock_engine, 
                                          sample_conversation, sample_message_block):
        """Test start_completion passes through additional kwargs."""
        handler = CompletionHandler()
        mock_thread_instance = Mock()
        mock_thread.return_value = mock_thread_instance
        
        custom_param = "test_value"
        handler.start_completion(
            engine=mock_engine,
            system_message=None,
            conversation=sample_conversation,
            new_block=sample_message_block,
            stream=False,
            custom_param=custom_param
        )
        
        call_kwargs = mock_thread.call_args[1]['kwargs']
        assert call_kwargs['custom_param'] == custom_param

class TestCompletionHandlerControl:
    """Test CompletionHandler control methods (stop, is_running)."""
    
    def test_is_running_with_no_task(self):
        handler = CompletionHandler()
        assert handler.is_running() is False
        
    def test_is_running_with_dead_task(self):
        handler = CompletionHandler()
        mock_task = Mock()
        mock_task.is_alive.return_value = False
        handler.task = mock_task
        assert handler.is_running() is False
        
    def test_is_running_with_alive_task(self):
        handler = CompletionHandler()
        mock_task = Mock()
        mock_task.is_alive.return_value = True
        handler.task = mock_task
        assert handler.is_running() is True
        
    @patch('basilisk.completion_handler.wx.CallAfter')
    def test_stop_completion_with_running_task(self, mock_call_after, callback_mocks):
        handler = CompletionHandler(**callback_mocks)
        mock_task = Mock()
        mock_task.is_alive.return_value = True
        handler.task = mock_task
        
        handler.stop_completion()
        
        assert handler._stop_completion is True
        mock_task.join.assert_called_once_with(timeout=0.05)
        assert handler.task is None
        mock_call_after.assert_called_once_with(callback_mocks['on_completion_end'], False)
        
    def test_stop_completion_with_no_running_task(self, callback_mocks):
        handler = CompletionHandler(**callback_mocks)
        handler.task = None
        
        with patch('basilisk.completion_handler.wx.CallAfter') as mock_call_after:
            handler.stop_completion()
            mock_call_after.assert_called_with(callback_mocks['on_completion_end'], False)

class TestCompletionHandlerStreaming:
    """Test CompletionHandler streaming functionality."""
    
    def test_handle_stream_chunk_with_string(self, sample_message_block):
        handler = CompletionHandler()
        initial_buffer = "initial"
        handler.stream_buffer = initial_buffer
        
        chunk = " additional"
        handler._handle_stream_chunk(chunk, sample_message_block)
        assert handler.stream_buffer == initial_buffer + chunk
        
    def test_handle_stream_chunk_with_citation_tuple(self, sample_message_block):
        handler = CompletionHandler()
        sample_message_block.response.citations = None
        
        citation_data = {"source": "test", "url": "http://example.com"}
        chunk = ("citation", citation_data)
        handler._handle_stream_chunk(chunk, sample_message_block)
        assert sample_message_block.response.citations == [citation_data]
        
    def test_handle_stream_chunk_with_unknown_tuple_type(self, sample_message_block):
        handler = CompletionHandler()
        with patch('basilisk.completion_handler.logger.warning') as mock_warning:
            chunk = ("unknown_type", "data")
            handler._handle_stream_chunk(chunk, sample_message_block)
            mock_warning.assert_called_once()
            
    @patch('basilisk.completion_handler.wx.CallAfter')
    def test_flush_stream_buffer_with_content(self, mock_call_after, sample_message_block, callback_mocks):
        handler = CompletionHandler(**callback_mocks)
        handler.stream_buffer = "test content"
        sample_message_block.response.content = "existing"
        
        handler.flush_stream_buffer(sample_message_block)
        assert sample_message_block.response.content == "existingtest content"
        assert handler.stream_buffer == ""
        mock_call_after.assert_called_once_with(handler._handle_stream_buffer, "test content")
        
    def test_flush_stream_buffer_with_empty_buffer(self, sample_message_block):
        handler = CompletionHandler()
        handler.stream_buffer = ""
        sample_message_block.response.content = "existing"
        
        handler.flush_stream_buffer(sample_message_block)
        assert sample_message_block.response.content == "existing"
        assert handler.stream_buffer == ""
        
    @patch.object(CompletionHandler, 'flush_stream_buffer')
    def test_handle_stream_chunk_triggers_flush_on_pattern_match(self, mock_flush, sample_message_block):
        handler = CompletionHandler()
        handler.stream_buffer = "content with period."
        
        handler._handle_stream_chunk("", sample_message_block)
        mock_flush.assert_called_once_with(sample_message_block)

class TestCompletionHandlerErrorHandling:
    """Test CompletionHandler error scenarios and edge cases."""
    
    @patch('basilisk.completion_handler.wx.CallAfter')
    @patch('basilisk.completion_handler.stop_sound')
    def test_handle_error_with_custom_callback(self, mock_stop_sound, mock_call_after):
        error_callback = Mock()
        handler = CompletionHandler(on_error=error_callback)
        handler._handle_error("Test error")
        
        mock_stop_sound.assert_called_once()
        error_callback.assert_called_once_with("Test error")
        
    @patch('basilisk.completion_handler.wx.MessageBox')
    @patch('basilisk.completion_handler.wx.CallAfter')
    @patch('basilisk.completion_handler.stop_sound')
    def test_handle_error_without_custom_callback(self, mock_stop_sound, mock_call_after, mock_message_box):
        handler = CompletionHandler()
        handler._handle_error("Test error")
        
        mock_stop_sound.assert_called_once()
        assert mock_message_box.called
        
    @patch('basilisk.completion_handler.play_sound')
    @patch('basilisk.completion_handler.wx.CallAfter')
    def test_handle_completion_engine_exception(self, mock_call_after, mock_play_sound, mock_engine):
        mock_engine.completion.side_effect = Exception("Engine error")
        handler = CompletionHandler()
        
        handler._handle_completion(mock_engine, stream=False)
        mock_call_after.assert_called()
        call_args = mock_call_after.call_args[0]
        assert call_args[0] == handler._handle_error
        
    @patch('basilisk.completion_handler.global_vars')
    def test_streaming_completion_stops_on_app_exit(self, mock_global_vars, mock_engine, sample_message_block):
        mock_global_vars.app_should_exit = True
        handler = CompletionHandler()
        
        result = handler._handle_streaming_completion(
            engine=mock_engine,
            response="mock_response", 
            new_block=sample_message_block,
            system_message=None
        )
        assert result is False
        
    def test_streaming_completion_stops_on_stop_flag(self, mock_engine, sample_message_block):
        handler = CompletionHandler()
        handler._stop_completion = True
        
        result = handler._handle_streaming_completion(
            engine=mock_engine,
            response="mock_response",
            new_block=sample_message_block, 
            system_message=None
        )
        assert result is False

class TestCompletionHandlerPerformance:
    """Test CompletionHandler performance and threading behavior."""
    
    @patch('basilisk.completion_handler.time.time')
    @patch('basilisk.completion_handler.play_sound')
    def test_handle_stream_buffer_sound_timing(self, mock_play_sound, mock_time, callback_mocks):
        handler = CompletionHandler(**callback_mocks)
        handler.last_time = 0
        
        mock_time.return_value = 5
        handler._handle_stream_buffer("test buffer")
        mock_play_sound.assert_called_with("chat_response_pending")
        assert handler.last_time == 5
        
        mock_play_sound.reset_mock()
        mock_time.return_value = 7
        handler._handle_stream_buffer("test buffer")
        mock_play_sound.assert_not_called()
        
    def test_concurrent_start_stop_completion(self, mock_engine, sample_conversation, sample_message_block):
        handler = CompletionHandler()
        with patch.object(handler, 'is_running', return_value=False):
            with patch('basilisk.completion_handler.threading.Thread') as mock_thread:
                mock_thread_instance = Mock()
                mock_thread.return_value = mock_thread_instance
                
                handler.start_completion(
                    engine=mock_engine,
                    system_message=None,
                    conversation=sample_conversation,
                    new_block=sample_message_block
                )
                
                handler.task = mock_thread_instance
                mock_thread_instance.is_alive.return_value = True
                
                handler.stop_completion()
                assert handler._stop_completion is True
                mock_thread_instance.join.assert_called_once()
                
    @pytest.mark.parametrize("buffer_content,should_flush", [
        ("content with period.", True),
        ("content with question?", True),
        ("content with exclamation!", True),
        ("content with newline\n", True),
        ("content with semicolon;", True),
        ("content with colon:", True),
        ("content without trigger", False),
        ("", False),
    ])
    def test_stream_buffer_pattern_matching(self, buffer_content, should_flush, sample_message_block):
        handler = CompletionHandler()
        handler.stream_buffer = buffer_content
        
        with patch.object(handler, 'flush_stream_buffer') as mock_flush:
            handler._handle_stream_chunk("", sample_message_block)
            if should_flush:
                mock_flush.assert_called_once()
            else:
                mock_flush.assert_not_called()

class TestCompletionHandlerIntegration:
    """Integration tests for complete CompletionHandler workflows."""
    
    @patch('basilisk.completion_handler.wx.CallAfter')
    @patch('basilisk.completion_handler.play_sound')
    @patch('basilisk.completion_handler.stop_sound')
    def test_complete_streaming_workflow(self, mock_stop_sound, mock_play_sound, 
                                        mock_call_after, mock_engine, sample_conversation,
                                        sample_message_block, sample_system_message, callback_mocks):
        stream_chunks = ["Hello", " world", "!"]
        mock_engine.completion_response_with_stream.return_value = iter(stream_chunks)
        
        handler = CompletionHandler(**callback_mocks)
        success = handler._handle_streaming_completion(
            engine=mock_engine,
            response="mock_response",
            new_block=sample_message_block,
            system_message=sample_system_message
        )
        assert success is True
        assert sample_message_block.response.content == "Hello world!"
        mock_call_after.assert_any_call(callback_mocks['on_stream_start'], sample_message_block, sample_system_message)
        mock_call_after.assert_any_call(callback_mocks['on_stream_finish'], sample_message_block)
                                       
    @patch('basilisk.completion_handler.wx.CallAfter')
    def test_complete_non_streaming_workflow(self, mock_call_after, mock_engine, 
                                            sample_conversation, sample_message_block,
                                            sample_system_message, callback_mocks):
        completed_block = Mock()
        mock_engine.completion_response_without_stream.return_value = completed_block
        
        handler = CompletionHandler(**callback_mocks)
        success = handler._handle_non_streaming_completion(
            engine=mock_engine,
            response="mock_response",
            new_block=sample_message_block,
            system_message=sample_system_message
        )
        assert success is True
        mock_call_after.assert_called_with(callback_mocks['on_non_stream_finish'], completed_block, sample_system_message)
                                         
    @patch('basilisk.completion_handler.wx.CallAfter')
    @patch('basilisk.completion_handler.play_sound')
    @patch('basilisk.completion_handler.stop_sound')
    def test_error_recovery_workflow(self, mock_stop_sound, mock_play_sound, 
                                     mock_call_after, mock_engine, callback_mocks):
        mock_engine.completion.side_effect = Exception("Network error")
        
        handler = CompletionHandler(**callback_mocks)
        handler._handle_completion(mock_engine, stream=False)
        
        mock_stop_sound.assert_called_once()
        mock_call_after.assert_called()
        call_args = mock_call_after.call_args[0]
        assert call_args[0] == handler._handle_error

class TestCompletionHandlerEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_large_stream_buffer_handling(self, sample_message_block):
        handler = CompletionHandler()
        large_content = "x" * 10000
        handler.stream_buffer = large_content
        handler.flush_stream_buffer(sample_message_block)
        assert sample_message_block.response.content == large_content
        assert handler.stream_buffer == ""
        
    def test_unicode_content_handling(self, sample_message_block):
        handler = CompletionHandler()
        unicode_content = "Hello 世界! 🌍 café naïve résumé"
        handler.stream_buffer = unicode_content
        handler.flush_stream_buffer(sample_message_block)
        assert sample_message_block.response.content == unicode_content
        
    def test_multiple_citations_handling(self, sample_message_block):
        handler = CompletionHandler()
        sample_message_block.response.citations = []
        citations = [
            {"source": "source1", "url": "http://example1.com"},
            {"source": "source2", "url": "http://example2.com"},
        ]
        for citation in citations:
            handler._handle_stream_chunk(("citation", citation), sample_message_block)
        assert sample_message_block.response.citations == citations
        
    def test_completion_with_none_values(self, mock_engine, sample_conversation, sample_message_block):
        handler = CompletionHandler()
        success = handler._handle_non_streaming_completion(
            engine=mock_engine,
            response="mock_response",
            new_block=sample_message_block,
            system_message=None
        )
        assert success is True

pytestmark = [
    pytest.mark.unit,
    pytest.mark.completion_handler,
]

class TestRegexPatterns:
    """Test the regex patterns used in completion_handler."""
    
    @pytest.mark.parametrize("test_string,should_match", [
        ("content with period.", True),
        ("content with question?", True),
        ("content with exclamation!", True),
        ("content with newline\n", True),
        ("content with semicolon;", True),
        ("content with colon:", True),
        ("content with quote\"", True),
        ("content with bracket]", True),
        ("content with paren)", True),
        ("content with guillemet»", True),
        ("just content", False),
        ("", False),
        ("content.", True),
        (".content", True),
    ])
    def test_common_pattern_regex(self, test_string, should_match):
        import re
        pattern = re.compile(rf".*{COMMON_PATTERN}.*")
        if should_match:
            assert pattern.match(test_string)
        else:
            assert not pattern.match(test_string)
            
    def test_re_stream_buffer_pattern(self):
        assert RE_STREAM_BUFFER.match("content.")
        assert not RE_STREAM_BUFFER.match("content")

def pytest_configure():
    """Configure pytest for completion_handler tests."""
    pytest.register_assert_rewrite("basilisk.completion_handler")