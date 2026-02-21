"""Tests for the ConversationDatabase manager CRUD operations."""

from datetime import datetime, timedelta, timezone

import pytest

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)


class TestSaveConversation:
	"""Tests for saving conversations."""

	def test_save_empty_conversation(self, db_manager):
		"""Test saving an empty conversation."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)
		assert isinstance(conv_id, int)
		assert conv_id > 0

	def test_save_conversation_with_title(self, db_manager):
		"""Test that the title is preserved."""
		conv = Conversation()
		conv.title = "My conversation"
		db_manager.save_conversation(conv)
		result = db_manager.list_conversations()
		assert result[0]["title"] == "My conversation"

	def test_save_conversation_returns_id(self, db_manager):
		"""Test that save returns a valid integer ID."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)
		assert conv_id > 0

	def test_save_conversation_with_blocks(
		self, db_manager, conversation_with_blocks
	):
		"""Test saving a conversation with message blocks."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 3

	def test_save_conversation_with_system(
		self, db_manager, conversation_with_blocks
	):
		"""Test that system prompts and links are created."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.systems) == 1
		assert loaded.systems[0].content == "System instructions"

	def test_save_conversation_shared_system(self, db_manager, test_ai_model):
		"""Test system prompt deduplication by hash."""
		system = SystemMessage(content="Shared prompt")

		# Create two conversations with the same system prompt
		for _ in range(2):
			conv = Conversation()
			req = Message(role=MessageRoleEnum.USER, content="Hello")
			block = MessageBlock(request=req, model=test_ai_model)
			conv.add_block(block, system)
			db_manager.save_conversation(conv)

		# Both should reference the same system_prompt row
		from sqlalchemy import select

		from basilisk.conversation.database.models import DBSystemPrompt

		with db_manager._get_session() as session:
			count = len(session.execute(select(DBSystemPrompt)).all())
		assert count == 1

	def test_save_conversation_with_attachments(
		self, db_manager, conversation_with_attachments
	):
		"""Test saving attachments with hash and BLOB."""
		conv_id = db_manager.save_conversation(conversation_with_attachments)
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		attachments = loaded.messages[0].request.attachments
		assert attachments is not None
		assert len(attachments) == 2


class TestSaveMessageBlock:
	"""Tests for incremental block saving."""

	def test_save_single_block(self, db_manager, test_ai_model):
		"""Test adding a single block to an existing conversation."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req = Message(role=MessageRoleEnum.USER, content="Hello")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="Hi")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		conv.add_block(block)

		db_manager.save_message_block(conv_id, 0, block)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1

	def test_save_block_with_response(self, db_manager, test_ai_model):
		"""Test that both request and response are saved."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req = Message(role=MessageRoleEnum.USER, content="Question")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="Answer")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		conv.add_block(block)

		db_manager.save_message_block(conv_id, 0, block)

		loaded = db_manager.load_conversation(conv_id)
		assert loaded.messages[0].request.content == "Question"
		assert loaded.messages[0].response.content == "Answer"

	def test_save_block_preserves_position(self, db_manager, test_ai_model):
		"""Test that block_index maps to position correctly."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		for i in range(3):
			req = Message(role=MessageRoleEnum.USER, content=f"Message {i}")
			block = MessageBlock(request=req, model=test_ai_model)
			conv.add_block(block)
			db_manager.save_message_block(conv_id, i, block)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 3
		assert loaded.messages[0].request.content == "Message 0"
		assert loaded.messages[2].request.content == "Message 2"

	def test_save_block_with_citations(
		self, db_manager, conversation_with_citations
	):
		"""Test saving citations in a block."""
		conv_id = db_manager.save_conversation(conversation_with_citations)
		loaded = db_manager.load_conversation(conv_id)
		citations = loaded.messages[0].response.citations
		assert citations is not None
		assert len(citations) == 2
		assert citations[0]["cited_text"] == "X is important"


class TestLoadConversation:
	"""Tests for loading conversations."""

	def test_load_empty_conversation(self, db_manager):
		"""Test round-trip of an empty conversation."""
		conv = Conversation()
		conv.title = "Empty"
		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)
		assert loaded.title == "Empty"
		assert len(loaded.messages) == 0

	def test_load_conversation_with_blocks(
		self, db_manager, conversation_with_blocks
	):
		"""Test all MessageBlocks are restored."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 3

	def test_load_conversation_with_system(
		self, db_manager, conversation_with_blocks
	):
		"""Test systems OrderedSet is reconstructed."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.systems) == 1
		# First block should reference system_index 0
		assert loaded.messages[0].system_index == 0

	def test_load_conversation_preserves_order(
		self, db_manager, conversation_with_blocks
	):
		"""Test message ordering is maintained."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		loaded = db_manager.load_conversation(conv_id)
		for i, block in enumerate(loaded.messages):
			assert block.request.content == f"Question {i}"
			assert block.response.content == f"Answer {i}"

	def test_load_nonexistent_raises(self, db_manager):
		"""Test that loading an invalid ID raises ValueError."""
		with pytest.raises(ValueError, match="not found"):
			db_manager.load_conversation(99999)


