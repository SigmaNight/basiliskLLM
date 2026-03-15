"""Tests for conversation properties dialog formatting."""

from datetime import datetime, timezone

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.conversation_model import TokenUsage
from basilisk.provider_ai_model import AIModelInfo
from basilisk.views.conversation_properties_dialog import (
	_cost_items,
	_format_conversation_properties,
	_models_items,
	_timestamps_items,
	_token_usage_items,
)


def _conv_with_blocks(usage_tuples, costs=None):
	"""Create conversation with blocks having given (input, output) usage."""
	conv = Conversation()
	model = AIModelInfo(provider_id="openai", model_id="gpt-4")
	base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
	for i, (inp, out) in enumerate(usage_tuples):
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=model,
			usage=TokenUsage(input_tokens=inp, output_tokens=out),
			created_at=base,
			updated_at=base,
		)
		if costs is not None and i < len(costs):
			block.cost = costs[i]
		conv.add_block(block)
	return conv


class TestTokenUsageItems:
	"""Tests for _token_usage_items."""

	def test_empty_usage_placeholder(self):
		"""Returns placeholder when token_total is 0."""
		conv = Conversation()
		conv.title = "Empty"
		items = _token_usage_items(conv)
		assert isinstance(items, list)
		assert len(items) == 1
		assert items[0][0] == ""
		assert "No usage" in items[0][1]

	def test_aggregates_totals(self):
		"""Includes Total tokens, Input, Output with percentages."""
		conv = _conv_with_blocks([(100, 50), (200, 80)])
		items = _token_usage_items(conv)
		labels = [it[0] for it in items]
		assert "Total tokens" in labels or any(
			"Total" in str(label) for label in labels
		)
		assert any("Input" in str(label) for label in labels)
		assert any("Output" in str(label) for label in labels)


class TestCostItems:
	"""Tests for _cost_items."""

	def test_none_returns_placeholder(self):
		"""Returns placeholder when cost_total is None."""
		conv = Conversation()
		items = _cost_items(conv, None, 0)
		assert len(items) == 1
		assert "Not available" in items[0][1]

	def test_has_total_and_mean_per_mtok(self):
		"""Includes Total and Mean per MTok when total > 0."""
		conv = Conversation()
		items = _cost_items(conv, 0.05, 1000)
		labels = [it[0] for it in items]
		assert "Total" in labels
		assert any("MTok" in str(label) for label in labels)


class TestModelsItems:
	"""Tests for _models_items."""

	def test_single_model_bullet_format(self):
		"""Single model returns bullet + model id."""
		conv = _conv_with_blocks([(10, 5)])
		items = _models_items(conv, 15, None)
		assert len(items) == 1
		assert items[0][0] == ""
		assert "•" in items[0][1]
		assert "openai/gpt-4" in items[0][1]

	def test_multiple_models(self):
		"""Multiple models get per-model stats."""
		conv = Conversation()
		model_a = AIModelInfo(provider_id="openai", model_id="gpt-4")
		model_b = AIModelInfo(provider_id="anthropic", model_id="claude-3")
		base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
		for model in [model_a, model_b]:
			req = Message(role=MessageRoleEnum.USER, content="q")
			resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
			block = MessageBlock(
				request=req,
				response=resp,
				model=model,
				usage=TokenUsage(input_tokens=100, output_tokens=50),
				created_at=base,
				updated_at=base,
			)
			conv.add_block(block)
		items = _models_items(conv, 300, 0.001)
		assert len(items) == 2


class TestTimestampsItems:
	"""Tests for _timestamps_items."""

	def test_includes_started_and_last_activity(self):
		"""Includes Started and Last activity."""
		conv = _conv_with_blocks([(10, 5)])
		items = _timestamps_items(conv)
		labels = [it[0] for it in items]
		assert "Started" in labels
		assert "Last activity" in labels


class TestFormatConversationProperties:
	"""Tests for _format_conversation_properties."""

	def test_returns_text_and_sections(self):
		"""Returns (text, section_line_indices) tuple."""
		conv = _conv_with_blocks([(100, 50)])
		conv.title = "Test"
		text, sections = _format_conversation_properties(conv)
		assert isinstance(text, str)
		assert isinstance(sections, list)
		assert len(sections) > 0
		assert "Overview" in text
		assert "Token usage" in text
		assert "Timestamps" in text
