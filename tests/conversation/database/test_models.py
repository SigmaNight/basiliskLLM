"""Tests for SQLAlchemy database models."""

from datetime import datetime

import pytest
from sqlalchemy.exc import IntegrityError

from basilisk.conversation.database.models import (
	DBAttachment,
	DBCitation,
	DBConversation,
	DBConversationSystemPrompt,
	DBMessage,
	DBMessageAttachment,
	DBMessageBlock,
	DBSystemPrompt,
)


class TestDBConversation:
	"""Tests for the DBConversation model."""

	def test_create_conversation(self, db_session):
		"""Test basic conversation creation."""
		conv = DBConversation(
			title="Test", created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()
		assert conv.id is not None
		assert conv.title == "Test"

	def test_conversation_nullable_title(self, db_session):
		"""Test that title can be NULL."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()
		assert conv.title is None

	def test_conversation_cascade_delete(self, db_session):
		"""Test that deleting a conversation cascades to blocks."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()

		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()

		db_session.delete(conv)
		db_session.flush()

		assert db_session.get(DBMessageBlock, block.id) is None


class TestDBSystemPrompt:
	"""Tests for the DBSystemPrompt model."""

	def test_create_system_prompt(self, db_session):
		"""Test creating a system prompt."""
		sp = DBSystemPrompt(content_hash="abc123", content="Be helpful")
		db_session.add(sp)
		db_session.flush()
		assert sp.id is not None

	def test_unique_content_hash(self, db_session):
		"""Test that duplicate content_hash raises IntegrityError."""
		sp1 = DBSystemPrompt(content_hash="same_hash", content="Content 1")
		sp2 = DBSystemPrompt(content_hash="same_hash", content="Content 2")
		db_session.add(sp1)
		db_session.flush()
		db_session.add(sp2)
		with pytest.raises(IntegrityError):
			db_session.flush()


class TestDBConversationSystemPrompt:
	"""Tests for the DBConversationSystemPrompt model."""

	def test_link_system_to_conversation(self, db_session):
		"""Test linking a system prompt to a conversation."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		sp = DBSystemPrompt(content_hash="hash1", content="Content")
		db_session.add_all([conv, sp])
		db_session.flush()

		csp = DBConversationSystemPrompt(
			conversation_id=conv.id, system_prompt_id=sp.id, position=0
		)
		db_session.add(csp)
		db_session.flush()
		assert csp.id is not None

	def test_unique_position_per_conversation(self, db_session):
		"""Test UNIQUE(conversation_id, position) constraint."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		sp = DBSystemPrompt(content_hash="hash1", content="Content")
		db_session.add_all([conv, sp])
		db_session.flush()

		csp1 = DBConversationSystemPrompt(
			conversation_id=conv.id, system_prompt_id=sp.id, position=0
		)
		csp2 = DBConversationSystemPrompt(
			conversation_id=conv.id, system_prompt_id=sp.id, position=0
		)
		db_session.add(csp1)
		db_session.flush()
		db_session.add(csp2)
		with pytest.raises(IntegrityError):
			db_session.flush()


class TestDBMessageBlock:
	"""Tests for the DBMessageBlock model."""

	def test_create_message_block(self, db_session):
		"""Test creating a message block with all fields."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()

		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			temperature=0.7,
			max_tokens=2048,
			top_p=0.9,
			stream=True,
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()
		assert block.id is not None
		assert block.temperature == 0.7
		assert block.stream is True

	def test_unique_position_per_conversation(self, db_session):
		"""Test UNIQUE(conversation_id, position) constraint."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()

		block1 = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		block2 = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block1)
		db_session.flush()
		db_session.add(block2)
		with pytest.raises(IntegrityError):
			db_session.flush()

	def test_optional_system_prompt_link(self, db_session):
		"""Test that conversation_system_prompt_id is nullable."""
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()

		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			conversation_system_prompt_id=None,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()
		assert block.conversation_system_prompt_id is None


class TestDBMessage:
	"""Tests for the DBMessage model."""

	def _make_block(self, db_session):
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()
		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()
		return block

	def test_create_user_message(self, db_session):
		"""Test creating a user message."""
		block = self._make_block(db_session)
		msg = DBMessage(message_block_id=block.id, role="user", content="Hello")
		db_session.add(msg)
		db_session.flush()
		assert msg.id is not None
		assert msg.role == "user"

	def test_create_assistant_message(self, db_session):
		"""Test creating an assistant message."""
		block = self._make_block(db_session)
		msg = DBMessage(
			message_block_id=block.id, role="assistant", content="Hi there"
		)
		db_session.add(msg)
		db_session.flush()
		assert msg.role == "assistant"

	def test_unique_role_per_block(self, db_session):
		"""Test UNIQUE(message_block_id, role) constraint."""
		block = self._make_block(db_session)
		msg1 = DBMessage(
			message_block_id=block.id, role="user", content="Hello"
		)
		msg2 = DBMessage(
			message_block_id=block.id, role="user", content="Hello again"
		)
		db_session.add(msg1)
		db_session.flush()
		db_session.add(msg2)
		with pytest.raises(IntegrityError):
			db_session.flush()

	def test_cascade_delete_with_block(self, db_session):
		"""Test that deleting a block cascades to messages."""
		block = self._make_block(db_session)
		msg = DBMessage(message_block_id=block.id, role="user", content="Hello")
		db_session.add(msg)
		db_session.flush()
		msg_id = msg.id

		db_session.delete(block)
		db_session.flush()
		assert db_session.get(DBMessage, msg_id) is None