class TestListConversations:
	"""Tests for listing conversations."""

	def test_list_empty(self, db_manager):
		"""Test listing with no conversations."""
		result = db_manager.list_conversations()
		assert result == []

	def test_list_ordered_by_updated(self, db_manager, test_ai_model):
		"""Test that results are ordered by updated_at DESC."""
		from basilisk.conversation.database.models import DBConversation

		base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
		for i in range(3):
			conv = Conversation()
			conv.title = f"Conv {i}"
			conv_id = db_manager.save_conversation(conv)
			# Assign deterministic updated_at so ordering is predictable
			with db_manager._get_session() as session:
				with session.begin():
					session.execute(
						DBConversation.__table__.update()
						.where(DBConversation.id == conv_id)
						.values(updated_at=base_time + timedelta(seconds=i))
					)

		result = db_manager.list_conversations()
		assert len(result) == 3
		# Most recent first
		assert result[0]["title"] == "Conv 2"

	def test_list_with_limit(self, db_manager):
		"""Test pagination with limit."""
		for i in range(5):
			conv = Conversation()
			conv.title = f"Conv {i}"
			db_manager.save_conversation(conv)

		result = db_manager.list_conversations(limit=2)
		assert len(result) == 2

	def test_list_with_offset(self, db_manager):
		"""Test pagination with offset."""
		for i in range(5):
			conv = Conversation()
			conv.title = f"Conv {i}"
			db_manager.save_conversation(conv)

		result = db_manager.list_conversations(limit=2, offset=2)
		assert len(result) == 2

	def test_list_with_search_in_title(self, db_manager, test_ai_model):
		"""Test searching by title."""
		conv1 = Conversation()
		conv1.title = "Python tips"
		db_manager.save_conversation(conv1)

		conv2 = Conversation()
		conv2.title = "JavaScript basics"
		db_manager.save_conversation(conv2)

		result = db_manager.list_conversations(search="Python")
		assert len(result) == 1
		assert result[0]["title"] == "Python tips"

	def test_list_with_search_in_content(self, db_manager, test_ai_model):
		"""Test searching in message content."""
		conv = Conversation()
		conv.title = "General chat"
		req = Message(
			role=MessageRoleEnum.USER, content="Tell me about quantum computing"
		)
		block = MessageBlock(request=req, model=test_ai_model)
		conv.add_block(block)
		db_manager.save_conversation(conv)

		result = db_manager.list_conversations(search="quantum")
		assert len(result) == 1

	def test_list_returns_message_count(
		self, db_manager, conversation_with_blocks
	):
		"""Test that message_count is returned."""
		db_manager.save_conversation(conversation_with_blocks)
		result = db_manager.list_conversations()
		assert result[0]["message_count"] == 3


