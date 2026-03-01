"""Tests for ConversationPresenter."""

from unittest.mock import MagicMock

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
def mock_view(conversation_view_base):
	"""Return a mock ConversationTab view with required attributes."""
	view = conversation_view_base
	view.submit_btn.IsEnabled.return_value = True
	view.messages.should_speak_response = False
	view.web_search_mode.GetValue.return_value = False
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

	def test_stores_content_and_starts_completion(
		self, presenter, mock_view, mocker
	):
		"""Submit with content should store prompt and start completion."""
		mock_view.prompt_panel.prompt_text = "Hello"
		mock_view.prompt_panel.attachment_files = []
		mock_view.prompt_panel.ensure_model_compatibility.return_value = (
			mock_view.current_model
		)
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)
		presenter.on_submit()

		mock_view.prompt_panel.clear.assert_called_once_with(refresh=True)
		mock_start.assert_called_once()


class TestOnCompletionError:
	"""Tests for _on_completion_error."""

	def test_restores_prompt(self, presenter, mock_view):
		"""Error should restore the saved prompt content."""
		presenter._stored_prompt_text = "my prompt"
		presenter._stored_attachments = []

		presenter._on_completion_error("test error")

		assert mock_view.prompt_panel.prompt_text == "my prompt"
		assert presenter._stored_prompt_text is None
		mock_view.show_enhanced_error.assert_called_once()


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

	def test_dispatches_start_when_not_recording(
		self, presenter, mock_view, mocker
	):
		"""Toggle should call start_recording when not already recording."""
		presenter.recording_thread = None
		mock_start = mocker.patch.object(presenter, "start_recording")
		presenter.toggle_recording()
		mock_start.assert_called_once()

	def test_dispatches_stop_when_recording(self, presenter, mock_view, mocker):
		"""Toggle should call stop_recording when already recording."""
		mock_thread = MagicMock()
		mock_thread.is_alive.return_value = True
		presenter.recording_thread = mock_thread
		mock_stop = mocker.patch.object(presenter, "stop_recording")
		presenter.toggle_recording()
		mock_stop.assert_called_once()


class TestBuildDraftBlock:
	"""Tests for _build_draft_block guard conditions."""

	@pytest.mark.parametrize(
		("mutate", "reason"),
		[
			(lambda v: setattr(v, "current_account", None), "no_account"),
			(lambda v: setattr(v, "current_model", None), "no_model"),
			(
				lambda v: None,  # default: prompt_text="" + attachment_files=[]
				"empty_prompt",
			),
		],
		ids=["no_account", "no_model", "empty_prompt"],
	)
	def test_returns_none_on_guard(self, presenter, mock_view, mutate, reason):
		"""_build_draft_block returns None when guard conditions are not met."""
		mutate(mock_view)
		assert presenter._build_draft_block() is None

	def test_returns_block_when_prompt_present(self, presenter, mock_view):
		"""_build_draft_block returns a MessageBlock when prompt is non-empty."""
		mock_view.prompt_panel.prompt_text = "draft text"
		result = presenter._build_draft_block()
		assert result is not None
		assert result.request.content == "draft text"


class TestCleanup:
	"""Tests for cleanup() resource teardown."""

	def test_stops_running_completion(self, presenter, mocker):
		"""cleanup() stops completion with skip_callbacks=True when running."""
		mocker.patch.object(
			presenter.completion_handler, "is_running", return_value=True
		)
		mock_stop = mocker.patch.object(
			presenter.completion_handler, "stop_completion"
		)
		mocker.patch("basilisk.presenters.conversation_presenter.stop_sound")
		mocker.patch.object(presenter, "flush_draft")
		presenter.cleanup()
		mock_stop.assert_called_once_with(skip_callbacks=True)

	def test_aborts_live_recording_thread(self, presenter, mocker):
		"""cleanup() aborts a live recording thread."""
		mock_thread = MagicMock()
		mock_thread.is_alive.return_value = True
		presenter.recording_thread = mock_thread
		mocker.patch("basilisk.presenters.conversation_presenter.stop_sound")
		mocker.patch.object(presenter, "flush_draft")
		presenter.cleanup()
		mock_thread.abort.assert_called_once()

	def test_skips_abort_when_no_recording_thread(self, presenter, mocker):
		"""cleanup() does not raise when recording_thread is None."""
		presenter.recording_thread = None
		mocker.patch("basilisk.presenters.conversation_presenter.stop_sound")
		mocker.patch.object(presenter, "flush_draft")
		presenter.cleanup()  # must not raise


