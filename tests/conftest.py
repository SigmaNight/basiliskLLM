"""Common test fixtures for basiliskLLM."""

from unittest import mock

import pytest
from PIL import Image
from upath import UPath

from basilisk.config.config_helper import BasiliskBaseSettings
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
def conversation_with_response(ai_model):
	"""Return a conversation with a single complete block (request + response)."""
	conv = Conversation()
	req = Message(role=MessageRoleEnum.USER, content="Hello")
	resp = Message(role=MessageRoleEnum.ASSISTANT, content="Hi there!")
	block = MessageBlock(request=req, response=resp, model=ai_model)
	conv.add_block(block)
	conv.title = "Test"
	return conv


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


@pytest.fixture(autouse=True)
def mock_display_error_msg():
	"""Mock display_signal_error_msg to prevent error dialogs in tests."""
	with mock.patch(
		"basilisk.send_signal.display_signal_error_msg"
	) as mock_display:
		# Also mock the platform-specific functions to ensure no system calls
		with mock.patch(
			"basilisk.send_signal._display_error_msg_windows"
		) as mock_win:
			with mock.patch(
				"basilisk.send_signal._display_error_msg_macos"
			) as mock_mac:
				with mock.patch(
					"basilisk.send_signal._display_error_msg_linux"
				) as mock_linux:
					yield {
						"main": mock_display,
						"windows": mock_win,
						"macos": mock_mac,
						"linux": mock_linux,
					}


@pytest.fixture
def mock_settings_sources():
	"""Mock the settings_customise_sources method to prevent loading real config files.

	This overrides the method to only use init_settings, avoiding any file loading.
	"""
	original_method = BasiliskBaseSettings.settings_customise_sources

	@classmethod
	def mock_settings_customise_sources(
		cls,
		settings_cls,
		init_settings,
		env_settings,
		dotenv_settings,
		file_secret_settings,
	):
		# Only use init_settings, skip loading from files
		return (init_settings,)

	# Apply the mock
	with mock.patch.object(
		BasiliskBaseSettings,
		'settings_customise_sources',
		mock_settings_customise_sources,
	):
		yield

	# Reset after test
	BasiliskBaseSettings.settings_customise_sources = original_method
