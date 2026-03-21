"""Unit tests for content_utils."""

from basilisk.conversation.content_utils import (
	END_REASONING,
	REASONING_DISPLAY_END,
	REASONING_DISPLAY_START,
	START_BLOCK_REASONING,
	format_response_for_display,
	split_reasoning_and_content,
	split_reasoning_and_content_from_display,
)


class TestSplitReasoningAndContent:
	"""Tests for split_reasoning_and_content (legacy ```think...``` format)."""

	def test_empty_string(self):
		"""Empty string returns (None, '')."""
		assert split_reasoning_and_content("") == (None, "")

	def test_no_think_block(self):
		"""Plain content without think block returns (None, content)."""
		text = "Hello, world!"
		assert split_reasoning_and_content(text) == (None, text)

	def test_simple_think_block(self):
		"""Single think block is extracted."""
		text = "```think\nLet me reason about this.\n```\n\nHere is the answer."
		reasoning, content = split_reasoning_and_content(text)
		assert reasoning == "Let me reason about this."
		assert content == "Here is the answer."

	def test_think_block_with_extra_whitespace(self):
		"""Think block content is stripped."""
		text = "```think\n  inner thought  \n```\n\nresponse"
		reasoning, content = split_reasoning_and_content(text)
		assert reasoning == "inner thought"
		assert content == "response"

	def test_think_block_multiline_reasoning(self):
		"""Multiline reasoning is preserved."""
		text = (
			"```think\nStep 1: analyze\nStep 2: conclude\n```\n\nFinal answer."
		)
		reasoning, content = split_reasoning_and_content(text)
		assert reasoning == "Step 1: analyze\nStep 2: conclude"
		assert content == "Final answer."

	def test_empty_reasoning_returns_none(self):
		"""Empty reasoning after strip returns None."""
		text = "```think\n   \n```\n\ncontent"
		reasoning, content = split_reasoning_and_content(text)
		assert reasoning is None
		assert content == "content"


class TestSplitReasoningAndContentFromDisplay:
	"""Tests for split_reasoning_and_content_from_display (<think>...</think> format)."""

	def test_empty_string(self):
		"""Empty string returns (None, '')."""
		assert split_reasoning_and_content_from_display("") == (None, "")

	def test_no_block(self):
		"""Plain content returns (None, content)."""
		text = "Just content"
		assert split_reasoning_and_content_from_display(text) == (None, text)

	def test_think_block_format(self):
		"""<think>...</think> block is extracted."""
		text = f"{START_BLOCK_REASONING}\nreasoning here\n{END_REASONING}\n\ncontent"
		reasoning, content = split_reasoning_and_content_from_display(text)
		assert reasoning == "reasoning here"
		assert content == "content"

	def test_falls_back_to_legacy_think(self):
		"""When no <think> block, falls back to ```think parsing."""
		text = "```think\nlegacy\n```\n\ncontent"
		reasoning, content = split_reasoning_and_content_from_display(text)
		assert reasoning == "legacy"
		assert content == "content"


class TestFormatResponseForDisplay:
	"""Tests for format_response_for_display."""

	def test_show_reasoning_with_content(self):
		"""When show_reasoning=True and reasoning exists, formats with block."""
		result = format_response_for_display(
			reasoning="thought", content="answer", show_reasoning=True
		)
		assert (
			result
			== f"{REASONING_DISPLAY_START}\nthought\n{REASONING_DISPLAY_END}\n\nanswer"
		)

	def test_show_reasoning_without_reasoning(self):
		"""When show_reasoning=True but no reasoning, returns content only."""
		result = format_response_for_display(
			reasoning=None, content="answer", show_reasoning=True
		)
		assert result == "answer"

	def test_hide_reasoning(self):
		"""When show_reasoning=False, returns content only."""
		result = format_response_for_display(
			reasoning="thought", content="answer", show_reasoning=False
		)
		assert result == "answer"

	def test_empty_reasoning_string(self):
		"""Empty string reasoning with show_reasoning=True returns content."""
		result = format_response_for_display(
			reasoning="", content="answer", show_reasoning=True
		)
		assert result == "answer"

	def test_empty_content_with_reasoning(self):
		"""When reasoning exists but content is empty, formats correctly."""
		result = format_response_for_display(
			reasoning="thought", content="", show_reasoning=True
		)
		assert (
			result
			== f"{REASONING_DISPLAY_START}\nthought\n{REASONING_DISPLAY_END}\n\n"
		)
