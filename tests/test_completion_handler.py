"""Tests for CompletionHandler reasoning logic."""

import pytest

from basilisk.completion_handler import CompletionHandler
from basilisk.conversation import Message, MessageBlock, MessageRoleEnum
from basilisk.provider_ai_model import AIModelInfo


@pytest.fixture
def ai_model():
	"""Return a test AIModelInfo instance."""
	return AIModelInfo(provider_id="openai", model_id="test")


@pytest.fixture
def handler():
	"""Return a CompletionHandler instance for testing."""
	return CompletionHandler()


@pytest.fixture
def block_with_legacy_think(ai_model):
	"""MessageBlock with response containing legacy ```think...``` in content."""
	req = Message(role=MessageRoleEnum.USER, content="Think")
	resp = Message(
		role=MessageRoleEnum.ASSISTANT,
		content="```think\ninternal reasoning\n```\n\nfinal answer",
		reasoning=None,
	)
	return MessageBlock(request=req, response=resp, model=ai_model)


@pytest.fixture
def block_without_think(ai_model):
	"""MessageBlock with plain content, no think block."""
	req = Message(role=MessageRoleEnum.USER, content="Hi")
	resp = Message(
		role=MessageRoleEnum.ASSISTANT, content="Hello there", reasoning=None
	)
	return MessageBlock(request=req, response=resp, model=ai_model)


class TestSplitReasoningFromContent:
	"""Tests for _split_reasoning_from_content."""

	def test_parses_legacy_think_into_reasoning_and_content(
		self, handler, block_with_legacy_think
	):
		"""Legacy ```think...``` is split into reasoning and content."""
		handler._split_reasoning_from_content(block_with_legacy_think)
		assert (
			block_with_legacy_think.response.reasoning == "internal reasoning"
		)
		assert block_with_legacy_think.response.content == "final answer"

	def test_no_change_when_no_think_block(self, handler, block_without_think):
		"""Content without ```think is left unchanged."""
		handler._split_reasoning_from_content(block_without_think)
		assert block_without_think.response.reasoning is None
		assert block_without_think.response.content == "Hello there"

	def test_no_op_when_response_none(self, handler, ai_model):
		"""Block with no response is unchanged."""
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Q"),
			response=None,
			model=ai_model,
		)
		handler._split_reasoning_from_content(block)
		assert block.response is None


class TestHandleStreamChunkReasoning:
	"""Tests for _handle_stream_chunk with reasoning and content chunks."""

	def test_reasoning_chunks_accumulate_in_response(
		self, handler, ai_model, mocker
	):
		"""Reasoning chunks are accumulated in message_block.response.reasoning."""
		mocker.patch("wx.CallAfter", side_effect=lambda f, *a, **k: f(*a, **k))
		mocker.patch(
			"basilisk.completion_handler.play_sound", return_value=None
		)
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Think"),
			response=Message(
				role=MessageRoleEnum.ASSISTANT, content="", reasoning=None
			),
			model=ai_model,
		)
		handler._handle_stream_chunk(("reasoning", "Part1 "), block)
		handler._handle_stream_chunk(("reasoning", "Part2"), block)
		assert block.response.reasoning == "Part1 Part2"

	def test_content_after_reasoning_appends_to_content(
		self, handler, ai_model, mocker
	):
		"""Content chunk after reasoning goes to response.content."""
		mocker.patch("wx.CallAfter", side_effect=lambda f, *a, **k: f(*a, **k))
		mocker.patch(
			"basilisk.completion_handler.play_sound", return_value=None
		)
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="Q"),
			response=Message(
				role=MessageRoleEnum.ASSISTANT, content="", reasoning=None
			),
			model=ai_model,
		)
		handler._handle_stream_chunk(("reasoning", "think"), block)
		handler._handle_stream_chunk(("content", "answer"), block)
		assert block.response.reasoning == "think"
		assert block.response.content == "answer"
