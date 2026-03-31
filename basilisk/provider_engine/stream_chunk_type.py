"""Stream chunk type tags for completion_response_with_stream iterators."""

from __future__ import annotations

import enum


class StreamChunkType(enum.StrEnum):
	"""Chunk kinds yielded by engines during streaming completion."""

	CONTENT = "content"
	REASONING = "reasoning"
	CITATION = "citation"
