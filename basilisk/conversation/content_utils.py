"""Utilities for message content processing."""

from __future__ import annotations

import re

START_BLOCK_REASONING = "<think>"
END_REASONING = "</think>"

REASONING_DISPLAY_START = "```think"
REASONING_DISPLAY_END = "```"

# Anchored at start so only a leading block is treated as metadata
_THINK_BLOCK_PATTERN = re.compile(r"^```think\s*\n(.*?)\n```\s*", re.DOTALL)
_REASONING_BLOCK_PATTERN = re.compile(
	rf"^{re.escape(START_BLOCK_REASONING)}\s*\n(.*?)\n{re.escape(END_REASONING)}\s*",
	re.DOTALL,
)


def split_reasoning_and_content(text: str) -> tuple[str | None, str]:
	"""Split content into reasoning and official response.

	Handles legacy format where reasoning was concatenated as ```think...```
	before the response. Used when loading from DB or after streaming.

	Args:
		text: Content that may contain ```think...``` block.

	Returns:
		Tuple of (reasoning, content). If no think block, returns (None, text).
	"""
	if not text:
		return None, text or ""
	match = _THINK_BLOCK_PATTERN.match(text)
	if not match:
		return None, text
	reasoning = match.group(1).strip()
	content = text[match.end() :].strip()
	return reasoning or None, content


def format_response_for_display(
	reasoning: str | None, content: str, show_reasoning: bool
) -> str:
	"""Format response for display (reasoning + content or content only)."""
	if show_reasoning and reasoning:
		return f"{REASONING_DISPLAY_START}\n{reasoning}\n{REASONING_DISPLAY_END}\n\n{content}"
	return content


def split_reasoning_and_content_from_display(
	text: str,
) -> tuple[str | None, str]:
	"""Split display text (<think>...</think> format) into reasoning and content.

	Used when parsing user-edited response text (e.g. in edit block dialog).

	Args:
		text: Display text that may contain <think>...</think> block.

	Returns:
		Tuple of (reasoning, content). If no block, returns (None, text).
	"""
	if not text:
		return None, text or ""
	match = _REASONING_BLOCK_PATTERN.match(text)
	if not match:
		return split_reasoning_and_content(text)
	reasoning = match.group(1).strip()
	content = text[match.end() :].strip()
	return reasoning or None, content
