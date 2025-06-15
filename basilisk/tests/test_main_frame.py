"""Comprehensive unit tests for the MainFrame class."""

import os
import tempfile
import sys
from unittest.mock import MagicMock, Mock, patch, call
from types import FrameType

import pytest
import wx

from basilisk.gui.main_frame import MainFrame
from basilisk.consts import HotkeyAction, CaptureMode
import basilisk.config as config
from basilisk.conversation import ImageFile


@pytest.fixture
def mock_wx_app():
    """Fixture to provide a mocked wx.App for testing."""
    with patch('wx.App') as mock_app:
        mock_app_instance = Mock()
        mock_app.return_value = mock_app_instance
        yield mock_app_instance


@pytest.fixture
def mock_config():
    """Fixture to provide a mocked basilisk configuration."""
    mock_conf = Mock()
    mock_conf.general.quit_on_close = True
    return mock_conf


@pytest.fixture
def mock_parent():
    """Fixture to provide a mocked parent window."""
    return Mock(spec=wx.Window)


@pytest.fixture
def mock_main_frame_dependencies():
    """Fixture to mock all major MainFrame dependencies."""
    with patch('basilisk.gui.main_frame.wx.Frame'), \
         patch('basilisk.gui.main_frame.TaskBarIcon'), \
         patch('basilisk.gui.main_frame.ConversationTab'), \
         patch('basilisk.gui.main_frame.signal.signal'), \
         patch('basilisk.gui.main_frame.config.conversation_profiles'), \
         patch('basilisk.gui.main_frame.config.accounts') as mock_accounts:

        mock_accounts.return_value = [Mock()]  # At least one account configured
        yield


class TestMainFrameInitialization:
    """Tests for MainFrame initialization and basic setup."""

    def test_init_with_default_parameters(self, mock_main_frame_dependencies, mock_config):
        """Test MainFrame initialization with default parameters."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()

            assert frame.conf == mock_config
            assert frame.last_conversation_id == 0
            assert hasattr(frame, 'tabs_panels')
            assert hasattr(frame, 'notebook')

    def test_init_with_custom_config(self, mock_main_frame_dependencies):
        """Test MainFrame initialization with custom configuration."""
        custom_config = Mock()
        custom_config.general.quit_on_close = False

        frame = MainFrame(conf=custom_config)
        assert frame.conf == custom_config

    def test_init_with_open_file(self, mock_main_frame_dependencies, mock_config):
        """Test MainFrame initialization with a file to open."""
        test_file = "test_conversation.bskc"

        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch.object(MainFrame, 'open_conversation') as mock_open:

            frame = MainFrame(open_file=test_file)
            mock_open.assert_called_once_with(test_file)

    def test_init_without_open_file_creates_new_conversation(self, mock_main_frame_dependencies, mock_config):
        """Test MainFrame initialization creates new conversation when no file specified."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch.object(MainFrame, 'on_new_default_conversation') as mock_new:

            frame = MainFrame()
            mock_new.assert_called_once_with(None)


