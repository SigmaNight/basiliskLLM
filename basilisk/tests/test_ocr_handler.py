"""Comprehensive unit tests for the OCR handler functionality.

This module tests all aspects of the OCRHandler class including initialization,
GUI interactions, message handling, process management, and error conditions.
Testing framework: pytest with extensive mocking of wx GUI components.
"""

import logging
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from multiprocessing import Queue, Value

from basilisk.gui.ocr_handler import OCRHandler, CHECK_TASK_DELAY
from basilisk.provider_capability import ProviderCapability

@pytest.fixture
def mock_wx():
    """Mock wx module and its components."""
    with patch('basilisk.gui.ocr_handler.wx') as mock_wx:
        mock_wx.EVT_BUTTON = MagicMock()
        mock_wx.OK = 1
        mock_wx.YES = 2
        mock_wx.NO = 4
        mock_wx.YES_NO = 6
        mock_wx.ICON_ERROR = 16
        mock_wx.ICON_INFORMATION = 32
        mock_wx.Button = MagicMock()
        mock_wx.MessageBox = MagicMock()
        mock_wx.LaunchDefaultApplication = MagicMock()
        mock_wx.CallLater = MagicMock()
        yield mock_wx

@pytest.fixture
def mock_parent():
    """Mock parent conversation tab."""
    parent = MagicMock()
    parent.current_engine = MagicMock()
    parent.current_engine.capabilities = [ProviderCapability.OCR]
    parent.current_engine.client = MagicMock()
    parent.current_account = MagicMock()
    parent.current_account.api_key.get_secret_value.return_value = "test_api_key"
    parent.current_account.custom_base_url = None
    parent.current_account.provider.base_url = "https://api.test.com"
    parent.prompt_panel = MagicMock()
    parent.prompt_panel.attachment_files = ["test_file.pdf"]
    parent.prompt_panel.check_attachments_valid.return_value = True
    return parent

@pytest.fixture
def mock_config():
    """Mock configuration object."""
    with patch('basilisk.gui.ocr_handler.config.conf') as mock_conf:
        config_obj = MagicMock()
        config_obj.general.log_level.name = "INFO"
        mock_conf.return_value = config_obj
        yield config_obj

@pytest.fixture
def mock_global_vars():
    """Mock global variables."""
    with patch('basilisk.gui.ocr_handler.global_vars') as mock_gv:
        mock_gv.args.log_level = None
        yield mock_gv

@pytest.fixture
def mock_progress_dialog():
    """Mock progress bar dialog."""
    with patch('basilisk.gui.ocr_handler.ProgressBarDialog') as mock_dialog_class:
        dialog = MagicMock()
        dialog.cancel_flag = Value('i', 0)
        dialog.IsShown.return_value = True
        mock_dialog_class.return_value = dialog
        yield dialog

@pytest.fixture
def ocr_handler(mock_parent, mock_config, mock_global_vars):
    """Create OCR handler instance with mocked dependencies."""
    with patch('basilisk.gui.ocr_handler.wx'):
        handler = OCRHandler(mock_parent)
        return handler

class TestOCRHandlerInitialization:
    """Test OCR handler initialization and basic configuration."""

    def test_init_with_parent(self, mock_parent, mock_config, mock_global_vars):
        handler = OCRHandler(mock_parent)
        assert handler.parent == mock_parent
        assert handler.conf is not None
        assert handler.process is None
        assert handler.ocr_button is None

    def test_init_sets_config(self, mock_parent, mock_config, mock_global_vars):
        handler = OCRHandler(mock_parent)
        assert handler.conf == mock_config

    def test_init_logger_configuration(self, mock_parent, mock_config, mock_global_vars):
        with patch('basilisk.gui.ocr_handler.logging.getLogger') as mock_logger:
            handler = OCRHandler(mock_parent)
            mock_logger.assert_called_once_with('basilisk.gui.ocr_handler')

