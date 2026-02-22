"""Tests for EditBlockPresenter."""

from unittest.mock import MagicMock, patch

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.presenters.edit_block_presenter import EditBlockPresenter
from basilisk.provider_ai_model import AIModelInfo

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def conversation():
	"""Return a Conversation with one complete block."""
	conv = Conversation()
	block = MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Hello"),
		response=Message(role=MessageRoleEnum.ASSISTANT, content="Hi"),
		model=AIModelInfo(provider_id="openai", model_id="gpt-4"),
		temperature=0.7,
		max_tokens=256,
		top_p=1.0,
		stream=True,
	)
	conv.add_block(block)
	return conv


@pytest.fixture
def mock_view(conversation):
	"""Return a mock EditBlockDialog view."""
	view = MagicMock()

	# prompt_panel
	view.prompt_panel.prompt_text = "Hello"
	view.prompt_panel.attachment_files = []
	view.prompt_panel.ensure_model_compatibility.return_value = MagicMock(
		id="gpt-4"
	)
	view.prompt_panel.check_attachments_valid.return_value = True

	# account
	view.current_account = MagicMock()
	view.current_account.provider.id = "openai"

	# model / engine
	view.current_model = MagicMock()
	view.current_model.id = "gpt-4"
	view.current_engine = MagicMock()

	# generation parameters
	view.system_prompt_txt.GetValue.return_value = ""
	view.temperature_spinner.GetValue.return_value = 0.7
	view.top_p_spinner.GetValue.return_value = 1.0
	view.max_tokens_spin_ctrl.GetValue.return_value = 256
	view.stream_mode.GetValue.return_value = True

	# response widget
	view.response_txt = MagicMock()
	view.response_txt.GetValue.return_value = "Hi"

	# UI controls
	view.regenerate_btn = MagicMock()
	view.stop_btn = MagicMock()
	view.a_output = MagicMock()

	# TTS
	view.should_speak_response = False

	view._is_destroying = False
	return view


@pytest.fixture
def presenter(mock_view, conversation):
	"""Return an EditBlockPresenter with mocked view."""
	return EditBlockPresenter(
		view=mock_view, conversation=conversation, block_index=0
	)


# ---------------------------------------------------------------------------
# save_block
# ---------------------------------------------------------------------------


class TestSaveBlock:
	"""Tests for EditBlockPresenter.save_block."""

	def test_all_fields_saved(self, presenter, mock_view, conversation):
		"""save_block should mutate the block with all widget values."""
		mock_view.prompt_panel.prompt_text = "Updated prompt"
		mock_view.prompt_panel.attachment_files = []
		mock_view.system_prompt_txt.GetValue.return_value = "Be helpful"
		mock_view.temperature_spinner.GetValue.return_value = 0.3
		mock_view.max_tokens_spin_ctrl.GetValue.return_value = 512
		mock_view.top_p_spinner.GetValue.return_value = 0.9
		mock_view.stream_mode.GetValue.return_value = False
		mock_view.response_txt.GetValue.return_value = "Updated response"

		result = presenter.save_block()

		assert result is True
		block = conversation.messages[0]
		assert block.request.content == "Updated prompt"
		assert block.temperature == 0.3
		assert block.max_tokens == 512
		assert block.top_p == 0.9
		assert block.stream is False
		assert block.response.content == "Updated response"

	def test_returns_false_when_no_account(self, presenter, mock_view):
		"""save_block should return False when no account is selected."""
		mock_view.current_account = None
		# ensure_model_compatibility returns a model but account is None
		result = presenter.save_block()
		assert result is False

	def test_returns_false_when_model_validation_fails(
		self, presenter, mock_view
	):
		"""save_block should return False when model compatibility fails."""
		mock_view.prompt_panel.ensure_model_compatibility.return_value = None
		result = presenter.save_block()
		assert result is False

	def test_returns_false_when_attachments_invalid(self, presenter, mock_view):
		"""save_block should return False when attachments are invalid."""
		mock_view.prompt_panel.check_attachments_valid.return_value = False
		result = presenter.save_block()
		assert result is False

	def test_system_index_set_when_prompt_present(
		self, presenter, mock_view, conversation
	):
		"""save_block sets system_index when a system prompt is provided."""
		mock_view.system_prompt_txt.GetValue.return_value = "You are helpful"

		presenter.save_block()

		block = conversation.messages[0]
		assert block.system_index is not None

	def test_system_index_cleared_when_no_prompt(
		self, presenter, mock_view, conversation
	):
		"""save_block clears system_index when system prompt is empty."""
		# First set a system index
		conversation.messages[0].system_index = 0
		mock_view.system_prompt_txt.GetValue.return_value = ""

		presenter.save_block()

		assert conversation.messages[0].system_index is None

	def test_attachments_none_when_empty(
		self, presenter, mock_view, conversation
	):
		"""save_block sets attachments to None when list is empty."""
		mock_view.prompt_panel.attachment_files = []
		presenter.save_block()
		assert conversation.messages[0].request.attachments is None


