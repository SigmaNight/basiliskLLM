"""Common test fixtures for basiliskLLM."""

import pytest
from PIL import Image
from upath import UPath

from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)
from basilisk.provider_ai_model import AIModelInfo


@pytest.fixture
def ai_model():
	"""Return a test AI model."""
	return AIModelInfo(provider_id="openai", model_id="test_model")


@pytest.fixture
def user_message():
	"""Return a test user message."""
	return Message(role=MessageRoleEnum.USER, content="Test message")


@pytest.fixture
def assistant_message():
	"""Return a test assistant message."""
	return Message(role=MessageRoleEnum.ASSISTANT, content="Test response")


@pytest.fixture
def system_message():
	"""Return a test system message."""
	return SystemMessage(
		role=MessageRoleEnum.SYSTEM, content="System instructions"
	)


@pytest.fixture
def message_block(ai_model, user_message):
	"""Return a test message block."""
	return MessageBlock(request=user_message, model=ai_model)


@pytest.fixture
def message_block_with_response(ai_model, user_message, assistant_message):
	"""Return a test message block with response."""
	return MessageBlock(
		request=user_message, response=assistant_message, model=ai_model
	)


@pytest.fixture
def empty_conversation():
	"""Return an empty conversation."""
	return Conversation()


@pytest.fixture
def text_file(tmp_path):
	"""Create and return a text file for testing."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("test content")
	return test_file_path


@pytest.fixture
def image_file(tmp_path):
	"""Create and return an image file for testing."""
	test_file_path = UPath(tmp_path) / "test.png"
	with test_file_path.open("wb") as f:
		img = Image.new('RGB', (100, 50), color='red')
		img.save(f, format='PNG')
	return test_file_path


@pytest.fixture
def attachment(text_file):
	"""Return an attachment file."""
	return AttachmentFile(location=text_file)


@pytest.fixture
def image_attachment(image_file):
	"""Return an image file attachment."""
	return ImageFile(location=image_file)


@pytest.fixture
def message_segments():
	"""Return a list of test message segments."""
	return [
		MessageSegment(length=7, kind=MessageSegmentType.CONTENT),
		MessageSegment(length=14, kind=MessageSegmentType.PREFIX),
		MessageSegment(length=21, kind=MessageSegmentType.CONTENT),
	]


@pytest.fixture
def segment_manager(message_segments):
	"""Return a message segment manager with test segments."""
	return MessageSegmentManager(message_segments)
