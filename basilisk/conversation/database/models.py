"""SQLAlchemy models for conversation persistence."""

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Index, LargeBinary, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
	"""Base class for all SQLAlchemy models."""

	pass


class DBConversation(Base):
	"""Represents a conversation stored in the database."""

	__tablename__ = "conversations"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	title: Mapped[str | None] = mapped_column(default=None)
	created_at: Mapped[datetime] = mapped_column(
		default=lambda: datetime.now(timezone.utc)
	)
	updated_at: Mapped[datetime] = mapped_column(
		default=lambda: datetime.now(timezone.utc),
		onupdate=lambda: datetime.now(timezone.utc),
	)

	system_prompt_links: Mapped[list["DBConversationSystemPrompt"]] = (
		relationship(
			back_populates="conversation",
			cascade="all, delete-orphan",
			order_by="DBConversationSystemPrompt.position",
		)
	)
	blocks: Mapped[list["DBMessageBlock"]] = relationship(
		back_populates="conversation",
		cascade="all, delete-orphan",
		order_by="DBMessageBlock.position",
	)

	__table_args__ = (Index("ix_conversations_updated", updated_at.desc()),)


class DBSystemPrompt(Base):
	"""Stores deduplicated system prompts by content hash."""

	__tablename__ = "system_prompts"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	content_hash: Mapped[str] = mapped_column(unique=True)
	content: Mapped[str]


class DBConversationSystemPrompt(Base):
	"""Links a conversation to a system prompt at a specific position."""

	__tablename__ = "conversation_system_prompts"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	conversation_id: Mapped[int] = mapped_column(
		ForeignKey("conversations.id", ondelete="CASCADE")
	)
	system_prompt_id: Mapped[int] = mapped_column(
		ForeignKey("system_prompts.id")
	)
	position: Mapped[int]

	conversation: Mapped["DBConversation"] = relationship(
		back_populates="system_prompt_links"
	)
	system_prompt: Mapped["DBSystemPrompt"] = relationship()

	__table_args__ = (
		UniqueConstraint("conversation_id", "position"),
		Index("ix_conv_sys_prompts_conv", "conversation_id"),
	)


class DBMessageBlock(Base):
	"""Represents a message block (request/response pair) in a conversation."""

	__tablename__ = "message_blocks"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	conversation_id: Mapped[int] = mapped_column(
		ForeignKey("conversations.id", ondelete="CASCADE")
	)
	position: Mapped[int]
	conversation_system_prompt_id: Mapped[int | None] = mapped_column(
		ForeignKey("conversation_system_prompts.id", ondelete="SET NULL"),
		default=None,
	)
	model_provider: Mapped[str]
	model_id: Mapped[str]
	temperature: Mapped[float] = mapped_column(default=1.0)
	max_tokens: Mapped[int] = mapped_column(default=4096)
	top_p: Mapped[float] = mapped_column(default=1.0)
	stream: Mapped[bool] = mapped_column(default=False)
	created_at: Mapped[datetime] = mapped_column(
		default=lambda: datetime.now(timezone.utc)
	)
	updated_at: Mapped[datetime] = mapped_column(
		default=lambda: datetime.now(timezone.utc),
		onupdate=lambda: datetime.now(timezone.utc),
	)

	conversation: Mapped["DBConversation"] = relationship(
		back_populates="blocks"
	)
	messages: Mapped[list["DBMessage"]] = relationship(
		back_populates="message_block", cascade="all, delete-orphan"
	)
	system_prompt_link: Mapped["DBConversationSystemPrompt | None"] = (
		relationship()
	)

	__table_args__ = (
		UniqueConstraint("conversation_id", "position"),
		Index("ix_message_blocks_conversation", "conversation_id", "position"),
	)


class DBMessage(Base):
	"""Represents a single message (user or assistant) within a block."""

	__tablename__ = "messages"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	message_block_id: Mapped[int] = mapped_column(
		ForeignKey("message_blocks.id", ondelete="CASCADE")
	)
	role: Mapped[str]
	content: Mapped[str]

	message_block: Mapped["DBMessageBlock"] = relationship(
		back_populates="messages"
	)
	attachment_links: Mapped[list["DBMessageAttachment"]] = relationship(
		back_populates="message",
		cascade="all, delete-orphan",
		order_by="DBMessageAttachment.position",
	)
	citations: Mapped[list["DBCitation"]] = relationship(
		back_populates="message",
		cascade="all, delete-orphan",
		order_by="DBCitation.position",
	)

	__table_args__ = (
		UniqueConstraint("message_block_id", "role"),
		Index("ix_messages_block", "message_block_id"),
	)


class DBAttachment(Base):
	"""Stores deduplicated attachments by content hash."""

	__tablename__ = "attachments"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	content_hash: Mapped[str] = mapped_column(unique=True)
	name: Mapped[str | None] = mapped_column(default=None)
	mime_type: Mapped[str | None] = mapped_column(default=None)
	size: Mapped[int | None] = mapped_column(default=None)
	location_type: Mapped[str]
	url: Mapped[str | None] = mapped_column(default=None)
	blob_data: Mapped[bytes | None] = mapped_column(LargeBinary, default=None)
	is_image: Mapped[bool] = mapped_column(default=False)
	image_width: Mapped[int | None] = mapped_column(default=None)
	image_height: Mapped[int | None] = mapped_column(default=None)


class DBMessageAttachment(Base):
	"""Links a message to an attachment at a specific position."""

	__tablename__ = "message_attachments"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	message_id: Mapped[int] = mapped_column(
		ForeignKey("messages.id", ondelete="CASCADE")
	)
	attachment_id: Mapped[int] = mapped_column(ForeignKey("attachments.id"))
	position: Mapped[int]
	description: Mapped[str | None] = mapped_column(default=None)

	message: Mapped["DBMessage"] = relationship(
		back_populates="attachment_links"
	)
	attachment: Mapped["DBAttachment"] = relationship()

	__table_args__ = (UniqueConstraint("message_id", "position"),)


class DBCitation(Base):
	"""Stores citation information for assistant messages."""

	__tablename__ = "citations"

	id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
	message_id: Mapped[int] = mapped_column(
		ForeignKey("messages.id", ondelete="CASCADE")
	)
	position: Mapped[int]
	cited_text: Mapped[str | None] = mapped_column(default=None)
	source_title: Mapped[str | None] = mapped_column(default=None)
	source_url: Mapped[str | None] = mapped_column(default=None)
	start_index: Mapped[int | None] = mapped_column(default=None)
	end_index: Mapped[int | None] = mapped_column(default=None)

	message: Mapped["DBMessage"] = relationship(back_populates="citations")