class TestOCRWidgetCreation:
    """Test OCR widget creation and UI setup."""

    def test_create_ocr_widget_returns_button(self, ocr_handler, mock_wx):
        mock_parent_window = MagicMock()
        mock_button = MagicMock()
        mock_wx.Button.return_value = mock_button
        result = ocr_handler.create_ocr_widget(mock_parent_window)
        assert result == mock_button
        assert ocr_handler.ocr_button == mock_button
        mock_wx.Button.assert_called_once()
        mock_button.Bind.assert_called_once_with(mock_wx.EVT_BUTTON, ocr_handler.on_ocr)

    def test_create_ocr_widget_button_label(self, ocr_handler, mock_wx):
        mock_parent_window = MagicMock()
        mock_button = MagicMock()
        mock_wx.Button.return_value = mock_button
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "Perform OCR on Attachments"
            ocr_handler.create_ocr_widget(mock_parent_window)
            call_args = mock_wx.Button.call_args
            assert 'label' in call_args.kwargs
            mock_translate.assert_called_once_with("Perform OCR on Attachments")

    def test_create_ocr_widget_event_binding(self, ocr_handler, mock_wx):
        mock_parent_window = MagicMock()
        mock_button = MagicMock()
        mock_wx.Button.return_value = mock_button
        ocr_handler.create_ocr_widget(mock_parent_window)
        mock_button.Bind.assert_called_once_with(mock_wx.EVT_BUTTON, ocr_handler.on_ocr)

class TestMessageHandling:
    """Test OCR message handling functionality."""

    def test_handle_ocr_message_info_message(self, ocr_handler):
        dialog = MagicMock()
        with patch.object(ocr_handler, '_handle_ocr_info_message') as mock_handle_info:
            ocr_handler._handle_ocr_message("message", "test info", dialog)
            mock_handle_info.assert_called_once_with("test info", dialog)

    def test_handle_ocr_message_progress_message(self, ocr_handler):
        dialog = MagicMock()
        with patch.object(ocr_handler, '_handle_ocr_progress_message') as mock_handle_progress:
            ocr_handler._handle_ocr_message("progress", 50, dialog)
            mock_handle_progress.assert_called_once_with(50, dialog)

    def test_handle_ocr_message_result_message(self, ocr_handler):
        dialog = MagicMock()
        with patch.object(ocr_handler, '_handle_ocr_completion_message') as mock_handle_completion:
            ocr_handler._handle_ocr_message("result", ["file1.txt"], dialog)
            mock_handle_completion.assert_called_once_with("result", ["file1.txt"], dialog)

    def test_handle_ocr_message_error_message(self, ocr_handler):
        dialog = MagicMock()
        with patch.object(ocr_handler, '_handle_ocr_completion_message') as mock_handle_completion:
            ocr_handler._handle_ocr_message("error", "OCR failed", dialog)
            mock_handle_completion.assert_called_once_with("error", "OCR failed", dialog)

    def test_handle_ocr_message_unknown_type(self, ocr_handler):
        dialog = MagicMock()
        with patch('basilisk.gui.ocr_handler.log.warning') as mock_log_warning:
            ocr_handler._handle_ocr_message("unknown_type", "data", dialog)
            mock_log_warning.assert_called_once_with(
                "Unknown message type in result queue: %s", "unknown_type"
            )

    def test_handle_ocr_message_exception_handling(self, ocr_handler, mock_wx):
        dialog = MagicMock()
        with patch.object(ocr_handler, '_handle_ocr_info_message') as mock_handle_info:
            mock_handle_info.side_effect = Exception("Test error")
            with patch('basilisk.gui.ocr_handler._') as mock_translate:
                mock_translate.return_value = "Error message"
                ocr_handler._handle_ocr_message("message", "test", dialog)
                mock_wx.MessageBox.assert_called_once()
                assert "Test error" in mock_wx.MessageBox.call_args[0][0]