class TestMainFrameConversationManagement:
    """Tests for conversation management functionality."""

    @pytest.fixture
    def frame_with_tabs(self, mock_main_frame_dependencies, mock_config):
        """Fixture providing a MainFrame instance with mocked tabs."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            frame.tabs_panels = [Mock(), Mock()]
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = 0
            yield frame

    def test_current_tab_property(self, frame_with_tabs):
        """Test current_tab property returns the selected tab."""
        result = frame_with_tabs.current_tab
        assert result == frame_with_tabs.tabs_panels[0]
        frame_with_tabs.notebook.GetSelection.assert_called_once()

    def test_new_conversation_with_profile(self, frame_with_tabs):
        """Test creating a new conversation with a specific profile."""
        mock_profile = Mock()
        mock_profile.name = "Test Profile"

        with patch('basilisk.gui.main_frame.ConversationTab') as mock_tab_class:
            mock_tab = Mock()
            mock_tab_class.return_value = mock_tab

            frame_with_tabs.new_conversation(mock_profile)

            mock_tab_class.assert_called_once()
            assert mock_tab in frame_with_tabs.tabs_panels

    def test_close_conversation_with_tabs_remaining(self, frame_with_tabs):
        """Test closing a conversation when other tabs remain."""
        frame_with_tabs.notebook.GetSelection.return_value = 0
        frame_with_tabs.notebook.GetPageCount.return_value = 1

        with patch.object(frame_with_tabs, 'refresh_frame_title') as mock_refresh:
            frame_with_tabs.on_close_conversation(None)

            frame_with_tabs.notebook.DeletePage.assert_called_once_with(0)
            assert len(frame_with_tabs.tabs_panels) == 1
            mock_refresh.assert_called_once()

    def test_close_conversation_creates_new_when_no_tabs_remain(self, frame_with_tabs):
        """Test closing last conversation creates a new default conversation."""
        frame_with_tabs.notebook.GetSelection.return_value = 0
        frame_with_tabs.notebook.GetPageCount.return_value = 0

        with patch.object(frame_with_tabs, 'on_new_default_conversation') as mock_new:
            frame_with_tabs.on_close_conversation(None)
            mock_new.assert_called_once_with(None)

    def test_close_conversation_with_no_selection(self, frame_with_tabs):
        """Test closing conversation when no tab is selected."""
        frame_with_tabs.notebook.GetSelection.return_value = wx.NOT_FOUND

        frame_with_tabs.on_close_conversation(None)
        frame_with_tabs.notebook.DeletePage.assert_not_called()


class TestMainFrameFileOperations:
    """Tests for file operations like saving and loading conversations."""

    @pytest.fixture
    def frame_with_current_tab(self, mock_main_frame_dependencies, mock_config):
        """Fixture providing a MainFrame with a current tab."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            mock_tab = Mock()
            mock_tab.bskc_path = None
            mock_tab.save_conversation.return_value = True
            frame.tabs_panels = [mock_tab]
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = 0
            yield frame

    def test_save_conversation_with_existing_path(self, frame_with_current_tab):
        """Test saving conversation when file path already exists."""
        frame_with_current_tab.current_tab.bskc_path = "existing_path.bskc"

        frame_with_current_tab.on_save_conversation(None)

        frame_with_current_tab.current_tab.save_conversation.assert_called_once_with("existing_path.bskc")

    def test_save_conversation_without_path_calls_save_as(self, frame_with_current_tab):
        """Test saving conversation without path triggers save-as dialog."""
        with patch.object(frame_with_current_tab, 'on_save_as_conversation') as mock_save_as:
            mock_save_as.return_value = "new_path.bskc"

            frame_with_current_tab.on_save_conversation(None)
            mock_save_as.assert_called_once()

    def test_save_conversation_no_tab_selected(self, mock_main_frame_dependencies, mock_config):
        """Test saving conversation when no tab is selected shows error."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.wx.MessageBox') as mock_msgbox:

            frame = MainFrame()
            frame.tabs_panels = []
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = wx.NOT_FOUND

            frame.on_save_conversation(None)
            mock_msgbox.assert_called_once()

    def test_save_as_conversation_success(self, frame_with_current_tab):
        """Test save-as conversation with successful file selection."""
        with patch('basilisk.gui.main_frame.wx.FileDialog') as mock_dialog:
            mock_dialog_instance = Mock()
            mock_dialog_instance.ShowModal.return_value = wx.ID_OK
            mock_dialog_instance.GetPath.return_value = "test_path.bskc"
            mock_dialog.return_value = mock_dialog_instance

            result = frame_with_current_tab.on_save_as_conversation(None)

            assert result == "test_path.bskc"
            frame_with_current_tab.current_tab.save_conversation.assert_called_once_with("test_path.bskc")

    def test_save_as_conversation_cancelled(self, frame_with_current_tab):
        """Test save-as conversation when user cancels dialog."""
        with patch('basilisk.gui.main_frame.wx.FileDialog') as mock_dialog:
            mock_dialog_instance = Mock()
            mock_dialog_instance.ShowModal.return_value = wx.ID_CANCEL
            mock_dialog.return_value = mock_dialog_instance

            result = frame_with_current_tab.on_save_as_conversation(None)

            assert result is None
            frame_with_current_tab.current_tab.save_conversation.assert_not_called()

    def test_open_conversation_success(self, mock_main_frame_dependencies, mock_config):
        """Test opening a conversation file successfully."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.ConversationTab.open_conversation') as mock_open, \
             patch.object(MainFrame, 'add_conversation_tab') as mock_add:

            mock_tab = Mock()
            mock_open.return_value = mock_tab

            frame = MainFrame()
            frame.open_conversation("test_file.bskc")

            mock_open.assert_called_once()
            mock_add.assert_called_once_with(mock_tab)

    def test_open_conversation_failure(self, mock_main_frame_dependencies, mock_config):
        """Test opening a conversation file that fails."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.ConversationTab.open_conversation') as mock_open, \
             patch('basilisk.gui.main_frame.wx.MessageBox') as mock_msgbox:

            mock_open.side_effect = Exception("File not found")

            frame = MainFrame()
            frame.open_conversation("nonexistent_file.bskc")

            mock_msgbox.assert_called_once()


class TestMainFrameEventHandling:
    """Tests for UI event handling and menu operations."""

    @pytest.fixture
    def frame_with_ui(self, mock_main_frame_dependencies, mock_config):
        """Fixture providing a MainFrame with UI components."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            frame.tray_icon = Mock()
            frame.signal_received = False
            yield frame

    def test_on_minimize_when_shown(self, frame_with_ui):
        """Test minimizing the frame when it's currently shown."""
        frame_with_ui.IsShown = Mock(return_value=True)
        frame_with_ui.Hide = Mock()

        frame_with_ui.on_minimize(None)

        frame_with_ui.Hide.assert_called_once()

    def test_on_minimize_when_already_hidden(self, frame_with_ui):
        """Test minimizing the frame when it's already hidden."""
        frame_with_ui.IsShown = Mock(return_value=False)
        frame_with_ui.Hide = Mock()

        frame_with_ui.on_minimize(None)

        frame_with_ui.Hide.assert_not_called()

    def test_on_restore_when_hidden(self, frame_with_ui):
        """Test restoring the frame when it's hidden."""
        frame_with_ui.IsShown = Mock(return_value=False)
        frame_with_ui.Show = Mock()
        frame_with_ui.Raise = Mock()

        frame_with_ui.on_restore(None)

        frame_with_ui.Show.assert_called_once_with(True)
        frame_with_ui.Raise.assert_called_once()

    def test_on_restore_when_already_shown(self, frame_with_ui):
        """Test restoring the frame when it's already shown."""
        frame_with_ui.IsShown = Mock(return_value=True)
        frame_with_ui.Show = Mock()

        frame_with_ui.on_restore(None)

        frame_with_ui.Show.assert_not_called()

    def test_toggle_visibility_when_shown(self, frame_with_ui):
        """Test toggling visibility when frame is shown."""
        frame_with_ui.IsShown = Mock(return_value=True)

        with patch.object(frame_with_ui, 'on_minimize') as mock_minimize:
            frame_with_ui.toggle_visibility(None)
            mock_minimize.assert_called_once_with(None)

    def test_toggle_visibility_when_hidden(self, frame_with_ui):
        """Test toggling visibility when frame is hidden."""
        frame_with_ui.IsShown = Mock(return_value=False)

        with patch.object(frame_with_ui, 'on_restore') as mock_restore:
            frame_with_ui.toggle_visibility(None)
            mock_restore.assert_called_once_with(None)

    def test_on_close_quit_on_close_enabled(self, frame_with_ui):
        """Test closing frame when quit_on_close is enabled."""
        frame_with_ui.conf.general.quit_on_close = True

        with patch.object(frame_with_ui, 'on_quit') as mock_quit:
            frame_with_ui.on_close(None)
            mock_quit.assert_called_once_with(None)

    def test_on_close_quit_on_close_disabled(self, frame_with_ui):
        """Test closing frame when quit_on_close is disabled."""
        frame_with_ui.conf.general.quit_on_close = False

        with patch.object(frame_with_ui, 'on_minimize') as mock_minimize:
            frame_with_ui.on_close(None)
            mock_minimize.assert_called_once_with(None)

    def test_on_ctrl_c_signal_handler(self, frame_with_ui):
        """Test SIGINT signal handler sets signal_received flag."""
        frame_with_ui.on_ctrl_c(2, Mock(spec=FrameType))
        assert frame_with_ui.signal_received is True

    def test_on_timer_with_signal_received(self, frame_with_ui):
        """Test timer handler when signal is received."""
        frame_with_ui.signal_received = True

        with patch('basilisk.gui.main_frame.wx.CallAfter') as mock_call_after:
            frame_with_ui.on_timer(None)
            mock_call_after.assert_called_once()


