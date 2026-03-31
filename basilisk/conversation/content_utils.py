"""Utilities for message content processing."""

from __future__ import annotations

import re

START_BLOCK_REASONING = "<think>"
END_REASONING = "</think>"

# Legacy ```think...``` (older streams / persisted content)
_THINK_BLOCK_PATTERN = re.compile(r"^```think\s*\n(.*?)\n```\s*", re.DOTALL)
_REASONING_BLOCK_PATTERN = re.compile(
	rf"^{re.escape(START_BLOCK_REASONING)}\s*\n(.*?)\n{re.escape(END_REASONING)}\s*",
	re.DOTALL,
)


def split_reasoning_and_content(text: str) -> tuple[str | None, str]:
	"""Split content into reasoning and official response.

	Tries a leading block delimited by ``START_BLOCK_REASONING`` /
	``END_REASONING``, then legacy `` ```think`` ... ````` `` blocks in older
	content and some providers.

	Args:
		text: Assistant content that may start with a reasoning block.

	Returns:
		Tuple of (reasoning, content). If no block, returns (None, text).
	"""
	if not text:
		return None, text or ""
	match = _REASONING_BLOCK_PATTERN.match(text)
	if match:
		reasoning = match.group(1).strip()
		content = text[match.end() :].strip()
		return reasoning or None, content
	match = _THINK_BLOCK_PATTERN.match(text)
	if not match:
		return None, text
	reasoning = match.group(1).strip()
	content = text[match.end() :].strip()
	return reasoning or None, content


def assistant_message_body_for_api(raw_content: str | None) -> str:
	"""Assistant text for provider APIs and chat history (never includes reasoning).

	Strips a leading reasoning wrapper from legacy payloads so reasoning is not
	sent on follow-up requests. Clean ``content`` (reasoning stored separately)
	is returned unchanged.
	"""
	_, body = split_reasoning_and_content(raw_content or "")
	return body


def format_response_for_display(
	reasoning: str | None, content: str, show_reasoning: bool
) -> str:
	"""Format response for display (reasoning + content or content only)."""
	if show_reasoning and reasoning:
		return f"{START_BLOCK_REASONING}\n{reasoning}\n{END_REASONING}\n\n{content}"
	return content


def split_reasoning_and_content_from_display(
	text: str,
) -> tuple[str | None, str]:
	"""Split display / edited text into reasoning and content.

	Same rules as :func:`split_reasoning_and_content`.
	"""
	return split_reasoning_and_content(text)