class TestUpdateConversation:
	"""Tests for updating conversations."""

	def test_update_title(self, db_manager):
		"""Test updating the title."""
		conv = Conversation()
		conv.title = "Old title"
		conv_id = db_manager.save_conversation(conv)

		db_manager.update_conversation_title(conv_id, "New title")

		result = db_manager.list_conversations()
		assert result[0]["title"] == "New title"

	def test_update_title_to_none(self, db_manager):
		"""Test clearing the title."""
		conv = Conversation()
		conv.title = "Has title"
		conv_id = db_manager.save_conversation(conv)

		db_manager.update_conversation_title(conv_id, None)

		result = db_manager.list_conversations()
		assert result[0]["title"] is None


class TestDeleteConversation:
	"""Tests for deleting conversations."""

	def test_delete_conversation(self, db_manager):
		"""Test deleting a conversation."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		db_manager.delete_conversation(conv_id)

		result = db_manager.list_conversations()
		assert len(result) == 0

	def test_delete_cascade_blocks(self, db_manager, conversation_with_blocks):
		"""Test that blocks are deleted in cascade."""
		conv_id = db_manager.save_conversation(conversation_with_blocks)
		db_manager.delete_conversation(conv_id)

		with pytest.raises(ValueError):
			db_manager.load_conversation(conv_id)

	def test_delete_nonexistent(self, db_manager):
		"""Test that deleting an invalid ID doesn't error."""
		# Should not raise
		db_manager.delete_conversation(99999)


class TestGetConversationCount:
	"""Tests for counting conversations."""

	def test_count_empty(self, db_manager):
		"""Test count with no conversations."""
		assert db_manager.get_conversation_count() == 0

	def test_count_multiple(self, db_manager):
		"""Test count with multiple conversations."""
		for _ in range(5):
			db_manager.save_conversation(Conversation())
		assert db_manager.get_conversation_count() == 5

	def test_count_with_search(self, db_manager, test_ai_model):
		"""Test filtered count."""
		conv1 = Conversation()
		conv1.title = "Alpha"
		db_manager.save_conversation(conv1)

		conv2 = Conversation()
		conv2.title = "Beta"
		db_manager.save_conversation(conv2)

		assert db_manager.get_conversation_count(search="Alpha") == 1


class TestDraftBlock:
	"""Tests for draft block save/delete operations."""

	def test_save_draft_block(self, db_manager, test_ai_model):
		"""Test saving a draft block (request only, no response)."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req = Message(role=MessageRoleEnum.USER, content="draft text")
		block = MessageBlock(request=req, model=test_ai_model)

		db_manager.save_draft_block(conv_id, 0, block)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		assert loaded.messages[0].request.content == "draft text"
		assert loaded.messages[0].response is None

	def test_save_draft_replaces_existing(self, db_manager, test_ai_model):
		"""Test that saving a draft at the same position replaces it."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req1 = Message(role=MessageRoleEnum.USER, content="draft v1")
		block1 = MessageBlock(request=req1, model=test_ai_model)
		db_manager.save_draft_block(conv_id, 0, block1)

		req2 = Message(role=MessageRoleEnum.USER, content="draft v2")
		block2 = MessageBlock(request=req2, model=test_ai_model)
		db_manager.save_draft_block(conv_id, 0, block2)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		assert loaded.messages[0].request.content == "draft v2"

	def test_delete_draft_block(self, db_manager, test_ai_model):
		"""Test deleting a draft block."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req = Message(role=MessageRoleEnum.USER, content="draft")
		block = MessageBlock(request=req, model=test_ai_model)
		db_manager.save_draft_block(conv_id, 0, block)

		db_manager.delete_draft_block(conv_id, 0)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 0

	def test_delete_draft_does_not_delete_completed(
		self, db_manager, test_ai_model
	):
		"""Test that delete_draft_block does not remove a block with response."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		req = Message(role=MessageRoleEnum.USER, content="question")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="answer")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		db_manager.save_message_block(conv_id, 0, block)

		db_manager.delete_draft_block(conv_id, 0)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		assert loaded.messages[0].response is not None

	def test_save_message_block_replaces_draft(self, db_manager, test_ai_model):
		"""Test that save_message_block replaces an existing draft."""
		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)

		# Save a draft first
		draft_req = Message(role=MessageRoleEnum.USER, content="draft")
		draft_block = MessageBlock(request=draft_req, model=test_ai_model)
		db_manager.save_draft_block(conv_id, 0, draft_block)

		# Now save a completed block at the same position
		req = Message(role=MessageRoleEnum.USER, content="final question")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="final answer")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		db_manager.save_message_block(conv_id, 0, block)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		assert loaded.messages[0].request.content == "final question"
		assert loaded.messages[0].response.content == "final answer"

	def test_draft_with_attachments_roundtrip(
		self, db_manager, test_ai_model, tmp_path
	):
		"""Test draft block with attachments round-trip."""
		from upath import UPath

		from basilisk.conversation import AttachmentFile

		text_path = UPath(tmp_path) / "draft_file.txt"
		with text_path.open("w") as f:
			f.write("draft attachment content")

		attachment = AttachmentFile(location=text_path)
		req = Message(
			role=MessageRoleEnum.USER,
			content="draft with file",
			attachments=[attachment],
		)
		block = MessageBlock(request=req, model=test_ai_model)

		conv = Conversation()
		conv_id = db_manager.save_conversation(conv)
		db_manager.save_draft_block(conv_id, 0, block)

		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 1
		assert loaded.messages[0].response is None
		atts = loaded.messages[0].request.attachments
		assert atts is not None
		assert len(atts) == 1
		assert atts[0].read_as_plain_text() == "draft attachment content"


