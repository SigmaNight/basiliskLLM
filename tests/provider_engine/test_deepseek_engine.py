"""Tests for DeepSeek engine reasoning chunk handling."""

import inspect
from unittest.mock import MagicMock

import pytest

from basilisk.conversation import Message, MessageBlock, MessageRoleEnum
from basilisk.provider_engine.deepseek_engine import DeepSeekAIEngine


def _make_chunk(
	reasoning_content: str | None = None, content: str | None = None
):
	"""Build a minimal ChatCompletionChunk-like object."""
	chunk = MagicMock()
	chunk.choices = [MagicMock()]
	chunk.choices[0].delta = MagicMock()
	chunk.choices[0].delta.reasoning_content = reasoning_content
	chunk.choices[0].delta.content = content
	chunk.usage = None
	return chunk


def _call_stream(engine, stream, new_block):
	"""Call completion_response_with_stream; supports (stream) or (stream, new_block)."""
	sig = inspect.signature(engine.completion_response_with_stream)
	if "new_block" in sig.parameters:
		return list(engine.completion_response_with_stream(stream, new_block))
	return list(engine.completion_response_with_stream(stream))


@pytest.fixture
def engine():
	"""Return a DeepSeek engine with mocked client."""
	eng = DeepSeekAIEngine(account=MagicMock())
	eng.client = MagicMock()
	return eng


@pytest.fixture
def new_block(ai_model):
	"""MessageBlock for non-streaming tests."""
	return MessageBlock(
		request=Message(role=MessageRoleEnum.USER, content="Hi"), model=ai_model
	)


class TestCompletionResponseWithStream:
	"""Tests for completion_response_with_stream (reasoning + content chunks)."""

	def test_yields_reasoning_then_content(self, engine, new_block):
		"""Stream yields ('reasoning', chunk) then ('content', chunk)."""
		chunks = [
			_make_chunk(reasoning_content="Let me think...", content=None),
			_make_chunk(reasoning_content=None, content="Hello"),
		]
		stream = iter(chunks)
		result = _call_stream(engine, stream, new_block)
		assert result == [
			("reasoning", "Let me think..."),
			("content", "Hello"),
		]

	def test_yields_content_only_when_no_reasoning(self, engine, new_block):
		"""Stream yields only ('content', chunk) when no reasoning_content."""
		chunks = [_make_chunk(reasoning_content=None, content="Hi there")]
		stream = iter(chunks)
		result = _call_stream(engine, stream, new_block)
		assert result == [("content", "Hi there")]

	def test_yields_both_in_same_chunk(self, engine, new_block):
		"""Chunk with both reasoning and content yields both in order."""
		chunks = [_make_chunk(reasoning_content="think", content="answer")]
		stream = iter(chunks)
		result = _call_stream(engine, stream, new_block)
		assert result == [("reasoning", "think"), ("content", "answer")]


class TestCompletionResponseWithoutStream:
	"""Tests for completion_response_without_stream."""

	def test_populates_reasoning_and_content(self, engine, new_block):
		"""Non-streaming response with reasoning_content sets both fields."""
		response = MagicMock()
		response.choices = [MagicMock()]
		response.choices[0].message = MagicMock()
		response.choices[0].message.reasoning_content = "Internal thought"
		response.choices[0].message.content = "Final answer"
		response.usage = None

		engine.completion_response_without_stream(response, new_block)

		assert new_block.response is not None
		assert new_block.response.reasoning == "Internal thought"
		assert new_block.response.content == "Final answer"

	def test_content_only_when_no_reasoning(self, engine, new_block):
		"""Non-streaming response without reasoning_content sets only content."""
		response = MagicMock()
		response.choices = [MagicMock()]
		response.choices[0].message = MagicMock()
		response.choices[0].message.reasoning_content = None
		response.choices[0].message.content = "Just content"
		response.usage = None

		engine.completion_response_without_stream(response, new_block)

		assert new_block.response is not None
		assert new_block.response.reasoning is None
		assert new_block.response.content == "Just content"
