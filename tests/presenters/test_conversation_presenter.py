"""Tests for ConversationPresenter."""

from unittest.mock import MagicMock, patch

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.presenters.conversation_presenter import ConversationPresenter
from basilisk.provider_ai_model import AIModelInfo
from basilisk.services.conversation_service import ConversationService


@pytest.fixture
def mock_view():
	"""Return a mock ConversationTab view with required attributes."""
	view = MagicMock()
	view.submit_btn = MagicMock()
	view.submit_btn.IsEnabled.return_value = True
	view.stop_completion_btn = MagicMock()
	view.messages = MagicMock()
	view.messages.should_speak_response = False
	view.prompt_panel = MagicMock()
	view.prompt_panel.prompt_text = ""
	view.prompt_panel.attachment_files = []
	view.prompt_panel.check_attachments_valid.return_value = True
	view.system_prompt_txt = MagicMock()
	view.system_prompt_txt.GetValue.return_value = ""
	view.temperature_spinner = MagicMock()
	view.temperature_spinner.GetValue.return_value = 0.5
	view.top_p_spinner = MagicMock()
	view.top_p_spinner.GetValue.return_value = 1.0
	view.max_tokens_spin_ctrl = MagicMock()
	view.max_tokens_spin_ctrl.GetValue.return_value = 100
	view.stream_mode = MagicMock()
	view.stream_mode.GetValue.return_value = True
	view.web_search_mode = MagicMock()
	view.web_search_mode.GetValue.return_value = False
	view._is_destroying = False
	view.toggle_record_btn = MagicMock()
	view._draft_timer = MagicMock()
	view.current_engine = MagicMock()
	view.current_engine.capabilities = set()
	view.current_account = MagicMock()
	view.current_account.provider.id = "openai"
	view.current_account.provider.engine_cls.capabilities = set()
	view.current_model = MagicMock()
	view.current_model.id = "gpt-4"
	view.SetStatusText = MagicMock()
	view.GetTopLevelParent.return_value.IsShown.return_value = False
	return view


@pytest.fixture
def mock_service():
	"""Return a mock ConversationService."""
	service = MagicMock(spec=ConversationService)
	service.db_conv_id = None
	service.private = False
	return service


@pytest.fixture
def presenter(mock_view, mock_service):
	"""Return a ConversationPresenter with mocked view and service."""
	return ConversationPresenter(
		view=mock_view,
		service=mock_service,
		conversation=Conversation(),
		conv_storage_path="memory://test",
		bskc_path=None,
	)


class TestOnSubmit:
	"""Tests for on_submit."""

	def test_empty_prompt_focuses_prompt(self, presenter, mock_view):
		"""Empty prompt should focus the prompt input."""
		mock_view.prompt_panel.prompt_text = ""
		mock_view.prompt_panel.attachment_files = []
		presenter.on_submit()
		mock_view.prompt_panel.set_prompt_focus.assert_called_once()

	def test_stores_content_and_starts_completion(self, presenter, mock_view):
		"""Submit with content should store prompt and start completion."""
		mock_view.prompt_panel.prompt_text = "Hello"
		mock_view.prompt_panel.attachment_files = []
		mock_view.prompt_panel.ensure_model_compatibility.return_value = (
			mock_view.current_model
		)

		with patch.object(
			presenter.completion_handler, "start_completion"
		) as mock_start:
			presenter.on_submit()

		mock_view.prompt_panel.clear.assert_called_once_with(refresh=True)
		mock_start.assert_called_once()


class TestOnCompletionError:
	"""Tests for _on_completion_error."""

	def test_restores_prompt(self, presenter, mock_view):
		"""Error should restore the saved prompt content."""
		presenter._stored_prompt_text = "my prompt"
		presenter._stored_attachments = []

		with patch(
			"basilisk.presenters.conversation_presenter.show_enhanced_error_dialog"
		):
			presenter._on_completion_error("test error")

		assert mock_view.prompt_panel.prompt_text == "my prompt"
		assert presenter._stored_prompt_text is None