class TestIsDestroyingGuard:
	"""Tests that callbacks respect the _is_destroying flag."""

	@pytest.mark.parametrize(
		("callback", "args", "spy_attr"),
		[
			("_on_completion_start", (), "submit_btn.Disable"),
			("_on_completion_end", (True,), "stop_completion_btn.Hide"),
			("_on_stream_chunk", ("text",), "messages.append_stream_chunk"),
		],
		ids=["completion_start", "completion_end", "stream_chunk"],
	)
	def test_skips_when_destroying(
		self, presenter, mock_view, callback, args, spy_attr
	):
		"""All guarded callbacks are no-ops when _is_destroying is True."""
		mock_view._is_destroying = True
		getattr(presenter, callback)(*args)
		target = mock_view
		for attr in spy_attr.split("."):
			target = getattr(target, attr)
		target.assert_not_called()


class TestOnStreamFinish:
	"""Tests for _on_stream_finish."""

	def test_calls_auto_save_to_db(self, presenter, mock_service):
		"""_on_stream_finish delegates auto-save to the service."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter._on_stream_finish(block)
		mock_service.auto_save_to_db.assert_called_once_with(
			presenter.conversation, block
		)

	def test_flushes_stream_buffer(self, presenter, mock_view):
		"""_on_stream_finish flushes the accessible output buffer."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter._on_stream_finish(block)
		mock_view.messages.a_output.handle_stream_buffer.assert_called_once()
		mock_view.messages.update_last_segment_length.assert_called_once()

	def test_skips_when_destroying(self, presenter, mock_view, mock_service):
		"""_on_stream_finish is a no-op when _is_destroying is True."""
		mock_view._is_destroying = True
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter._on_stream_finish(block)
		mock_service.auto_save_to_db.assert_not_called()