class TestMainFrameScreenCapture:
    """Tests for screen capture functionality."""

    @pytest.fixture
    def frame_with_conversation(self, mock_main_frame_dependencies, mock_config):
        """Fixture providing a MainFrame with a conversation tab."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            mock_tab = Mock()
            mock_tab.conv_storage_path = Mock()
            mock_tab.conv_storage_path.__truediv__ = Mock(return_value="test_path")
            frame.tabs_panels = [mock_tab]
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = 0
            yield frame

    def test_screen_capture_full_mode(self, frame_with_conversation):
        """Test screen capture in full screen mode."""
        with patch('basilisk.gui.main_frame.ScreenCaptureThread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            frame_with_conversation.screen_capture(CaptureMode.FULL)

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_screen_capture_window_mode(self, frame_with_conversation):
        """Test screen capture in window mode."""
        with patch('basilisk.gui.main_frame.ScreenCaptureThread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            frame_with_conversation.screen_capture(CaptureMode.WINDOW)

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_screen_capture_partial_mode_with_coordinates(self, frame_with_conversation):
        """Test screen capture in partial mode with coordinates."""
        coordinates = (100, 100, 500, 300)

        with patch('basilisk.gui.main_frame.ScreenCaptureThread') as mock_thread:
            mock_thread_instance = Mock()
            mock_thread.return_value = mock_thread_instance

            frame_with_conversation.screen_capture(CaptureMode.PARTIAL, coordinates)

            mock_thread.assert_called_once()
            mock_thread_instance.start.assert_called_once()

    def test_screen_capture_partial_mode_without_coordinates(self, frame_with_conversation):
        """Test screen capture in partial mode without coordinates shows error."""
        with patch('basilisk.gui.main_frame.wx.MessageBox') as mock_msgbox:
            frame_with_conversation.screen_capture(CaptureMode.PARTIAL)
            mock_msgbox.assert_called_once()

    def test_screen_capture_no_conversation_selected(self, mock_main_frame_dependencies, mock_config):
        """Test screen capture when no conversation is selected."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.wx.MessageBox') as mock_msgbox:

            frame = MainFrame()
            frame.tabs_panels = []
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = wx.NOT_FOUND

            frame.screen_capture(CaptureMode.FULL)
            mock_msgbox.assert_called_once()

    def test_post_screen_capture_restores_window(self, frame_with_conversation):
        """Test post screen capture restores and raises window."""
        mock_image_file = Mock(spec=ImageFile)
        frame_with_conversation.IsShown = Mock(return_value=False)
        frame_with_conversation.Show = Mock()
        frame_with_conversation.Restore = Mock()
        frame_with_conversation.Layout = Mock()
        frame_with_conversation.Raise = Mock()

        frame_with_conversation.post_screen_capture(mock_image_file)

        frame_with_conversation.Show.assert_called_once()
        frame_with_conversation.Restore.assert_called_once()
        frame_with_conversation.Raise.assert_called_once()


