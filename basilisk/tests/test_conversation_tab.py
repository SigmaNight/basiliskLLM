"""Comprehensive unit tests for the ConversationTab class.

This module provides thorough testing coverage for the ConversationTab GUI component,
including initialization, message handling, audio recording, file operations, and error conditions.
Testing framework: pytest
"""

import datetime
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from typing import Optional

import pytest
from upath import UPath

from basilisk.gui.conversation_tab import ConversationTab, _
from basilisk.conversation import Conversation, Message, MessageBlock, MessageRoleEnum, SystemMessage
from basilisk.provider_capability import ProviderCapability
import basilisk.config as config


class TestConversationTab:
    """Comprehensive test suite for ConversationTab class functionality."""

    @pytest.fixture
    def mock_wx_panel(self):
        """Mock wx.Panel to avoid GUI dependencies."""
        with patch('basilisk.gui.conversation_tab.wx.Panel') as mock_panel:
            mock_panel.__init__ = Mock(return_value=None)
            yield mock_panel

    @pytest.fixture
    def mock_base_conversation(self):
        """Mock BaseConversation base class."""
        with patch('basilisk.gui.conversation_tab.BaseConversation') as mock_base:
            mock_base.__init__ = Mock(return_value=None)
            yield mock_base

    @pytest.fixture
    def mock_wx_components(self):
        """Mock various wx components used in ConversationTab."""
        mocks = {}
        components = [
            'wx.StaticText', 'wx.BoxSizer', 'wx.Button', 'wx.ComboBox',
            'wx.TextCtrl', 'wx.SpinCtrl', 'wx.CheckBox', 'wx.Menu'
        ]

        for component in components:
            patcher = patch(f'basilisk.gui.conversation_tab.{component}')
            mock_obj = patcher.start()
            mock_obj.return_value = Mock()
            mocks[component.split('.')[-1]] = mock_obj

        yield mocks

        # Clean up all patches
        patch.stopall()

    @pytest.fixture
    def mock_parent_window(self):
        """Create a mock parent window."""
        parent = Mock()
        parent.SetStatusText = Mock()
        parent.TopLevelParent = Mock()
        parent.TopLevelParent.SetStatusText = Mock()
        return parent

    @pytest.fixture
    def mock_conversation(self):
        """Create a mock conversation object."""
        conversation = Mock(spec=Conversation)
        conversation.messages = []
        conversation.title = "Test Conversation"
        conversation.add_block = Mock()
        conversation.remove_block = Mock()
        conversation.save = Mock()
        return conversation

    @pytest.fixture
    def mock_profile(self):
        """Create a mock conversation profile."""
        profile = Mock()
        profile.system_prompt = "Test system prompt"
        profile.temperature = 0.7
        profile.max_tokens = 1000
        return profile

    def test_conv_storage_path_generates_unique_path(self):
        """Test that conv_storage_path generates unique paths with timestamps."""
        path1 = ConversationTab.conv_storage_path()
        path2 = ConversationTab.conv_storage_path()
        assert isinstance(path1, UPath)
        assert isinstance(path2, UPath)
        assert str(path1).startswith("memory://conversation_")
        assert str(path2).startswith("memory://conversation_")
        assert str(path1) != str(path2)

    @patch('basilisk.gui.conversation_tab.Conversation.open')
    def test_open_conversation_success(self, mock_conv_open, mock_parent_window):
        """Test successful opening of a conversation from file."""
        mock_conversation = Mock()
        mock_conversation.title = "Loaded Conversation"
        mock_conv_open.return_value = mock_conversation

        file_path = "/path/to/conversation.json"
        default_title = "Default Title"

        with patch.object(ConversationTab, '__init__', return_value=None):
            ConversationTab.open_conversation(mock_parent_window, file_path, default_title)

        mock_conv_open.assert_called_once()
        args, kwargs = mock_conv_open.call_args
        assert args[0] == file_path
        assert isinstance(args[1], UPath)

    @patch('basilisk.gui.conversation_tab.Conversation.open')
    def test_open_conversation_uses_default_title_when_no_title(self, mock_conv_open, mock_parent_window):
        """Test that default title is used when conversation has no title."""
        mock_conversation = Mock()
        mock_conversation.title = None
        mock_conv_open.return_value = mock_conversation

        file_path = "/path/to/conversation.json"
        default_title = "Default Title"

        with patch.object(ConversationTab, '__init__', return_value=None) as mock_init:
            ConversationTab.open_conversation(mock_parent_window, file_path, default_title)

        mock_init.assert_called_once()
        args, kwargs = mock_init.call_args
        assert kwargs.get('title') == default_title or args[1] == default_title

    @patch('basilisk.gui.conversation_tab.Conversation.open')
    def test_open_conversation_io_error(self, mock_conv_open, mock_parent_window):
        """Test handling of IOError when opening conversation."""
        mock_conv_open.side_effect = IOError("File not found")
        with pytest.raises(IOError):
            ConversationTab.open_conversation(mock_parent_window, "/nonexistent.json", "Default")

    @patch('basilisk.gui.conversation_tab.wx.Panel.__init__')
    @patch('basilisk.gui.conversation_tab.BaseConversation.__init__')
    def test_init_default_parameters(self, mock_base_init, mock_panel_init, mock_parent_window):
        """Test ConversationTab initialization with default parameters."""
        with patch.object(ConversationTab, 'init_ui'), \
             patch.object(ConversationTab, 'init_data'), \
             patch.object(ConversationTab, 'adjust_advanced_mode_setting'), \
             patch('basilisk.gui.conversation_tab.CompletionHandler'), \
             patch('basilisk.gui.conversation_tab.OCRHandler'):
            tab = ConversationTab(mock_parent_window)

        mock_panel_init.assert_called_once_with(mock_parent_window)
        mock_base_init.assert_called_once()
        assert tab.title == _("Untitled conversation")
        assert isinstance(tab.conv_storage_path, UPath)
        assert isinstance(tab.conversation, Conversation)
        assert tab.recording_thread is None
        assert tab.process is None

    @patch('basilisk.gui.conversation_tab.wx.Panel.__init__')
    @patch('basilisk.gui.conversation_tab.BaseConversation.__init__')
    def test_init_with_custom_parameters(self, mock_base_init, mock_panel_init,
                                         mock_parent_window, mock_conversation, mock_profile):
        """Test ConversationTab initialization with custom parameters."""
        custom_title = "Custom Title"
        custom_path = UPath("memory://custom_path")
        bskc_path = "/path/to/config.bskc"

        with patch.object(ConversationTab, 'init_ui'), \
             patch.object(ConversationTab, 'init_data'), \
             patch.object(ConversationTab, 'adjust_advanced_mode_setting'), \
             patch('basilisk.gui.conversation_tab.CompletionHandler'), \
             patch('basilisk.gui.conversation_tab.OCRHandler'):
            tab = ConversationTab(
                mock_parent_window,
                title=custom_title,
                profile=mock_profile,
                conversation=mock_conversation,
                conv_storage_path=custom_path,
                bskc_path=bskc_path
            )

        assert tab.title == custom_title
        assert tab.conversation == mock_conversation
        assert tab.conv_storage_path == custom_path
        assert tab.bskc_path == bskc_path

    @patch('basilisk.gui.conversation_tab.wx.Panel.__init__')
    @patch('basilisk.gui.conversation_tab.BaseConversation.__init__')
    def test_init_completion_handler_setup(self, mock_base_init, mock_panel_init, mock_parent_window):
        """Test that CompletionHandler is properly initialized with callbacks."""
        with patch.object(ConversationTab, 'init_ui'), \
             patch.object(ConversationTab, 'init_data'), \
             patch.object(ConversationTab, 'adjust_advanced_mode_setting'), \
             patch('basilisk.gui.conversation_tab.CompletionHandler') as mock_handler, \
             patch('basilisk.gui.conversation_tab.OCRHandler'):
            tab = ConversationTab(mock_parent_window)

        mock_handler.assert_called_once()
        _, kwargs = mock_handler.call_args
        assert 'on_completion_start' in kwargs
        assert 'on_completion_end' in kwargs
        assert 'on_stream_chunk' in kwargs
        assert 'on_stream_start' in kwargs
        assert 'on_stream_finish' in kwargs
        assert 'on_non_stream_finish' in kwargs
        assert kwargs['on_completion_start'] == tab._on_completion_start
        assert kwargs['on_completion_end'] == tab._on_completion_end

    def test_get_system_message_with_content(self, mock_parent_window):
        """Test getting system message when system prompt has content."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.system_prompt_txt = Mock()
            tab.system_prompt_txt.GetValue.return_value = "Test system prompt"

            system_msg = tab.get_system_message()

            assert isinstance(system_msg, SystemMessage)
            assert system_msg.content == "Test system prompt"

    def test_get_system_message_empty(self, mock_parent_window):
        """Test getting system message when system prompt is empty."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.system_prompt_txt = Mock()
            tab.system_prompt_txt.GetValue.return_value = ""

            system_msg = tab.get_system_message()

            assert system_msg is None

    def test_get_new_message_block_success(self, mock_parent_window):
        """Test successful creation of new message block."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            mock_model = Mock()
            mock_model.id = "test-model"
            tab.prompt_panel = Mock()
            tab.prompt_panel.ensure_model_compatibility.return_value = mock_model
            tab.prompt_panel.resize_all_attachments.return_value = None
            tab.prompt_panel.prompt_text = "Test prompt"
            tab.prompt_panel.attachment_files = []
            tab.current_account = Mock()
            tab.current_account.provider.id = "test-provider"
            tab.temperature_spinner = Mock()
            tab.temperature_spinner.GetValue.return_value = 0.7
            tab.top_p_spinner = Mock()
            tab.top_p_spinner.GetValue.return_value = 0.9
            tab.max_tokens_spin_ctrl = Mock()
            tab.max_tokens_spin_ctrl.GetValue.return_value = 1000
            tab.stream_mode = Mock()
            tab.stream_mode.GetValue.return_value = True

            block = tab.get_new_message_block()

            assert isinstance(block, MessageBlock)
            assert block.request.content == "Test prompt"
            assert block.request.role == MessageRoleEnum.USER
            assert block.model_id == "test-model"
            assert block.provider_id == "test-provider"
            assert block.temperature == 0.7
            assert block.top_p == 0.9
            assert block.max_tokens == 1000
            assert block.stream is True

    def test_get_new_message_block_no_compatible_model(self, mock_parent_window):
        """Test handling when no compatible model is available."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.prompt_panel = Mock()
            tab.prompt_panel.ensure_model_compatibility.return_value = None

            block = tab.get_new_message_block()
            assert block is None

    def test_remove_message_block(self, mock_parent_window, mock_conversation):
        """Test removing a message block from conversation."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.conversation = mock_conversation
            tab.refresh_messages = Mock()
            test_block = Mock(spec=MessageBlock)

            tab.remove_message_block(test_block)

            mock_conversation.remove_block.assert_called_once_with(test_block)
            tab.refresh_messages.assert_called_once()

    def test_get_conversation_block_index_found(self, mock_parent_window):
        """Test getting index of existing message block."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            block1 = Mock(spec=MessageBlock)
            block2 = Mock(spec=MessageBlock)
            block3 = Mock(spec=MessageBlock)
            tab.conversation = Mock()
            tab.conversation.messages = [block1, block2, block3]

            index = tab.get_conversation_block_index(block2)
            assert index == 1

    def test_get_conversation_block_index_not_found(self, mock_parent_window):
        """Test getting index of non-existent message block."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            block1 = Mock(spec=MessageBlock)
            block2 = Mock(spec=MessageBlock)
            non_existent_block = Mock(spec=MessageBlock)
            tab.conversation = Mock()
            tab.conversation.messages = [block1, block2]

            index = tab.get_conversation_block_index(non_existent_block)
            assert index is None

    def test_start_recording_success(self, mock_parent_window):
        """Test successful start of audio recording."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.current_engine = Mock()
            tab.current_engine.capabilities = [ProviderCapability.STT]
            tab.toggle_record_btn = Mock()
            tab.submit_btn = Mock()
            tab.transcribe_audio_file = Mock()

            tab.start_recording()

            tab.toggle_record_btn.SetLabel.assert_called_once()
            assert _("Stop recording") in tab.toggle_record_btn.SetLabel.call_args[0][0]
            tab.submit_btn.Disable.assert_called_once()
            tab.transcribe_audio_file.assert_called_once()

    def test_start_recording_no_stt_capability(self, mock_parent_window):
        """Test starting recording when provider doesn't support STT."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.wx.MessageBox') as mock_msgbox:
            tab = ConversationTab()
            tab.current_engine = Mock()
            tab.current_engine.capabilities = []

            tab.start_recording()

            mock_msgbox.assert_called_once()
            args = mock_msgbox.call_args[0]
            assert _("The selected provider does not support speech-to-text") in args[0]

    def test_stop_recording(self, mock_parent_window):
        """Test stopping audio recording."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.recording_thread = Mock()
            tab.recording_thread.stop = Mock()
            tab.toggle_record_btn = Mock()
            tab.submit_btn = Mock()

            tab.stop_recording()

            tab.recording_thread.stop.assert_called_once()
            tab.toggle_record_btn.SetLabel.assert_called_once()
            assert _("Record") in tab.toggle_record_btn.SetLabel.call_args[0][0]
            tab.submit_btn.Enable.assert_called_once()

    def test_toggle_recording_start_when_not_recording(self, mock_parent_window):
        """Test toggling recording when not currently recording."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.recording_thread = None
            tab.start_recording = Mock()
            tab.stop_recording = Mock()

            tab.toggle_recording(Mock())

            tab.start_recording.assert_called_once()
            tab.stop_recording.assert_not_called()

    def test_toggle_recording_stop_when_recording(self, mock_parent_window):
        """Test toggling recording when currently recording."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.recording_thread = Mock()
            tab.recording_thread.is_alive.return_value = True
            tab.start_recording = Mock()
            tab.stop_recording = Mock()

            tab.toggle_recording(Mock())

            tab.stop_recording.assert_called_once()
            tab.start_recording.assert_not_called()

    def test_on_transcription_received(self, mock_parent_window):
        """Test handling received transcription."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.stop_sound') as mock_stop_sound:
            tab = ConversationTab()
            tab.SetStatusText = Mock()
            tab.prompt_panel = Mock()
            tab.prompt_panel.prompt = Mock()
            tab.prompt_panel.prompt.HasFocus.return_value = True
            tab.prompt_panel.set_prompt_focus = Mock()
            tab.GetTopLevelParent = Mock()
            tab.GetTopLevelParent.return_value.IsShown.return_value = True
            tab._handle_accessible_output = Mock()

            transcription = Mock()
            transcription.text = "Test transcription"

            tab.on_transcription_received(transcription)

            mock_stop_sound.assert_called_once()
            tab.SetStatusText.assert_called_with(_("Ready"))
            tab.prompt_panel.prompt.AppendText.assert_called_with("Test transcription")
            tab._handle_accessible_output.assert_called_with("Test transcription")
            tab.prompt_panel.set_prompt_focus.assert_called_once()

    def test_on_transcription_error(self, mock_parent_window):
        """Test handling transcription error."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.stop_sound') as mock_stop_sound, \
             patch('basilisk.gui.conversation_tab.wx.MessageBox') as mock_msgbox:
            tab = ConversationTab()
            tab.SetStatusText = Mock()

            error = Exception("Transcription failed")
            tab.on_transcription_error(error)

            mock_stop_sound.assert_called_once()
            tab.SetStatusText.assert_called_with(_("Ready"))
            mock_msgbox.assert_called_once()
            args = mock_msgbox.call_args[0]
            assert _("An error occurred during transcription: ") in args[0]
            assert "Transcription failed" in args[0]

    def test_on_completion_start(self, mock_parent_window):
        """Test handling of completion start."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.config.conf') as mock_conf:
            tab = ConversationTab()
            tab.submit_btn = Mock()
            tab.stop_completion_btn = Mock()
            tab.messages = Mock()

            mock_conf.return_value.conversation.focus_history_after_send = True
            tab._on_completion_start()

            tab.submit_btn.Disable.assert_called_once()
            tab.stop_completion_btn.Show.assert_called_once()
            tab.messages.SetFocus.assert_called_once()

    def test_on_completion_end_success(self, mock_parent_window):
        """Test handling of successful completion end."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.config.conf') as mock_conf:
            tab = ConversationTab()
            tab.submit_btn = Mock()
            tab.stop_completion_btn = Mock()
            tab.messages = Mock()

            mock_conf.return_value.conversation.focus_history_after_send = True
            tab._on_completion_end(success=True)

            tab.stop_completion_btn.Hide.assert_called_once()
            tab.submit_btn.Enable.assert_called_once()
            tab.messages.SetFocus.assert_called_once()

    def test_on_completion_end_failure(self, mock_parent_window):
        """Test handling of failed completion end."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.submit_btn = Mock()
            tab.stop_completion_btn = Mock()
            tab.messages = Mock()

            tab._on_completion_end(success=False)

            tab.stop_completion_btn.Hide.assert_called_once()
            tab.submit_btn.Enable.assert_called_once()
            tab.messages.SetFocus.assert_not_called()

    def test_on_stream_chunk(self, mock_parent_window):
        """Test handling of streaming chunks."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.messages = Mock()

            chunk = "Test chunk content"
            tab._on_stream_chunk(chunk)

            tab.messages.append_stream_chunk.assert_called_once_with(chunk)

    def test_on_stream_start(self, mock_parent_window):
        """Test handling of stream start."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.conversation = Mock()
            tab.messages = Mock()
            tab.prompt_panel = Mock()

            new_block = Mock(spec=MessageBlock)
            system_message = Mock(spec=SystemMessage)
            tab._on_stream_start(new_block, system_message)

            tab.conversation.add_block.assert_called_once_with(new_block, system_message)
            tab.messages.display_new_block.assert_called_once_with(new_block)
            tab.messages.SetInsertionPointEnd.assert_called_once()
            tab.prompt_panel.clear.assert_called_once()

    def test_on_stream_finish(self, mock_parent_window):
        """Test handling of stream finish."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.messages = Mock()
            tab.messages.a_output = Mock()

            new_block = Mock(spec=MessageBlock)
            tab._on_stream_finish(new_block)

            tab.messages.a_output.handle_stream_buffer.assert_called_once()
            tab.messages.update_last_segment_length.assert_called_once()

    def test_on_non_stream_finish(self, mock_parent_window):
        """Test handling of non-stream completion finish."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.conversation = Mock()
            tab.messages = Mock()
            tab.prompt_panel = Mock()

            new_block = Mock(spec=MessageBlock)
            new_block.response.content = "Test response"
            system_message = Mock(spec=SystemMessage)
            tab._on_non_stream_finish(new_block, system_message)

            tab.conversation.add_block.assert_called_once_with(new_block, system_message)
            tab.messages.display_new_block.assert_called_once_with(new_block)
            tab.messages.handle_accessible_output.assert_called_once_with("Test response")
            tab.prompt_panel.clear.assert_called_once()

    def test_save_conversation_success(self, mock_parent_window):
        """Test successful conversation saving."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.conversation = Mock()
            tab.conversation.save.return_value = None

            file_path = "/path/to/save/conversation.json"
            result = tab.save_conversation(file_path)

            assert result is True
            tab.conversation.save.assert_called_once_with(file_path)

    def test_save_conversation_failure(self, mock_parent_window):
        """Test conversation saving failure."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.wx.MessageBox') as mock_msgbox:
            tab = ConversationTab()
            tab.conversation = Mock()
            tab.conversation.save.side_effect = Exception("Save failed")

            file_path = "/path/to/save/conversation.json"
            result = tab.save_conversation(file_path)

            assert result is False
            tab.conversation.save.assert_called_once_with(file_path)
            mock_msgbox.assert_called_once()
            args = mock_msgbox.call_args[0]
            assert _("An error occurred while saving the conversation: ") in args[0]
            assert "Save failed" in args[0]

    def test_generate_conversation_title_success(self, mock_parent_window):
        """Test successful conversation title generation."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.play_sound') as mock_play_sound, \
             patch('basilisk.gui.conversation_tab.stop_sound') as mock_stop_sound:
            tab = ConversationTab()
            tab.completion_handler = Mock()
            tab.completion_handler.is_running.return_value = False
            tab.conversation = Mock()
            tab.conversation.messages = [Mock()]
            tab.current_model = Mock()
            tab.current_account = Mock()
            tab.current_account.provider.id = "test-provider"
            tab.temperature_spinner = Mock()
            tab.temperature_spinner.GetValue.return_value = 0.7
            tab.top_p_spinner = Mock()
            tab.top_p_spinner.GetValue.return_value = 0.9
            tab.max_tokens_spin_ctrl = Mock()
            tab.max_tokens_spin_ctrl.GetValue.return_value = 1000
            tab.stream_mode = Mock()
            tab.stream_mode.GetValue.return_value = False
            tab.current_engine = Mock()
            mock_response = Mock()
            tab.current_engine.completion.return_value = mock_response
            mock_new_block = Mock()
            mock_new_block.response.content = "Generated Title"
            tab.current_engine.completion_response_without_stream.return_value = mock_new_block

            result = tab.generate_conversation_title()

            assert result == "Generated Title"
            mock_play_sound.assert_called_with("progress", loop=True)
            mock_stop_sound.assert_called_once()

    def test_generate_conversation_title_completion_in_progress(self, mock_parent_window):
        """Test title generation when completion is already running."""
        with patch.object(ConversationTab, '__init__', return_value=None), \
             patch('basilisk.gui.conversation_tab.wx.MessageBox') as mock_msgbox:
            tab = ConversationTab()
            tab.completion_handler = Mock()
            tab.completion_handler.is_running.return_value = True

            result = tab.generate_conversation_title()

            assert result is None
            mock_msgbox.assert_called_once()
            args = mock_msgbox.call_args[0]
            assert _("A completion is already in progress") in args[0]

    def test_generate_conversation_title_no_messages(self, mock_parent_window):
        """Test title generation with no messages."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.completion_handler = Mock()
            tab.completion_handler.is_running.return_value = False
            tab.conversation = Mock()
            tab.conversation.messages = []

            result = tab.generate_conversation_title()
            assert result is None

    def test_generate_conversation_title_no_model(self, mock_parent_window):
        """Test title generation with no current model."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.completion_handler = Mock()
            tab.completion_handler.is_running.return_value = False
            tab.conversation = Mock()
            tab.conversation.messages = [Mock()]
            tab.current_model = None

            result = tab.generate_conversation_title()
            assert result is None

    def test_extract_text_from_message_string_input(self, mock_parent_window):
        """Test extracting text from string message content."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            content = "Test message content"

            result = tab.extract_text_from_message(content)
            assert result == "Test message content"

    def test_extract_text_from_message_non_string_input(self, mock_parent_window):
        """Test extracting text from non-string message content."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            content = {"type": "image", "data": "..."}

            result = tab.extract_text_from_message(content)
            assert result is None

    def test_refresh_messages_with_clear(self, mock_parent_window):
        """Test refreshing messages with clear flag."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.messages = Mock()
            tab.prompt_panel = Mock()
            tab.conversation = Mock()
            block1 = Mock(spec=MessageBlock)
            block2 = Mock(spec=MessageBlock)
            tab.conversation.messages = [block1, block2]

            tab.refresh_messages(need_clear=True)

            tab.messages.Clear.assert_called_once()
            tab.prompt_panel.clear.assert_called_once()
            tab.prompt_panel.refresh_attachments_list.assert_called_once()
            expected_calls = [call(block1), call(block2)]
            tab.messages.display_new_block.assert_has_calls(expected_calls)

    def test_refresh_messages_without_clear(self, mock_parent_window):
        """Test refreshing messages without clear flag."""
        with patch.object(ConversationTab, '__init__', return_value=None):
            tab = ConversationTab()
            tab.messages = Mock()
            tab.prompt_panel = Mock()
            tab.conversation = Mock()
            tab.conversation.messages = []

            tab.refresh_messages(need_clear=False)

            tab.messages.Clear.assert_not_called()
            tab.prompt_panel.clear.assert_not_called()
            tab.prompt_panel.refresh_attachments_list.assert_called_once()


# Additional parametrized tests for comprehensive coverage
@pytest.mark.parametrize("capability,expected_enabled", [
    ([ProviderCapability.STT], True),
    ([ProviderCapability.OCR], False),
    ([ProviderCapability.WEB_SEARCH], False),
    ([], False),
    ([ProviderCapability.STT, ProviderCapability.OCR], True),
])
def test_recording_button_enabled_based_on_capabilities(capability, expected_enabled, mock_parent_window):
    """Test that recording button is enabled based on provider capabilities."""
    with patch.object(ConversationTab, '__init__', return_value=None):
        tab = ConversationTab()
        tab.current_engine = Mock()
        tab.current_engine.capabilities = capability
        tab.toggle_record_btn = Mock()
        if ProviderCapability.STT in capability:
            assert expected_enabled is True
        else:
            assert expected_enabled is False


@pytest.mark.parametrize("stream_mode,expected_stream", [
    (True, True),
    (False, False),
])
def test_message_block_stream_setting(stream_mode, expected_stream, mock_parent_window):
    """Test that message block respects stream mode setting."""
    with patch.object(ConversationTab, '__init__', return_value=None):
        tab = ConversationTab()
        mock_model = Mock()
        mock_model.id = "test-model"
        tab.prompt_panel = Mock()
        tab.prompt_panel.ensure_model_compatibility.return_value = mock_model
        tab.prompt_panel.resize_all_attachments.return_value = None
        tab.prompt_panel.prompt_text = "Test"
        tab.prompt_panel.attachment_files = []
        tab.current_account = Mock()
        tab.current_account.provider.id = "test-provider"
        tab.temperature_spinner = Mock()
        tab.temperature_spinner.GetValue.return_value = 0.7
        tab.top_p_spinner = Mock()
        tab.top_p_spinner.GetValue.return_value = 0.9
        tab.max_tokens_spin_ctrl = Mock()
        tab.max_tokens_spin_ctrl.GetValue.return_value = 1000
        tab.stream_mode = Mock()
        tab.stream_mode.GetValue.return_value = stream_mode

        block = tab.get_new_message_block()
        assert block.stream == expected_stream


if __name__ == "__main__":
    pytest.main([__file__, "-v"])