# ---------------------------------------------------------------------------
# start_regenerate
# ---------------------------------------------------------------------------


class TestStartRegenerate:
	"""Tests for EditBlockPresenter.start_regenerate."""

	def test_returns_false_when_model_validation_fails(
		self, presenter, mock_view
	):
		"""start_regenerate should return False on model validation failure."""
		mock_view.prompt_panel.ensure_model_compatibility.return_value = None
		result = presenter.start_regenerate()
		assert result is False

	def test_returns_false_when_no_account(self, presenter, mock_view):
		"""start_regenerate should return False when account is None."""
		mock_view.current_account = None
		result = presenter.start_regenerate()
		assert result is False

	def test_returns_false_when_attachments_invalid(self, presenter, mock_view):
		"""start_regenerate should return False on invalid attachments."""
		mock_view.prompt_panel.check_attachments_valid.return_value = False
		result = presenter.start_regenerate()
		assert result is False

	def test_calls_start_completion_with_temp_block(self, presenter, mock_view):
		"""start_regenerate should call start_completion with a temp block."""
		with patch.object(
			presenter.completion_handler, "start_completion"
		) as mock_start:
			result = presenter.start_regenerate()

		assert result is True
		mock_start.assert_called_once()
		kwargs = mock_start.call_args.kwargs
		assert kwargs["stop_block_index"] == 0
		assert kwargs["engine"] is mock_view.current_engine

	def test_system_message_absent_when_no_prompt(self, presenter, mock_view):
		"""start_regenerate passes system_message=None when prompt is empty."""
		mock_view.system_prompt_txt.GetValue.return_value = ""

		with patch.object(
			presenter.completion_handler, "start_completion"
		) as mock_start:
			presenter.start_regenerate()

		kwargs = mock_start.call_args.kwargs
		assert kwargs["system_message"] is None

	def test_system_message_present_when_prompt_set(self, presenter, mock_view):
		"""start_regenerate passes a SystemMessage when prompt is non-empty."""
		mock_view.system_prompt_txt.GetValue.return_value = "Be concise"

		with patch.object(
			presenter.completion_handler, "start_completion"
		) as mock_start:
			presenter.start_regenerate()

		kwargs = mock_start.call_args.kwargs
		assert isinstance(kwargs["system_message"], SystemMessage)
		assert kwargs["system_message"].content == "Be concise"


# ---------------------------------------------------------------------------
# stop_regenerate
# ---------------------------------------------------------------------------


class TestStopRegenerate:
	"""Tests for EditBlockPresenter.stop_regenerate."""

	def test_delegates_to_completion_handler(self, presenter):
		"""stop_regenerate should call stop_completion on the handler."""
		with patch.object(
			presenter.completion_handler, "stop_completion"
		) as mock_stop:
			presenter.stop_regenerate()

		mock_stop.assert_called_once()


# ---------------------------------------------------------------------------
# _on_regenerate_start
# ---------------------------------------------------------------------------


class TestOnRegenerateStart:
	"""Tests for EditBlockPresenter._on_regenerate_start."""

	def test_hides_regenerate_shows_stop_clears_response(
		self, presenter, mock_view
	):
		"""_on_regenerate_start should swap buttons and clear response."""
		presenter._on_regenerate_start()

		mock_view.regenerate_btn.Hide.assert_called_once()
		mock_view.stop_btn.Show.assert_called_once()
		mock_view.response_txt.SetValue.assert_called_once_with("")
		mock_view.Layout.assert_called_once()


# ---------------------------------------------------------------------------
# _on_regenerate_end
# ---------------------------------------------------------------------------