class TestMainFrameEdgeCases:
    """Tests for edge cases and error conditions."""

    def test_get_default_conv_title_increments_id(self, mock_main_frame_dependencies, mock_config):
        """Test default conversation title increments ID correctly."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()

            title1 = frame.get_default_conv_title()
            title2 = frame.get_default_conv_title()

            assert "1" in title1
            assert "2" in title2
            assert frame.last_conversation_id == 2

    def test_refresh_tab_title_no_current_tab(self, mock_main_frame_dependencies, mock_config):
        """Test refreshing tab title when no current tab exists."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            frame.tabs_panels = []
            frame.notebook = Mock()
            frame.notebook.GetSelection.return_value = wx.NOT_FOUND

            # Should not raise an exception
            frame.refresh_tab_title()

    def test_make_on_goto_tab_function(self, mock_main_frame_dependencies, mock_config):
        """Test the make_on_goto_tab function factory."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config):
            frame = MainFrame()
            frame.notebook = Mock()
            frame.tabs_panels = [Mock(), Mock(), Mock()]

            goto_func = frame.make_on_goto_tab(2)
            goto_func(None)

            frame.notebook.SetSelection.assert_called_once_with(1)  # 0-indexed

    def test_handle_no_account_configured_with_accounts(self, mock_main_frame_dependencies, mock_config):
        """Test handle_no_account_configured when accounts exist."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.config.accounts') as mock_accounts:

            mock_accounts.return_value = [Mock()]  # Has accounts

            frame = MainFrame()
            frame.handle_no_account_configured()
            # Should return early, no message box

    def test_handle_no_account_configured_without_accounts(self, mock_main_frame_dependencies, mock_config):
        """Test handle_no_account_configured when no accounts exist."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.config.accounts') as mock_accounts, \
             patch('basilisk.gui.main_frame.wx.MessageBox') as mock_msgbox, \
             patch.object(MainFrame, 'on_manage_accounts') as mock_manage:

            mock_accounts.return_value = []  # No accounts
            mock_msgbox.return_value = wx.YES

            frame = MainFrame()
            frame.handle_no_account_configured()

            mock_msgbox.assert_called_once()
            mock_manage.assert_called_once_with(None)


class TestMainFrameIntegration:
    """Integration-style tests for MainFrame interactions."""

    def test_quit_application_cleanup(self, mock_main_frame_dependencies, mock_config):
        """Test application quit performs proper cleanup."""
        with patch('basilisk.gui.main_frame.config.conf', return_value=mock_config), \
             patch('basilisk.gui.main_frame.global_vars') as mock_globals, \
             patch('basilisk.gui.main_frame.wx.GetApp') as mock_app:

            mock_app_instance = Mock()
            mock_app.return_value = mock_app_instance

            frame = MainFrame()
            frame.tray_icon = Mock()
            frame.Destroy = Mock()

            # Add some tabs with completion handlers
            mock_tab1 = Mock()
            mock_tab2 = Mock()
            frame.tabs_panels = [mock_tab1, mock_tab2]

            frame.on_quit(None)

            # Verify cleanup
            assert mock_globals.app_should_exit is True
            mock_tab1.completion_handler.stop_completion.assert_called_once()
            mock_tab2.completion_handler.stop_completion.assert_called_once()
            frame.tray_icon.RemoveIcon.assert_called_once()
            frame.tray_icon.Destroy.assert_called_once()
            frame.Destroy.assert_called_once()
            mock_app_instance.ExitMainLoop.assert_called_once()