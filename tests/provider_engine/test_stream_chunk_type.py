"""Tests for StreamChunkType."""

import pytest

from basilisk.provider_engine.stream_chunk_type import StreamChunkType


def test_stream_chunk_type_compares_to_string():
	"""StrEnum values compare equal to their wire string."""
	assert StreamChunkType.CONTENT == "content"
	assert StreamChunkType.REASONING == "reasoning"
	assert StreamChunkType.CITATION == "citation"


@pytest.mark.parametrize(
	("member", "value"),
	[
		(StreamChunkType.CONTENT, "content"),
		(StreamChunkType.REASONING, "reasoning"),
		(StreamChunkType.CITATION, "citation"),
	],
)
def test_stream_chunk_type_coerce(member, value):
	"""Construction from API wire strings round-trips."""
	assert StreamChunkType(value) is member


def test_stream_chunk_type_members():
	"""All chunk kinds are distinct string values."""
	assert {m.value for m in StreamChunkType} == {
		"content",
		"reasoning",
		"citation",
	}