class TestOnRegenerateEnd:
	"""Tests for EditBlockPresenter._on_regenerate_end."""

	def test_success_shows_regenerate_hides_stop(self, presenter, mock_view):
		"""_on_regenerate_end(True) should restore the regenerate button."""
		with patch("basilisk.presenters.edit_block_presenter.config") as mc:
			mc.conf.return_value.conversation.focus_history_after_send = False
			presenter._on_regenerate_end(True)

		mock_view.stop_btn.Hide.assert_called_once()
		mock_view.regenerate_btn.Show.assert_called_once()

	def test_failure_does_not_focus_response(self, presenter, mock_view):
		"""_on_regenerate_end(False) should not focus the response control."""
		with patch("basilisk.presenters.edit_block_presenter.config") as mc:
			mc.conf.return_value.conversation.focus_history_after_send = True
			presenter._on_regenerate_end(False)

		mock_view.response_txt.SetFocus.assert_not_called()

	def test_success_with_focus_config_focuses_response(
		self, presenter, mock_view
	):
		"""_on_regenerate_end(True) should focus response when config says so."""
		with patch("basilisk.presenters.edit_block_presenter.config") as mc:
			mc.conf.return_value.conversation.focus_history_after_send = True
			presenter._on_regenerate_end(True)

		mock_view.response_txt.SetFocus.assert_called_once()


# ---------------------------------------------------------------------------
# _on_non_stream_finish
# ---------------------------------------------------------------------------


class TestOnNonStreamFinish:
	"""Tests for EditBlockPresenter._on_non_stream_finish."""

	def test_sets_response_value(self, presenter, mock_view, conversation):
		"""_on_non_stream_finish should set the response text control."""
		block = conversation.messages[0]
		presenter._on_non_stream_finish(block, None)

		mock_view.response_txt.SetValue.assert_called_once_with(
			block.response.content
		)

	def test_speaks_when_should_speak(self, presenter, mock_view, conversation):
		"""_on_non_stream_finish should call a_output.handle when speaking."""
		mock_view.should_speak_response = True
		block = conversation.messages[0]
		presenter._on_non_stream_finish(block, None)

		mock_view.a_output.handle.assert_called_once_with(
			block.response.content
		)

	def test_no_speak_when_should_not_speak(
		self, presenter, mock_view, conversation
	):
		"""_on_non_stream_finish should not speak when flag is False."""
		mock_view.should_speak_response = False
		block = conversation.messages[0]
		presenter._on_non_stream_finish(block, None)

		mock_view.a_output.handle.assert_not_called()


# ---------------------------------------------------------------------------
# _on_stream_chunk
# ---------------------------------------------------------------------------


class TestOnStreamChunk:
	"""Tests for EditBlockPresenter._on_stream_chunk."""

	def test_appends_text_and_restores_insertion_point(
		self, presenter, mock_view
	):
		"""_on_stream_chunk should AppendText and restore insertion point."""
		mock_view.response_txt.GetInsertionPoint.return_value = 5
		mock_view.should_speak_response = False

		presenter._on_stream_chunk("hello")

		mock_view.response_txt.AppendText.assert_called_once_with("hello")
		mock_view.response_txt.SetInsertionPoint.assert_called_once_with(5)

	def test_speaks_when_should_speak(self, presenter, mock_view):
		"""_on_stream_chunk should call handle_stream_buffer when speaking."""
		mock_view.should_speak_response = True
		mock_view.response_txt.GetInsertionPoint.return_value = 0

		presenter._on_stream_chunk("chunk")

		mock_view.a_output.handle_stream_buffer.assert_called_once_with(
			new_text="chunk"
		)

	def test_no_speak_when_should_not_speak(self, presenter, mock_view):
		"""_on_stream_chunk should not call handle_stream_buffer when silent."""
		mock_view.should_speak_response = False
		mock_view.response_txt.GetInsertionPoint.return_value = 0

		presenter._on_stream_chunk("chunk")

		mock_view.a_output.handle_stream_buffer.assert_not_called()


# ---------------------------------------------------------------------------
# _on_stream_finish
# ---------------------------------------------------------------------------


class TestOnStreamFinish:
	"""Tests for EditBlockPresenter._on_stream_finish."""

	def test_calls_handle_stream_buffer(
		self, presenter, mock_view, conversation
	):
		"""_on_stream_finish should flush the accessible output buffer."""
		block = conversation.messages[0]
		presenter._on_stream_finish(block)

		mock_view.a_output.handle_stream_buffer.assert_called_once()
