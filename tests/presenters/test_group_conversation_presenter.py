"""Unit tests for GroupConversationPresenter.

Tests the chain orchestration logic in isolation using mock views and
a mock CompletionHandler so no real LLM calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

from basilisk.conversation import Conversation, GroupParticipant
from basilisk.presenters.group_conversation_presenter import (
	GroupConversationPresenter,
)
from basilisk.provider_ai_model import AIModelInfo

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_participant(
	name: str = "Alice", provider: str = "openai"
) -> GroupParticipant:
	"""Build a minimal GroupParticipant for testing."""
	return GroupParticipant(
		profile_id=uuid4(),
		name=name,
		system_prompt="",
		account_info={"id": str(uuid4())},
		ai_model_info=AIModelInfo(provider_id=provider, model_id="gpt-4o"),
		max_tokens=4096,
		temperature=1.0,
		top_p=1.0,
		stream_mode=False,
	)


def _make_mock_view() -> MagicMock:
	"""Return a minimal mock GroupConversationTab view."""
	view = MagicMock()
	view._is_destroying = False
	view.get_prompt_text.return_value = "Hello!"
	view.get_attachment_files.return_value = []
	view.get_debate_rounds.return_value = 2
	view.messages = MagicMock()
	view.messages.should_speak_response = False
	view.messages.a_output = MagicMock()
	return view


def _make_presenter(
	participants=None, view=None, service=None
) -> GroupConversationPresenter:
	"""Build a GroupConversationPresenter with mocked collaborators."""
	if participants is None:
		participants = [_make_participant("Alice"), _make_participant("Bob")]
	if view is None:
		view = _make_mock_view()
	if service is None:
		service = MagicMock()
	conversation = Conversation(group_participants=participants)
	presenter = GroupConversationPresenter(
		view=view,
		service=service,
		conversation=conversation,
		conv_storage_path=MagicMock(),
		participants=participants,
	)
	return presenter


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestNormalModeChain:
	"""Tests for normal (user-driven) mode chain progression."""

	def test_chain_calls_all_participants(self, mocker):
		"""Normal mode should submit one completion per participant."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_engine = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=mock_engine)

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)

		presenter.on_submit()

		# First participant submitted immediately
		assert mock_start.call_count == 1
		assert presenter._current_participant_index == 0

		# Simulate first completion ending successfully
		presenter._on_completion_end(True)
		assert mock_start.call_count == 2
		assert presenter._current_participant_index == 1

		# Simulate second completion ending successfully
		presenter._on_completion_end(True)
		assert mock_start.call_count == 2  # No more submissions
		assert not presenter._is_running_chain

	def test_error_stops_chain(self, mocker):
		"""An error on any participant stops the chain immediately."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=MagicMock())

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)

		presenter.on_submit()
		assert mock_start.call_count == 1

		# First participant errors
		presenter._on_completion_error("API error")

		# No further submissions
		assert mock_start.call_count == 1
		assert not presenter._is_running_chain

	def test_stop_mid_chain(self, mocker):
		"""Calling on_stop() stops the running completion."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=MagicMock())

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		mocker.patch.object(presenter.completion_handler, "start_completion")
		mock_stop = mocker.patch.object(
			presenter.completion_handler, "stop_completion"
		)

		presenter.on_submit()
		presenter.on_stop()

		mock_stop.assert_called_once()
		assert not presenter._is_running_chain


class TestDebateModeRounds:
	"""Tests for debate (autonomous) mode round progression."""

	def test_debate_progresses_through_rounds(self, mocker):
		"""Debate mode should iterate through N rounds × M participants."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=MagicMock())

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)

		# Start debate with 2 rounds, 2 participants → 4 total completions
		presenter.on_start_debate()
		assert presenter._mode == "debate"
		assert presenter._total_rounds == 2

		# Round 0, participant 0
		assert mock_start.call_count == 1
		presenter._on_completion_end(True)

		# Round 0, participant 1
		assert mock_start.call_count == 2
		presenter._on_completion_end(True)

		# Round 1, participant 0
		assert mock_start.call_count == 3
		assert presenter._current_round == 1
		presenter._on_completion_end(True)

		# Round 1, participant 1
		assert mock_start.call_count == 4
		presenter._on_completion_end(True)

		# Chain done
		assert not presenter._is_running_chain

	def test_debate_uses_empty_sentinel_in_round_1(self, mocker):
		"""Subsequent debate rounds should use an empty request content."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=MagicMock())

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)

		presenter.on_start_debate()

		# Complete round 0 for both participants
		presenter._on_completion_end(True)
		presenter._on_completion_end(True)

		# Round 1 starts — the request in the new_block should be empty
		assert mock_start.call_count == 3
		call_kwargs = mock_start.call_args.kwargs
		assert call_kwargs["new_block"].request.content == ""


class TestGuardDestroying:
	"""Tests for _guard_destroying protection on callbacks."""

	def test_callbacks_noop_when_destroying(self, mocker):
		"""All guarded callbacks are no-ops after view._is_destroying = True."""
		presenter = _make_presenter()
		presenter.view._is_destroying = True

		mock_start = mocker.patch.object(
			presenter.completion_handler, "start_completion"
		)

		# These should all be no-ops
		presenter._on_completion_start()
		presenter._on_completion_end(True)
		presenter._on_stream_chunk("chunk")
		presenter._on_stream_start(MagicMock(), None)
		presenter._on_stream_finish(MagicMock())
		presenter._on_non_stream_finish(MagicMock(), None)
		presenter._on_completion_error("err")

		mock_start.assert_not_called()
		# View methods should not have been called
		presenter.view.on_completion_start.assert_not_called()


class TestGroupIdGeneration:
	"""Tests for group_id and group_position on emitted blocks."""

	def test_all_participants_share_group_id(self, mocker):
		"""All blocks in one round share the same group_id."""
		presenter = _make_presenter()

		mock_account = MagicMock()
		mock_account.provider = MagicMock()
		mock_account.provider.id = "openai"
		mock_account.provider.engine_cls = MagicMock(return_value=MagicMock())

		mocker.patch.object(
			presenter, "_resolve_account", return_value=mock_account
		)
		blocks_seen = []

		def capture_start(**kwargs):
			"""Record the new_block passed to start_completion."""
			blocks_seen.append(kwargs["new_block"])

		mocker.patch.object(
			presenter.completion_handler,
			"start_completion",
			side_effect=capture_start,
		)

		presenter.on_submit()
		presenter._on_completion_end(True)

		assert len(blocks_seen) == 2
		assert blocks_seen[0].group_id == blocks_seen[1].group_id
		assert blocks_seen[0].group_position == 0
		assert blocks_seen[1].group_position == 1
