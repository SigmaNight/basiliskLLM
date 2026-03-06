"""Utilities for message content processing."""

from __future__ import annotations

import re

START_BLOCK_REASONING = "<think>"
END_REASONING = "</think>"

_THINK_BLOCK_PATTERN = re.compile(r"```think\s*\n(.*?)\n```\s*", re.DOTALL)


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
	match = _THINK_BLOCK_PATTERN.search(text)
	if not match:
		return None, text
	reasoning = match.group(1).strip()
	content = (_THINK_BLOCK_PATTERN.sub("", text) or "").strip()
	return reasoning or None, content
