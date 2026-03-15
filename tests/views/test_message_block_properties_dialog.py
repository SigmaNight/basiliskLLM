"""Tests for message block properties dialog formatting."""

from datetime import datetime, timezone

from basilisk.conversation import Message, MessageBlock, MessageRoleEnum
from basilisk.conversation.conversation_model import ResponseTiming, TokenUsage
from basilisk.provider_ai_model import AIModelInfo
from basilisk.views.message_block_properties_dialog import (
	_format_block_properties,
	_format_request_section,
	_format_timing_section,
	_format_usage_section,
)


def _block_with_usage():
	"""Create block with usage data."""
	model = AIModelInfo(provider_id="openai", model_id="gpt-4")
	req = Message(role=MessageRoleEnum.USER, content="Hello")
	resp = Message(role=MessageRoleEnum.ASSISTANT, content="Hi")
	return MessageBlock(
		request=req,
		response=resp,
		model=model,
		usage=TokenUsage(input_tokens=100, output_tokens=50),
	)


def _block_with_timing():
	"""Create block with timing data."""
	model = AIModelInfo(provider_id="openai", model_id="gpt-4")
	req = Message(role=MessageRoleEnum.USER, content="q")
	resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
	base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
	return MessageBlock(
		request=req,
		response=resp,
		model=model,
		timing=ResponseTiming(
			started_at=base,
			request_sent_at=base,
			finished_at=base.replace(second=5),
			duration_seconds=5.0,
		),
	)


class TestFormatRequestSection:
	"""Tests for _format_request_section."""

	def test_includes_model_and_params(self):
		"""Includes model and common params."""
		block = _block_with_usage()
		lines = _format_request_section(block)
		assert len(lines) >= 2
		assert "Request" in lines[0]
		assert "openai/gpt-4" in "\n".join(lines)


class TestFormatUsageSection:
	"""Tests for _format_usage_section."""

	def test_no_usage_placeholder(self):
		"""Returns placeholder when block has no usage."""
		model = AIModelInfo(provider_id="openai", model_id="gpt-4")
		req = Message(role=MessageRoleEnum.USER, content="q")
		block = MessageBlock(request=req, model=model)
		lines = _format_usage_section(block)
		assert "Response consumption" in lines[0]
		assert "No usage" in "\n".join(lines)

	def test_includes_input_output_total(self):
		"""Includes input, output, total tokens."""
		block = _block_with_usage()
		lines = _format_usage_section(block)
		text = "\n".join(lines)
		assert "100" in text
		assert "50" in text
		assert "150" in text or "Total" in text

	def test_includes_cost_breakdown_when_present(self):
		"""Includes cost breakdown subsection when block has cost_breakdown."""
		block = _block_with_usage()
		block.cost_breakdown = {"input": 0.0001, "output": 0.0001}
		lines = _format_usage_section(block)
		text = "\n".join(lines)
		assert "Cost breakdown" in text or "breakdown" in text.lower()


class TestFormatTimingSection:
	"""Tests for _format_timing_section."""

	def test_no_timing_placeholder(self):
		"""Returns placeholder when block has no timing."""
		block = _block_with_usage()
		lines = _format_timing_section(block)
		assert "Timing" in lines[0]
		assert "No timing" in "\n".join(lines)

	def test_includes_duration_and_timestamps(self):
		"""Includes Total duration and Timestamps."""
		block = _block_with_timing()
		lines = _format_timing_section(block)
		text = "\n".join(lines)
		assert "5.00" in text or "5.0" in text
		assert "Timestamps" in text
		assert "Started" in text


class TestFormatBlockProperties:
	"""Tests for _format_block_properties."""

	def test_returns_text_and_sections(self):
		"""Returns (text, section_line_indices) tuple."""
		block = _block_with_usage()
		block.timing = ResponseTiming(
			started_at=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
			finished_at=datetime(2026, 1, 1, 12, 0, 5, tzinfo=timezone.utc),
		)
		text, sections = _format_block_properties(block)
		assert isinstance(text, str)
		assert isinstance(sections, list)
		assert len(sections) >= 3  # Request, Response consumption, Timing
		assert "Request" in text
		assert "Response consumption" in text
		assert "Timing" in text
