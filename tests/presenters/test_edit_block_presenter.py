"""Tests for EditBlockPresenter."""

from unittest.mock import MagicMock

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
def mock_view(conversation_view_base):
	"""Return a mock EditBlockDialog view."""
	view = conversation_view_base
	view.prompt_panel.prompt_text = "Hello"
	view.prompt_panel.ensure_model_compatibility.return_value = MagicMock(
		id="gpt-4"
	)
	view.temperature_spinner.GetValue.return_value = 0.7
	view.max_tokens_spin_ctrl.GetValue.return_value = 256
	view.response_txt.GetValue.return_value = "Hi"
	view.should_speak_response = False
	return view


@pytest.fixture
def presenter(mock_view, conversation):
	"""Return an EditBlockPresenter with mocked view."""
	return EditBlockPresenter(
		view=mock_view, conversation=conversation, block_index=0
	)


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

	@pytest.mark.parametrize(
		"mutate",
		[
			lambda v: setattr(v, "current_account", None),
			lambda v: setattr(
				v.prompt_panel.ensure_model_compatibility, "return_value", None
			),
			lambda v: setattr(
				v.prompt_panel.check_attachments_valid, "return_value", False
			),
		],
		ids=["no_account", "model_validation_fails", "attachments_invalid"],
	)
	def test_returns_false_on_validation_failure(
		self, presenter, mock_view, mutate
	):
		"""save_block returns False when validation conditions are not met."""
		mutate(mock_view)
		assert presenter.save_block() is False

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

	def test_calls_auto_save_to_db_on_success(self, mock_view, conversation):
		"""save_block calls service.auto_save_to_db when service is provided."""
		service = MagicMock()
		p = EditBlockPresenter(
			view=mock_view,
			conversation=conversation,
			block_index=0,
			service=service,
		)

		result = p.save_block()

		assert result is True
		service.auto_save_to_db.assert_called_once_with(
			conversation, conversation.messages[0]
		)

	def test_no_auto_save_on_validation_failure(self, mock_view, conversation):
		"""save_block does not call auto_save_to_db when validation fails."""
		service = MagicMock()
		mock_view.current_account = None
		p = EditBlockPresenter(
			view=mock_view,
			conversation=conversation,
			block_index=0,
			service=service,
		)

		result = p.save_block()

		assert result is False
		service.auto_save_to_db.assert_not_called()

	def test_updated_at_refreshed_on_success(self, mock_view, conversation):
		"""save_block updates block.updated_at to the current time."""
		block = conversation.messages[0]
		original_updated_at = block.updated_at
		p = EditBlockPresenter(
			view=mock_view, conversation=conversation, block_index=0
		)

		p.save_block()

		assert block.updated_at >= original_updated_at


class TestStartRegenerate:
	"""Tests for EditBlockPresenter.start_regenerate."""

	@pytest.mark.parametrize(
		"mutate",
		[
			lambda v: setattr(v, "current_account", None),
			lambda v: setattr(
				v.prompt_panel.ensure_model_compatibility, "return_value", None
			),
			lambda v: setattr(
				v.prompt_panel.check_attachments_valid, "return_value", False
			),
		],
		ids=["no_account", "model_validation_fails", "attachments_invalid"],
	)
	def test_returns_false_on_validation_failure(
		self, presenter, mock_view, mutate
	):
		"""start_regenerate returns False when validation conditions are not met."""
		mutate(mock_view)
		assert presenter.start_regenerate() is False

	def test_calls_start_completion_with_temp_block(
		self, presenter, mock_view, mocker
	):
		"""start_regenerate should call start_completion with a temp block."""
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)
		result = presenter.start_regenerate()

		assert result is True
		mock_start.assert_called_once()
		kwargs = mock_start.call_args.kwargs
		assert kwargs["stop_block_index"] == 0
		assert kwargs["engine"] is mock_view.current_engine

	def test_system_message_absent_when_no_prompt(
		self, presenter, mock_view, mocker
	):
		"""start_regenerate passes system_message=None when prompt is empty."""
		mock_view.system_prompt_txt.GetValue.return_value = ""
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)
		presenter.start_regenerate()

		kwargs = mock_start.call_args.kwargs
		assert kwargs["system_message"] is None

	def test_system_message_present_when_prompt_set(
		self, presenter, mock_view, mocker
	):
		"""start_regenerate passes a SystemMessage when prompt is non-empty."""
		mock_view.system_prompt_txt.GetValue.return_value = "Be concise"
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)
		presenter.start_regenerate()

		kwargs = mock_start.call_args.kwargs
		assert isinstance(kwargs["system_message"], SystemMessage)
		assert kwargs["system_message"].content == "Be concise"


class TestStopRegenerate:
	"""Tests for EditBlockPresenter.stop_regenerate."""

	def test_delegates_to_completion_handler(self, presenter, mocker):
		"""stop_regenerate should call stop_completion on the handler."""
		mock_stop = mocker.patch.object(
			presenter.completion_handler, "stop_completion"
		)
		presenter.stop_regenerate()

		mock_stop.assert_called_once()


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


class TestOnRegenerateEnd:
	"""Tests for EditBlockPresenter._on_regenerate_end."""

	@pytest.mark.parametrize(
		("success", "focus_config", "expect_focus"),
		[(True, False, False), (False, True, False), (True, True, True)],
		ids=["success_no_focus", "failure_no_focus", "success_with_focus"],
	)
	def test_on_regenerate_end(
		self, presenter, mock_view, mocker, success, focus_config, expect_focus
	):
		"""_on_regenerate_end shows buttons on success and optionally focuses response."""
		mc = mocker.patch("basilisk.presenters.edit_block_presenter.config")
		mc.conf.return_value.conversation.focus_history_after_send = (
			focus_config
		)

		presenter._on_regenerate_end(success)

		if success:
			mock_view.stop_btn.Hide.assert_called_once()
			mock_view.regenerate_btn.Show.assert_called_once()
		if expect_focus:
			mock_view.response_txt.SetFocus.assert_called_once()
		else:
			mock_view.response_txt.SetFocus.assert_not_called()


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


class TestOnStreamFinish:
	"""Tests for EditBlockPresenter._on_stream_finish."""

	def test_calls_handle_stream_buffer(
		self, presenter, mock_view, conversation
	):
		"""_on_stream_finish should flush the accessible output buffer."""
		block = conversation.messages[0]
		presenter._on_stream_finish(block)

		mock_view.a_output.handle_stream_buffer.assert_called_once()
