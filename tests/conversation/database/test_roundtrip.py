"""Tests for Pydantic <-> DB round-trip conversions."""

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)


class TestPydanticToDBRoundtrip:
	"""Tests for saving and loading conversations."""

	def test_simple_conversation_roundtrip(
		self, db_manager, conversation_with_blocks
	):
		"""Test saving and loading a simple conversation."""
		conv = conversation_with_blocks
		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		assert loaded.title == conv.title
		assert len(loaded.messages) == len(conv.messages)
		for orig, restored in zip(conv.messages, loaded.messages):
			assert restored.request.content == orig.request.content
			assert restored.response.content == orig.response.content

	def test_conversation_with_multiple_systems_roundtrip(
		self, db_manager, test_ai_model
	):
		"""Test round-trip with multiple system prompts."""
		conv = Conversation()
		system1 = SystemMessage(content="System prompt 1")
		system2 = SystemMessage(content="System prompt 2")

		# Block 0 with system1
		req0 = Message(role=MessageRoleEnum.USER, content="Q0")
		resp0 = Message(role=MessageRoleEnum.ASSISTANT, content="A0")
		block0 = MessageBlock(request=req0, response=resp0, model=test_ai_model)
		conv.add_block(block0, system1)

		# Block 1 with system2
		req1 = Message(role=MessageRoleEnum.USER, content="Q1")
		resp1 = Message(role=MessageRoleEnum.ASSISTANT, content="A1")
		block1 = MessageBlock(request=req1, response=resp1, model=test_ai_model)
		conv.add_block(block1, system2)

		# Block 2 with system1 (reused)
		req2 = Message(role=MessageRoleEnum.USER, content="Q2")
		resp2 = Message(role=MessageRoleEnum.ASSISTANT, content="A2")
		block2 = MessageBlock(request=req2, response=resp2, model=test_ai_model)
		conv.add_block(block2, system1)

		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		assert len(loaded.systems) == 2
		assert loaded.systems[0].content == "System prompt 1"
		assert loaded.systems[1].content == "System prompt 2"
		assert loaded.messages[0].system_index == 0
		assert loaded.messages[1].system_index == 1
		assert loaded.messages[2].system_index == 0

	def test_conversation_with_attachments_roundtrip(
		self, db_manager, conversation_with_attachments
	):
		"""Test round-trip preserves attachment metadata."""
		conv = conversation_with_attachments
		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		orig_atts = conv.messages[0].request.attachments
		loaded_atts = loaded.messages[0].request.attachments

		assert loaded_atts is not None
		assert len(loaded_atts) == len(orig_atts)

		# Check text attachment
		assert loaded_atts[0].name == orig_atts[0].name
		assert loaded_atts[0].mime_type == orig_atts[0].mime_type
		assert loaded_atts[0].size == orig_atts[0].size

		# Check image attachment
		assert loaded_atts[1].name == orig_atts[1].name
		assert loaded_atts[1].mime_type == orig_atts[1].mime_type

	def test_attachment_content_readable(
		self, db_manager, conversation_with_attachments
	):
		"""Test that BLOB content is readable from memory path."""
		conv = conversation_with_attachments
		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		loaded_att = loaded.messages[0].request.attachments[0]
		content = loaded_att.read_as_plain_text()
		assert content == "test content"

	def test_attachment_dedup_roundtrip(
		self, db_manager, test_ai_model, tmp_path
	):
		"""Test that the same file attached twice is deduplicated."""
		from upath import UPath

		from basilisk.conversation import AttachmentFile

		text_path = UPath(tmp_path) / "shared.txt"
		with text_path.open("w") as f:
			f.write("shared content")

		conv = Conversation()

		# Two blocks with the same attachment
		for i in range(2):
			att = AttachmentFile(location=text_path)
			req = Message(
				role=MessageRoleEnum.USER, content=f"Msg {i}", attachments=[att]
			)
			block = MessageBlock(request=req, model=test_ai_model)
			conv.add_block(block)

		conv_id = db_manager.save_conversation(conv)

		# Verify only 1 attachment row in DB
		from sqlalchemy import func, select

		from basilisk.conversation.database.models import DBAttachment

		with db_manager._get_session() as session:
			count = session.execute(
				select(func.count(DBAttachment.id))
			).scalar_one()
		assert count == 1

		# But both messages should have the attachment restored
		loaded = db_manager.load_conversation(conv_id)
		assert loaded.messages[0].request.attachments is not None
		assert loaded.messages[1].request.attachments is not None
		assert len(loaded.messages[0].request.attachments) == 1
		assert len(loaded.messages[1].request.attachments) == 1

		# Verify the restored content matches the original
		content0 = (
			loaded.messages[0].request.attachments[0].read_as_plain_text()
		)
		content1 = (
			loaded.messages[1].request.attachments[0].read_as_plain_text()
		)
		assert content0 == "shared content"
		assert content1 == "shared content"

	def test_conversation_model_params_roundtrip(
		self, db_manager, test_ai_model
	):
		"""Test that model parameters are preserved."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="Hello")
		block = MessageBlock(
			request=req,
			model=test_ai_model,
			temperature=0.7,
			max_tokens=2048,
			top_p=0.9,
			stream=True,
		)
		conv.add_block(block)

		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		loaded_block = loaded.messages[0]
		assert loaded_block.temperature == 0.7
		assert loaded_block.max_tokens == 2048
		assert loaded_block.top_p == 0.9
		assert loaded_block.stream is True
		assert loaded_block.model.provider_id == "openai"
		assert loaded_block.model.model_id == "test_model"

	def test_conversation_timestamps_roundtrip(
		self, db_manager, conversation_with_blocks
	):
		"""Test that timestamps are preserved."""
		conv = conversation_with_blocks
		orig_created = conv.messages[0].created_at
		orig_updated = conv.messages[0].updated_at

		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		# Compare with second precision (SQLite may truncate microseconds)
		assert loaded.messages[0].created_at.replace(
			microsecond=0
		) == orig_created.replace(microsecond=0)
		assert loaded.messages[0].updated_at.replace(
			microsecond=0
		) == orig_updated.replace(microsecond=0)

	def test_conversation_with_citations_roundtrip(
		self, db_manager, conversation_with_citations
	):
		"""Test that citations are preserved."""
		conv = conversation_with_citations
		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		citations = loaded.messages[0].response.citations
		assert citations is not None
		assert len(citations) == 2

		assert citations[0]["cited_text"] == "X is important"
		assert citations[0]["source_title"] == "Source A"
		assert citations[0]["source_url"] == "https://example.com/a"
		assert citations[0]["start_index"] == 0
		assert citations[0]["end_index"] == 14

		assert citations[1]["cited_text"] == "X was discovered"
		assert citations[1]["source_title"] == "Source B"
		assert "source_url" not in citations[1]

	def test_incremental_save_then_load(self, db_manager, test_ai_model):
		"""Test the auto-save flow: save conv, add block, save block, load all."""
		conv = Conversation()
		conv.title = "Incremental"

		# Initial save with one block
		req1 = Message(role=MessageRoleEnum.USER, content="First")
		resp1 = Message(role=MessageRoleEnum.ASSISTANT, content="Reply 1")
		block1 = MessageBlock(request=req1, response=resp1, model=test_ai_model)
		conv.add_block(block1)
		conv_id = db_manager.save_conversation(conv)

		# Add second block incrementally
		req2 = Message(role=MessageRoleEnum.USER, content="Second")
		resp2 = Message(role=MessageRoleEnum.ASSISTANT, content="Reply 2")
		block2 = MessageBlock(request=req2, response=resp2, model=test_ai_model)
		conv.add_block(block2)
		db_manager.save_message_block(conv_id, 1, block2)

		# Load and verify
		loaded = db_manager.load_conversation(conv_id)
		assert loaded.title == "Incremental"
		assert len(loaded.messages) == 2
		assert loaded.messages[0].request.content == "First"
		assert loaded.messages[1].request.content == "Second"
		assert loaded.messages[1].response.content == "Reply 2"

	def test_no_response_block_roundtrip(self, db_manager, test_ai_model):
		"""Test block with no response (request only)."""
		conv = Conversation()
		req = Message(role=MessageRoleEnum.USER, content="No reply")
		block = MessageBlock(request=req, model=test_ai_model)
		conv.add_block(block)

		conv_id = db_manager.save_conversation(conv)
		loaded = db_manager.load_conversation(conv_id)

		assert len(loaded.messages) == 1
		assert loaded.messages[0].request.content == "No reply"
		assert loaded.messages[0].response is None

	def test_draft_block_roundtrip(self, db_manager, test_ai_model, tmp_path):
		"""Test saving a conversation with completed blocks + draft, then reload."""
		from upath import UPath

		from basilisk.conversation import AttachmentFile

		conv = Conversation()
		system = SystemMessage(content="System instructions")

		# Add a completed block
		req = Message(role=MessageRoleEnum.USER, content="Hello")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="Hi there")
		block = MessageBlock(request=req, response=resp, model=test_ai_model)
		conv.add_block(block, system)
		conv_id = db_manager.save_conversation(conv)

		# Add a draft block at position 1
		text_path = UPath(tmp_path) / "draft.txt"
		with text_path.open("w") as f:
			f.write("draft file content")

		attachment = AttachmentFile(location=text_path)
		draft_req = Message(
			role=MessageRoleEnum.USER,
			content="work in progress",
			attachments=[attachment],
		)
		draft_block = MessageBlock(
			request=draft_req,
			model=test_ai_model,
			temperature=0.5,
			max_tokens=1024,
			top_p=0.8,
			stream=True,
		)
		db_manager.save_draft_block(conv_id, 1, draft_block, system)

		# Reload and verify
		loaded = db_manager.load_conversation(conv_id)
		assert len(loaded.messages) == 2

		# First block is completed
		assert loaded.messages[0].response is not None
		assert loaded.messages[0].response.content == "Hi there"

		# Second block is the draft
		draft = loaded.messages[1]
		assert draft.response is None
		assert draft.request.content == "work in progress"
		assert draft.temperature == 0.5
		assert draft.max_tokens == 1024
		assert draft.top_p == 0.8
		assert draft.stream is True
		assert draft.request.attachments is not None
		assert len(draft.request.attachments) == 1
		assert (
			draft.request.attachments[0].read_as_plain_text()
			== "draft file content"
		)