class TestSpecificMessageHandlers:
    """Test specific message type handlers."""

    def test_handle_ocr_info_message_with_string(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_info_message("Processing file 1 of 3", dialog)
        dialog.update_message.assert_called_once_with("Processing file 1 of 3")

    def test_handle_ocr_info_message_with_empty_string(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_info_message("", dialog)
        dialog.update_message.assert_not_called()

    def test_handle_ocr_info_message_with_non_string(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_info_message(123, dialog)
        dialog.update_message.assert_not_called()

    def test_handle_ocr_progress_message_with_integer(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_progress_message(75, dialog)
        dialog.update_progress_bar.assert_called_once_with(75)

    def test_handle_ocr_progress_message_with_non_integer(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_progress_message("75%", dialog)
        dialog.update_progress_bar.assert_not_called()

    def test_handle_ocr_progress_message_boundary_values(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler._handle_ocr_progress_message(0, dialog)
        ocr_handler._handle_ocr_progress_message(100, dialog)
        assert dialog.update_progress_bar.call_count == 2
        dialog.update_progress_bar.assert_any_call(0)
        dialog.update_progress_bar.assert_any_call(100)

class TestCompletionMessageHandling:
    """Test completion message handling and result display."""

    def test_handle_ocr_completion_message_result_success(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        with patch.object(ocr_handler, '_display_ocr_result') as mock_display:
            ocr_handler._handle_ocr_completion_message("result", ["file1.txt"], dialog)
            dialog.Destroy.assert_called_once()
            ocr_handler.ocr_button.Enable.assert_called_once()
            mock_display.assert_called_once_with(["file1.txt"])

    def test_handle_ocr_completion_message_error(self, ocr_handler, mock_wx):
        dialog = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "Error"
            ocr_handler._handle_ocr_completion_message("error", "OCR failed", dialog)
            dialog.Destroy.assert_called_once()
            ocr_handler.ocr_button.Enable.assert_called_once()
            mock_wx.MessageBox.assert_called_once_with(
                "OCR failed", "Error", mock_wx.OK | mock_wx.ICON_ERROR
            )

    def test_handle_ocr_completion_message_no_dialog(self, ocr_handler):
        ocr_handler.ocr_button = MagicMock()
        with patch.object(ocr_handler, '_display_ocr_result') as mock_display:
            ocr_handler._handle_ocr_completion_message("result", ["file1.txt"], None)
            ocr_handler.ocr_button.Enable.assert_called_once()
            mock_display.assert_called_once_with(["file1.txt"])

    def test_display_ocr_result_with_file_list(self, ocr_handler, mock_wx):
        file_list = ["file1.txt", "file2.txt"]
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.side_effect = [
                "OCR completed successfully. Text extracted to:",
                "Do you want to open the files?"
            ]
            mock_wx.MessageBox.return_value = mock_wx.YES
            ocr_handler._display_ocr_result(file_list)
            assert mock_wx.MessageBox.call_count == 1
            mock_wx.LaunchDefaultApplication.assert_has_calls([
                call("file1.txt"), call("file2.txt")
            ])

    def test_display_ocr_result_with_file_list_no_open(self, ocr_handler, mock_wx):
        file_list = ["file1.txt", "file2.txt"]
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.side_effect = [
                "OCR completed successfully. Text extracted to:",
                "Do you want to open the files?"
            ]
            mock_wx.MessageBox.return_value = mock_wx.NO
            ocr_handler._display_ocr_result(file_list)
            assert mock_wx.LaunchDefaultApplication.call_count == 0

    def test_display_ocr_result_with_string_result(self, ocr_handler, mock_wx):
        result_string = "Extracted text content"
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "Result"
            ocr_handler._display_ocr_result(result_string)
            mock_wx.MessageBox.assert_called_once_with(
                result_string, "Result", mock_wx.OK | mock_wx.ICON_INFORMATION
            )

    def test_display_ocr_result_with_empty_or_invalid_data(self, ocr_handler, mock_wx):
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "OCR completed, but no text was extracted."
            ocr_handler._display_ocr_result([])
            ocr_handler._display_ocr_result(None)
            assert mock_wx.MessageBox.call_count == 2
            for args in mock_wx.MessageBox.call_args_list:
                assert "no text was extracted" in args[0][0].lower()

class TestQueueProcessingAndTaskManagement:
    """Test queue processing and task management functionality."""

    def test_process_ocr_queue_with_messages(self, ocr_handler):
        result_queue = MagicMock()
        dialog = MagicMock()
        result_queue.empty.side_effect = [False, False, True]
        result_queue.get.side_effect = [
            ("message", "Processing file 1"),
            ("progress", 50)
        ]
        with patch.object(ocr_handler, '_handle_ocr_message') as mock_handle:
            ocr_handler._process_ocr_queue(result_queue, dialog)
            assert mock_handle.call_count == 2
            mock_handle.assert_has_calls([
                call("message", "Processing file 1", dialog),
                call("progress", 50, dialog)
            ])

    def test_process_ocr_queue_empty_queue(self, ocr_handler):
        result_queue = MagicMock()
        dialog = MagicMock()
        result_queue.empty.return_value = True
        with patch.object(ocr_handler, '_handle_ocr_message') as mock_handle:
            ocr_handler._process_ocr_queue(result_queue, dialog)
            mock_handle.assert_not_called()

    def test_process_ocr_queue_exception_handling(self, ocr_handler):
        result_queue = MagicMock()
        dialog = MagicMock()
        result_queue.empty.side_effect = Exception("Queue error")
        with patch('basilisk.gui.ocr_handler.log.error') as mock_log_error:
            ocr_handler._process_ocr_queue(result_queue, dialog)
            mock_log_error.assert_called_once()

    def test_cleanup_ocr_process_with_running_process(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 1
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        ocr_handler.process = mock_process
        ocr_handler.ocr_button = MagicMock()
        with patch('basilisk.gui.ocr_handler.log.debug') as mock_log_debug:
            ocr_handler._cleanup_ocr_process(dialog)
            mock_process.terminate.assert_called_once()
            mock_process.join.assert_called_once_with(timeout=1.0)
            mock_log_debug.assert_called_once()
            dialog.Destroy.assert_called_once()
            ocr_handler.ocr_button.Enable.assert_called_once()
            assert ocr_handler.process is None

    def test_cleanup_ocr_process_kill_stubborn_process(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 1
        mock_process = MagicMock()
        mock_process.is_alive.side_effect = [True, True]
        ocr_handler.process = mock_process
        ocr_handler.ocr_button = MagicMock()
        with patch('basilisk.gui.ocr_handler.log.warning') as mock_log_warning:
            ocr_handler._cleanup_ocr_process(dialog)
            mock_process.kill.assert_called_once()
            mock_log_warning.assert_called_once_with("Process did not terminate, killing it")

    def test_cleanup_ocr_process_no_cancellation(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 0
        dialog.IsShown.return_value = True
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        ocr_handler.process = mock_process
        ocr_handler.ocr_button = MagicMock()
        ocr_handler._cleanup_ocr_process(dialog)
        mock_process.terminate.assert_not_called()
        dialog.Destroy.assert_called_once()
        ocr_handler.ocr_button.Enable.assert_called_once()

    def test_cleanup_ocr_process_exception_handling(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 1
        dialog.Destroy.side_effect = Exception("Dialog destroy error")
        mock_process = MagicMock()
        mock_process.terminate.side_effect = Exception("Terminate error")
        ocr_handler.process = mock_process
        ocr_handler.ocr_button = MagicMock()
        with patch('basilisk.gui.ocr_handler.log.error') as mock_log_error:
            ocr_handler._cleanup_ocr_process(dialog)
            assert mock_log_error.call_count == 2

class TestTaskProgressMonitoring:
    """Test task progress monitoring functionality."""

    def test_check_task_progress_process_running(self, ocr_handler, mock_wx):
        dialog = MagicMock()
        dialog.cancel_flag.value = 0
        result_queue = MagicMock()
        cancel_flag = MagicMock()
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        ocr_handler.process = mock_process
        with patch.object(ocr_handler, '_process_ocr_queue') as mock_process_queue:
            ocr_handler.check_task_progress(dialog, result_queue, cancel_flag)
            mock_process_queue.assert_called_once_with(result_queue, dialog)
            mock_wx.CallLater.assert_called_once_with(
                CHECK_TASK_DELAY,
                ocr_handler.check_task_progress,
                dialog,
                result_queue,
                cancel_flag
            )

    def test_check_task_progress_process_finished(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 0
        result_queue = MagicMock()
        cancel_flag = MagicMock()
        mock_process = MagicMock()
        mock_process.is_alive.return_value = False
        ocr_handler.process = mock_process
        with patch.object(ocr_handler, '_process_ocr_queue') as mock_process_queue, \
             patch.object(ocr_handler, '_cleanup_ocr_process') as mock_cleanup:
            ocr_handler.check_task_progress(dialog, result_queue, cancel_flag)
            mock_process_queue.assert_called_once_with(result_queue, dialog)
            mock_cleanup.assert_called_once_with(dialog)

    def test_check_task_progress_cancelled(self, ocr_handler):
        dialog = MagicMock()
        dialog.cancel_flag.value = 1
        result_queue = MagicMock()
        cancel_flag = MagicMock()
        mock_process = MagicMock()
        mock_process.is_alive.return_value = True
        ocr_handler.process = mock_process
        with patch.object(ocr_handler, '_process_ocr_queue') as mock_process_queue, \
             patch.object(ocr_handler, '_cleanup_ocr_process') as mock_cleanup:
            ocr_handler.check_task_progress(dialog, result_queue, cancel_flag)
            mock_process_queue.assert_called_once_with(result_queue, dialog)
            mock_cleanup.assert_called_once_with(dialog)

    def test_check_task_progress_no_process(self, ocr_handler):
        dialog = MagicMock()
        result_queue = MagicMock()
        cancel_flag = MagicMock()
        ocr_handler.process = None
        with patch.object(ocr_handler, '_process_ocr_queue') as mock_process_queue, \
             patch.object(ocr_handler, '_cleanup_ocr_process') as mock_cleanup:
            ocr_handler.check_task_progress(dialog, result_queue, cancel_flag)
            mock_process_queue.assert_called_once_with(result_queue, dialog)
            mock_cleanup.assert_called_once_with(dialog)

class TestOCREventHandler:
    """Test main OCR event handler functionality."""

    def test_on_ocr_no_ocr_capability(self, ocr_handler, mock_wx):
        event = MagicMock()
        ocr_handler.parent.current_engine.capabilities = []
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "The selected provider does not support OCR."
            ocr_handler.on_ocr(event)
            mock_wx.MessageBox.assert_called_once_with(
                "The selected provider does not support OCR.",
                mock_translate.return_value,
                mock_wx.OK | mock_wx.ICON_ERROR
            )

    def test_on_ocr_no_attachments(self, ocr_handler, mock_wx):
        event = MagicMock()
        ocr_handler.parent.prompt_panel.attachment_files = []
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "No attachments to perform OCR on."
            ocr_handler.on_ocr(event)
            mock_wx.MessageBox.assert_called_once_with(
                "No attachments to perform OCR on.",
                mock_translate.return_value,
                mock_wx.OK | mock_wx.ICON_ERROR
            )

    def test_on_ocr_invalid_attachments(self, ocr_handler, mock_wx):
        event = MagicMock()
        ocr_handler.parent.prompt_panel.check_attachments_valid.return_value = False
        ocr_handler.on_ocr(event)
        mock_wx.MessageBox.assert_not_called()

    def test_on_ocr_no_client(self, ocr_handler, mock_wx):
        event = MagicMock()
        ocr_handler.parent.current_engine.client = None
        with patch('basilisk.gui.ocr_handler._') as mock_translate:
            mock_translate.return_value = "The selected provider does not have a client."
            ocr_handler.on_ocr(event)
            mock_wx.MessageBox.assert_called_once_with(
                "The selected provider does not have a client.",
                mock_translate.return_value,
                mock_wx.OK | mock_wx.ICON_ERROR
            )

    @patch('basilisk.gui.ocr_handler.run_task')
    def test_on_ocr_successful_start(self, mock_run_task, ocr_handler, mock_wx, mock_progress_dialog):
        event = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        mock_process = MagicMock()
        mock_process.pid = 12345
        mock_run_task.return_value = mock_process
        with patch('basilisk.gui.ocr_handler._') as mock_translate, \
             patch('basilisk.gui.ocr_handler.log.debug') as mock_log_debug:
            mock_translate.side_effect = [
                "Performing OCR...", "Performing OCR on attachments..."
            ]
            ocr_handler.on_ocr(event)
            ocr_handler.ocr_button.Disable.assert_called_once()
            mock_progress_dialog.Show.assert_called_once()
            mock_run_task.assert_called_once()
            assert ocr_handler.process == mock_process
            mock_wx.CallLater.assert_called_once()
            mock_log_debug.assert_called_once_with("OCR process started: %s", 12345)

    @patch('basilisk.gui.ocr_handler.run_task')
    @patch('basilisk.gui.ocr_handler.Value')
    @patch('basilisk.gui.ocr_handler.Queue')
    def test_on_ocr_process_parameters(self, mock_queue, mock_value, mock_run_task, ocr_handler, mock_progress_dialog):
        event = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        mock_cancel_flag = MagicMock()
        mock_result_queue = MagicMock()
        mock_value.return_value = mock_cancel_flag
        mock_queue.return_value = mock_result_queue
        with patch('basilisk.gui.ocr_handler._'):
            ocr_handler.on_ocr(event)
            args, kwargs = mock_run_task.call_args
            assert args[0] == ocr_handler.parent.current_engine.handle_ocr
            assert args[1] == mock_result_queue
            assert args[2] == mock_cancel_flag
            assert kwargs['api_key'] == "test_api_key"
            assert kwargs['base_url'] == "https://api.test.com"
            assert kwargs['attachments'] == ["test_file.pdf"]
            assert 'log_level' in kwargs

    @patch('basilisk.gui.ocr_handler.run_task')
    def test_on_ocr_custom_base_url(self, mock_run_task, ocr_handler, mock_progress_dialog):
        event = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        ocr_handler.parent.current_account.custom_base_url = "https://custom.api.com"
        with patch('basilisk.gui.ocr_handler._'):
            ocr_handler.on_ocr(event)
            kwargs = mock_run_task.call_args[1]
            assert kwargs['base_url'] == "https://custom.api.com"

    @patch('basilisk.gui.ocr_handler.run_task')
    def test_on_ocr_custom_log_level(self, mock_run_task, ocr_handler, mock_progress_dialog):
        event = MagicMock()
        ocr_handler.ocr_button = MagicMock()
        with patch('basilisk.gui.ocr_handler.global_vars') as mock_gv, \
             patch('basilisk.gui.ocr_handler._'):
            mock_gv.args.log_level = "DEBUG"
            ocr_handler.on_ocr(event)
            assert mock_run_task.call_args[1]['log_level'] == "DEBUG"

class TestOCRHandlerEdgeCases:
    """Test edge cases and error conditions."""

    def test_handle_message_with_destroyed_dialog(self, ocr_handler):
        ocr_handler._handle_ocr_completion_message("result", ["file.txt"], None)

    def test_cleanup_with_no_button(self, ocr_handler):
        dialog = MagicMock()
        ocr_handler.ocr_button = None
        ocr_handler._cleanup_ocr_process(dialog)

    def test_multiple_message_types_in_queue(self, ocr_handler):
        result_queue = MagicMock()
        dialog = MagicMock()
        result_queue.empty.side_effect = [False, False, False, True]
        result_queue.get.side_effect = [
            ("message", "Starting OCR"),
            ("progress", 25),
            ("result", ["output.txt"])
        ]
        with patch.object(ocr_handler, '_handle_ocr_message') as mock_handle:
            ocr_handler._process_ocr_queue(result_queue, dialog)
            assert mock_handle.call_count == 3
            mock_handle.assert_has_calls([
                call("message", "Starting OCR", dialog),
                call("progress", 25, dialog),
                call("result", ["output.txt"], dialog)
            ])