class TestCleanupOrphanAttachments:
	"""Tests for cleanup_orphan_attachments."""

	def test_no_orphans_returns_zero(
		self, db_manager, conversation_with_attachments
	):
		"""Test that cleanup returns 0 when no orphans exist."""
		db_manager.save_conversation(conversation_with_attachments)
		assert db_manager.cleanup_orphan_attachments() == 0

	def test_orphans_removed_after_conversation_delete(
		self, db_manager, conversation_with_attachments
	):
		"""Test that orphaned attachments are removed after conversation delete."""
		from sqlalchemy import func, select

		from basilisk.conversation.database.models import DBAttachment

		conv_id = db_manager.save_conversation(conversation_with_attachments)

		with db_manager._get_session() as session:
			count_before = session.execute(
				select(func.count(DBAttachment.id))
			).scalar_one()
		assert count_before > 0

		# delete_conversation calls cleanup internally
		db_manager.delete_conversation(conv_id)

		with db_manager._get_session() as session:
			count_after = session.execute(
				select(func.count(DBAttachment.id))
			).scalar_one()
		assert count_after == 0

	def test_shared_attachment_not_removed(
		self, db_manager, test_ai_model, tmp_path
	):
		"""Test that an attachment shared between two conversations is kept."""
		from sqlalchemy import func, select
		from upath import UPath

		from basilisk.conversation import AttachmentFile
		from basilisk.conversation.database.models import DBAttachment

		text_path = UPath(tmp_path) / "shared.txt"
		text_path.write_text("shared content")

		def _make_conv():
			att = AttachmentFile(location=text_path)
			req = Message(
				role=MessageRoleEnum.USER, content="msg", attachments=[att]
			)
			block = MessageBlock(request=req, model=test_ai_model)
			conv = Conversation()
			conv.add_block(block)
			return conv

		id1 = db_manager.save_conversation(_make_conv())
		id2 = db_manager.save_conversation(_make_conv())

		# Deduplication: only one DBAttachment row
		with db_manager._get_session() as session:
			assert (
				session.execute(
					select(func.count(DBAttachment.id))
				).scalar_one()
				== 1
			)

		# Delete first — shared row must survive
		db_manager.delete_conversation(id1)
		with db_manager._get_session() as session:
			assert (
				session.execute(
					select(func.count(DBAttachment.id))
				).scalar_one()
				== 1
			)

		# Delete second — now orphaned, must be removed
		db_manager.delete_conversation(id2)
		with db_manager._get_session() as session:
			assert (
				session.execute(
					select(func.count(DBAttachment.id))
				).scalar_one()
				== 0
			)