class TestOnNonStreamFinish:
	"""Tests for _on_non_stream_finish."""

	def test_adds_block_and_saves(self, presenter, mock_view, mock_service):
		"""_on_non_stream_finish adds block to conversation and auto-saves."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		system_msg = SystemMessage(content="Be helpful")
		presenter._on_non_stream_finish(block, system_msg)
		assert block in presenter.conversation.messages
		mock_view.messages.display_new_block.assert_called_once_with(block)
		mock_service.auto_save_to_db.assert_called_once_with(
			presenter.conversation, block
		)

	def test_speaks_response_when_enabled(self, presenter, mock_view):
		"""_on_non_stream_finish speaks the response when should_speak_response is True."""
		mock_view.messages.should_speak_response = True
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter._on_non_stream_finish(block, None)
		mock_view.messages.a_output.handle.assert_called_once_with("Hello")

	def test_skips_when_destroying(self, presenter, mock_view, mock_service):
		"""_on_non_stream_finish is a no-op when _is_destroying is True."""
		mock_view._is_destroying = True
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter._on_non_stream_finish(block, None)
		mock_service.auto_save_to_db.assert_not_called()


class TestStartRecording:
	"""Tests for start_recording."""

	def test_returns_early_when_no_engine(self, presenter, mock_view):
		"""start_recording returns silently when current_engine is None."""
		mock_view.current_engine = None
		presenter.start_recording()
		mock_view.show_error.assert_not_called()

	def test_shows_error_when_stt_not_supported(self, presenter, mock_view):
		"""start_recording calls view.show_error when STT unsupported."""
		mock_view.current_engine.capabilities = set()  # no STT
		presenter.start_recording()
		mock_view.show_error.assert_called_once()

	def test_calls_transcribe_when_stt_supported(
		self, presenter, mock_view, mocker
	):
		"""start_recording calls transcribe_audio_file when STT is available."""
		from basilisk.provider_capability import ProviderCapability

		mock_view.current_engine.capabilities = {ProviderCapability.STT}
		mock_transcribe = mocker.patch.object(
			presenter, "transcribe_audio_file"
		)
		presenter.start_recording()

		mock_transcribe.assert_called_once_with()
		mock_view.show_error.assert_not_called()


class TestTranscribeAudioFile:
	"""Tests for transcribe_audio_file."""

	def test_creates_new_thread_when_none(self, presenter, mock_view, mocker):
		"""transcribe_audio_file creates a RecordingThread when none exists."""
		presenter.recording_thread = None

		mock_thread_cls = MagicMock()
		mock_thread_instance = MagicMock()
		mock_thread_cls.return_value = mock_thread_instance

		mocker.patch(
			"basilisk.recording_thread.RecordingThread", mock_thread_cls
		)
		presenter.transcribe_audio_file()

		mock_thread_cls.assert_called_once()
		mock_thread_instance.start.assert_called_once()

	def test_reuses_class_when_thread_exists(self, presenter, mock_view):
		"""transcribe_audio_file starts a new thread of the same class when active."""
		mock_thread = MagicMock()
		presenter.recording_thread = mock_thread

		presenter.transcribe_audio_file("audio.mp3")

		assert presenter.recording_thread is not mock_thread
		presenter.recording_thread.start.assert_called_once()

	def test_passes_audio_file_to_thread(self, presenter, mock_view, mocker):
		"""transcribe_audio_file passes audio_file arg to RecordingThread."""
		presenter.recording_thread = None

		mock_thread_cls = MagicMock()
		mocker.patch(
			"basilisk.recording_thread.RecordingThread", mock_thread_cls
		)
		presenter.transcribe_audio_file("/path/to/audio.mp3")

		call_kwargs = mock_thread_cls.call_args[1]
		assert call_kwargs["audio_file_path"] == "/path/to/audio.mp3"


class TestGenerateConversationTitle:
	"""Tests for generate_conversation_title."""

	def test_returns_none_when_completion_running(
		self, presenter, mock_view, mocker
	):
		"""Returns None and shows error when a completion is in progress."""
		mocker.patch.object(
			presenter.completion_handler, "is_running", return_value=True
		)
		result = presenter.generate_conversation_title()

		assert result is None
		mock_view.show_error.assert_called_once()

	def test_returns_none_when_no_messages(self, presenter, mocker):
		"""Returns None silently when conversation has no messages."""
		mocker.patch.object(
			presenter.completion_handler, "is_running", return_value=False
		)
		result = presenter.generate_conversation_title()
		assert result is None

	def test_returns_title_on_success(
		self, presenter, mock_view, mock_service, mocker
	):
		"""Returns the generated title when service succeeds."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter.conversation.add_block(block, None)
		mock_service.generate_title.return_value = "My Conversation"

		mocker.patch.object(
			presenter.completion_handler, "is_running", return_value=False
		)
		result = presenter.generate_conversation_title()

		assert result == "My Conversation"

	def test_shows_error_when_title_none_but_messages_exist(
		self, presenter, mock_view, mock_service, mocker
	):
		"""Shows enhanced error dialog when service returns None but messages exist."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Hi"),
			response=Message(role=MessageRoleEnum.ASSISTANT, content="Hello"),
			model=AIModelInfo(provider_id="openai", model_id="test"),
		)
		presenter.conversation.add_block(block, None)
		mock_service.generate_title.return_value = None

		mocker.patch.object(
			presenter.completion_handler, "is_running", return_value=False
		)
		result = presenter.generate_conversation_title()

		assert result is None
		mock_view.show_enhanced_error.assert_called_once()
