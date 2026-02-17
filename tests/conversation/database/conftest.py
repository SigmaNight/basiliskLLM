"""Test fixtures for conversation database tests."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
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
from basilisk.conversation.database.manager import ConversationDatabase
from basilisk.conversation.database.models import Base
from basilisk.provider_ai_model import AIModelInfo


@pytest.fixture
def db_engine():
	"""Create an in-memory SQLite engine with the full schema."""
	engine = create_engine("sqlite:///:memory:")
	Base.metadata.create_all(engine)
	yield engine
	engine.dispose()


@pytest.fixture
def db_session(db_engine):
	"""Provide a SQLAlchemy session with automatic rollback."""
	session_factory = sessionmaker(bind=db_engine)
	session = session_factory()
	yield session
	session.rollback()
	session.close()


@pytest.fixture
def db_manager(db_engine):
	"""Create a ConversationDatabase with an in-memory DB (no Alembic)."""
	manager = ConversationDatabase.__new__(ConversationDatabase)
	manager._db_path = ":memory:"
	manager._engine = db_engine
	manager._session_factory = sessionmaker(bind=db_engine)
	return manager


@pytest.fixture
def test_ai_model():
	"""Return a test AI model info."""
	return AIModelInfo(provider_id="openai", model_id="test_model")


@pytest.fixture
def conversation_with_blocks(test_ai_model):
	"""Create a conversation with 3 message blocks."""
	conv = Conversation()
	system = SystemMessage(content="System instructions")
	for i in range(3):
		req = Message(role=MessageRoleEnum.USER, content=f"Question {i}")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content=f"Answer {i}")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		conv.add_block(block, system if i == 0 else None)
	conv.title = "Test conversation"
	return conv


@pytest.fixture
def conversation_with_attachments(test_ai_model, tmp_path):
	"""Create a conversation with text and image attachments."""
	# Create test files
	text_path = UPath(tmp_path) / "test.txt"
	with text_path.open("w") as f:
		f.write("test content")

	img_path = UPath(tmp_path) / "test.png"
	from PIL import Image

	with img_path.open("wb") as f:
		img = Image.new("RGB", (100, 50), color="red")
		img.save(f, format="PNG")

	attachment = AttachmentFile(location=text_path)
	img_attachment = ImageFile(location=img_path)

	req = Message(
		role=MessageRoleEnum.USER,
		content="With files",
		attachments=[attachment, img_attachment],
	)
	block = MessageBlock(request=req, model=test_ai_model)
	conv = Conversation()
	conv.add_block(block)
	conv.title = "Conversation with attachments"
	return conv


@pytest.fixture
def conversation_with_citations(test_ai_model):
	"""Create a conversation with citations in the response."""
	req = Message(role=MessageRoleEnum.USER, content="Tell me about X")
	resp = Message(
		role=MessageRoleEnum.ASSISTANT,
		content="Here is info about X",
		citations=[
			{
				"cited_text": "X is important",
				"source_title": "Source A",
				"source_url": "https://example.com/a",
				"start_index": 0,
				"end_index": 14,
			},
			{"cited_text": "X was discovered", "source_title": "Source B"},
		],
	)
	block = MessageBlock(request=req, response=resp, model=test_ai_model)
	conv = Conversation()
	conv.add_block(block)
	return conv
