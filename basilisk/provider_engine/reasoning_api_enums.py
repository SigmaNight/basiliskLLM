"""StrEnums for reasoning, stream events, and wire values used in provider APIs."""

from __future__ import annotations

import enum


class OpenRouterReasoningEffort(enum.StrEnum):
	"""Effort values for OpenRouter ``extra_body.reasoning`` (effort-based path)."""

	MINIMAL = "minimal"
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	XHIGH = "xhigh"

	@classmethod
	def normalize(cls, effort: str | None) -> OpenRouterReasoningEffort:
		"""Map a loose string to a valid effort; unknown values become MEDIUM."""
		raw = (effort or cls.MEDIUM.value).lower()
		try:
			return cls(raw)
		except ValueError:
			return cls.MEDIUM


class AnthropicReasoningEffort(enum.StrEnum):
	"""Effort strings for Claude ``output_config`` (adaptive thinking)."""

	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
	MAX = "max"

	@classmethod
	def is_valid(cls, effort: str) -> bool:
		"""Return True if ``effort`` matches a known Claude output_config value."""
		try:
			cls(effort.lower())
			return True
		except ValueError:
			return False


class AnthropicCitationLocationType(enum.StrEnum):
	"""Citation ``type`` values Anthropic returns for text citations."""

	CHAR_LOCATION = "char_location"
	PAGE_LOCATION = "page_location"


class AnthropicContentBlockType(enum.StrEnum):
	"""Non-stream message ``content`` block types from Anthropic."""

	THINKING = "thinking"
	TEXT = "text"


class AnthropicStreamDeltaType(enum.StrEnum):
	"""``content_block_delta`` delta ``type`` strings from Anthropic streaming."""

	TEXT_DELTA = "text_delta"
	THINKING_DELTA = "thinking_delta"
	CITATIONS_DELTA = "citations_delta"


class AnthropicStreamEventType(enum.StrEnum):
	"""Top-level stream ``event.type`` strings from Anthropic."""

	CONTENT_BLOCK_DELTA = "content_block_delta"
	MESSAGE_DELTA = "message_delta"
	MESSAGE_STOP = "message_stop"


class GeminiThinkingEffortKey(enum.StrEnum):
	"""Effort labels mapped to ThinkingLevel for Gemini 3."""

	MINIMAL = "minimal"
	LOW = "low"
	MEDIUM = "medium"
	HIGH = "high"