class TestDBAttachment:
	"""Tests for the DBAttachment model."""

	def test_create_blob_attachment(self, db_session):
		"""Test creating an attachment with blob data."""
		att = DBAttachment(
			content_hash="hash1",
			name="file.txt",
			mime_type="text/plain",
			size=12,
			location_type="memory",
			blob_data=b"test content",
		)
		db_session.add(att)
		db_session.flush()
		assert att.id is not None
		assert att.blob_data == b"test content"

	def test_create_url_attachment(self, db_session):
		"""Test creating a URL attachment without blob."""
		att = DBAttachment(
			content_hash="hash2",
			name="remote.txt",
			mime_type="text/plain",
			location_type="url",
			url="https://example.com/file.txt",
		)
		db_session.add(att)
		db_session.flush()
		assert att.url == "https://example.com/file.txt"
		assert att.blob_data is None

	def test_create_image_attachment(self, db_session):
		"""Test creating an image attachment."""
		att = DBAttachment(
			content_hash="hash3",
			name="img.png",
			mime_type="image/png",
			size=1024,
			location_type="local",
			blob_data=b"fake png",
			is_image=True,
			image_width=100,
			image_height=50,
		)
		db_session.add(att)
		db_session.flush()
		assert att.is_image is True
		assert att.image_width == 100
		assert att.image_height == 50

	def test_unique_content_hash(self, db_session):
		"""Test that duplicate content_hash raises IntegrityError."""
		att1 = DBAttachment(content_hash="same", location_type="memory")
		att2 = DBAttachment(content_hash="same", location_type="memory")
		db_session.add(att1)
		db_session.flush()
		db_session.add(att2)
		with pytest.raises(IntegrityError):
			db_session.flush()


class TestDBMessageAttachment:
	"""Tests for the DBMessageAttachment model."""

	def _make_message_and_attachment(self, db_session):
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()
		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()
		msg = DBMessage(message_block_id=block.id, role="user", content="Hello")
		db_session.add(msg)
		db_session.flush()
		att = DBAttachment(
			content_hash="hash_test", location_type="memory", blob_data=b"data"
		)
		db_session.add(att)
		db_session.flush()
		return msg, att

	def test_link_attachment_to_message(self, db_session):
		"""Test linking an attachment to a message."""
		msg, att = self._make_message_and_attachment(db_session)
		link = DBMessageAttachment(
			message_id=msg.id,
			attachment_id=att.id,
			position=0,
			description="A file",
		)
		db_session.add(link)
		db_session.flush()
		assert link.id is not None

	def test_unique_position_per_message(self, db_session):
		"""Test UNIQUE(message_id, position) constraint."""
		msg, att = self._make_message_and_attachment(db_session)
		link1 = DBMessageAttachment(
			message_id=msg.id, attachment_id=att.id, position=0
		)
		link2 = DBMessageAttachment(
			message_id=msg.id, attachment_id=att.id, position=0
		)
		db_session.add(link1)
		db_session.flush()
		db_session.add(link2)
		with pytest.raises(IntegrityError):
			db_session.flush()


class TestDBCitation:
	"""Tests for the DBCitation model."""

	def _make_message(self, db_session):
		conv = DBConversation(
			created_at=datetime.now(), updated_at=datetime.now()
		)
		db_session.add(conv)
		db_session.flush()
		block = DBMessageBlock(
			conversation_id=conv.id,
			position=0,
			model_provider="openai",
			model_id="gpt-4",
			created_at=datetime.now(),
			updated_at=datetime.now(),
		)
		db_session.add(block)
		db_session.flush()
		msg = DBMessage(
			message_block_id=block.id, role="assistant", content="Response"
		)
		db_session.add(msg)
		db_session.flush()
		return msg

	def test_create_citation(self, db_session):
		"""Test creating a citation."""
		msg = self._make_message(db_session)
		cit = DBCitation(
			message_id=msg.id,
			position=0,
			cited_text="Important fact",
			source_title="Source",
			source_url="https://example.com",
			start_index=0,
			end_index=14,
		)
		db_session.add(cit)
		db_session.flush()
		assert cit.id is not None

	def test_cascade_delete_with_message(self, db_session):
		"""Test that deleting a message cascades to citations."""
		msg = self._make_message(db_session)
		cit = DBCitation(message_id=msg.id, position=0, cited_text="text")
		db_session.add(cit)
		db_session.flush()
		cit_id = cit.id

		db_session.delete(msg)
		db_session.flush()
		assert db_session.get(DBCitation, cit_id) is None

	def test_multiple_citations_ordered(self, db_session):
		"""Test multiple citations maintain position order."""
		msg = self._make_message(db_session)
		for i in range(3):
			cit = DBCitation(
				message_id=msg.id, position=i, cited_text=f"Citation {i}"
			)
			db_session.add(cit)
		db_session.flush()

		citations = sorted(msg.citations, key=lambda c: c.position)
		assert len(citations) == 3
		assert citations[0].cited_text == "Citation 0"
		assert citations[2].cited_text == "Citation 2"