class TestOnStreamStart:
	"""Tests for _on_stream_start."""

	def test_adds_block_to_conversation(self, presenter, mock_view):
		"""Stream start should add the block to the conversation."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content=""),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		system_msg = SystemMessage(content="Be helpful")

		presenter._on_stream_start(block, system_msg)

		assert block in presenter.conversation.messages
		mock_view.messages.display_new_block.assert_called_once_with(
			block, streaming=True
		)
		mock_view.messages.SetInsertionPointEnd.assert_called_once()


class TestToggleRecording:
	"""Tests for toggle_recording."""

	def test_dispatches_start_when_not_recording(self, presenter, mock_view):
		"""Toggle should call start_recording when not already recording."""
		presenter.recording_thread = None

		with patch.object(presenter, "start_recording") as mock_start:
			presenter.toggle_recording()
			mock_start.assert_called_once()

	def test_dispatches_stop_when_recording(self, presenter, mock_view):
		"""Toggle should call stop_recording when already recording."""
		mock_thread = MagicMock()
		mock_thread.is_alive.return_value = True
		presenter.recording_thread = mock_thread

		with patch.object(presenter, "stop_recording") as mock_stop:
			presenter.toggle_recording()
			mock_stop.assert_called_once()


class TestBuildDraftBlock:
	"""Tests for _build_draft_block guard conditions."""

	def test_returns_none_when_no_account(self, presenter, mock_view):
		"""_build_draft_block returns None when current_account is None."""
		mock_view.current_account = None
		assert presenter._build_draft_block() is None

	def test_returns_none_when_no_model(self, presenter, mock_view):
		"""_build_draft_block returns None when current_model is None."""
		mock_view.current_model = None
		assert presenter._build_draft_block() is None

	def test_returns_none_when_empty_prompt_and_no_attachments(
		self, presenter, mock_view
	):
		"""_build_draft_block returns None when prompt and attachments are empty."""
		# mock_view default: prompt_text="" and attachment_files=[]
		assert presenter._build_draft_block() is None

	def test_returns_block_when_prompt_present(self, presenter, mock_view):
		"""_build_draft_block returns a MessageBlock when prompt is non-empty."""
		mock_view.prompt_panel.prompt_text = "draft text"
		result = presenter._build_draft_block()
		assert result is not None
		assert result.request.content == "draft text"


class TestCleanup:
	"""Tests for cleanup() resource teardown."""

	def test_stops_running_completion(self, presenter):
		"""cleanup() stops completion with skip_callbacks=True when running."""
		with (
			patch.object(
				presenter.completion_handler, "is_running", return_value=True
			),
			patch.object(
				presenter.completion_handler, "stop_completion"
			) as mock_stop,
			patch("basilisk.presenters.conversation_presenter.stop_sound"),
			patch.object(presenter, "flush_draft"),
		):
			presenter.cleanup()
		mock_stop.assert_called_once_with(skip_callbacks=True)

	def test_aborts_live_recording_thread(self, presenter):
		"""cleanup() aborts a live recording thread."""
		mock_thread = MagicMock()
		mock_thread.is_alive.return_value = True
		presenter.recording_thread = mock_thread
		with (
			patch("basilisk.presenters.conversation_presenter.stop_sound"),
			patch.object(presenter, "flush_draft"),
		):
			presenter.cleanup()
		mock_thread.abort.assert_called_once()

	def test_skips_abort_when_no_recording_thread(self, presenter):
		"""cleanup() does not raise when recording_thread is None."""
		presenter.recording_thread = None
		with (
			patch("basilisk.presenters.conversation_presenter.stop_sound"),
			patch.object(presenter, "flush_draft"),
		):
			presenter.cleanup()  # must not raise


class TestIsDestroyingGuard:
	"""Tests that callbacks respect the _is_destroying flag."""

	def test_on_completion_start_skips_when_destroying(
		self, presenter, mock_view
	):
		"""_on_completion_start is a no-op when _is_destroying is True."""
		mock_view._is_destroying = True
		presenter._on_completion_start()
		mock_view.submit_btn.Disable.assert_not_called()

	def test_on_completion_end_skips_when_destroying(
		self, presenter, mock_view
	):
		"""_on_completion_end is a no-op when _is_destroying is True."""
		mock_view._is_destroying = True
		presenter._on_completion_end(True)
		mock_view.stop_completion_btn.Hide.assert_not_called()

	def test_on_stream_chunk_skips_when_destroying(self, presenter, mock_view):
		"""_on_stream_chunk is a no-op when _is_destroying is True."""
		mock_view._is_destroying = True
		presenter._on_stream_chunk("text")
		mock_view.messages.append_stream_chunk.assert_not_called()
