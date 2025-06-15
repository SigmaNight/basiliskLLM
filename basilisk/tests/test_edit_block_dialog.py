"""Comprehensive unit tests for EditBlockDialog."""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import wx
from PIL import Image
from upath import UPath

from basilisk.conversation import (
    Conversation,
    Message,
    MessageBlock,
    MessageRoleEnum,
    SystemMessage,
)
from basilisk.provider_ai_model import AIModelInfo
from basilisk.gui.edit_block_dialog import EditBlockDialog
from basilisk.completion_handler import CompletionHandler


@pytest.fixture
def ai_model():
    """Create a sample AIModelInfo for testing."""
    return AIModelInfo(provider_id="test_provider", model_id="test_model")


@pytest.fixture
def attachment():
    """Create a sample attachment object."""
    return Mock(name="attachment")


@pytest.fixture
def mock_parent():
    """Create a mock parent ConversationTab."""
    parent = Mock()
    parent.conversation = Mock(spec=Conversation)
    parent.conversation.messages = []
    parent.conversation.systems = Mock()
    parent.messages = Mock()
    parent.messages.a_output = Mock()
    parent.messages.speak_stream = False
    parent.accounts_engines = []
    parent.conv_storage_path = UPath("memory://test")
    return parent


@pytest.fixture
def sample_message_block(ai_model):
    """Create a sample message block for testing."""
    return MessageBlock(
        request=Message(role=MessageRoleEnum.USER, content="Test prompt"),
        response=Message(role=MessageRoleEnum.ASSISTANT, content="Test response"),
        model=ai_model,
        temperature=0.7,
        max_tokens=1000,
        top_p=0.9,
        stream=True
    )


@pytest.fixture
def mock_conversation_with_block(sample_message_block):
    """Create a mock conversation with a message block."""
    conversation = Mock(spec=Conversation)
    conversation.messages = [sample_message_block]
    conversation.systems = Mock()
    conversation.systems.__getitem__ = Mock(return_value=SystemMessage(content="System message"))
    return conversation