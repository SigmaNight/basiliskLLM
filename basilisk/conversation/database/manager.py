"""Database manager for conversation persistence."""

import hashlib
import logging
from pathlib import Path

from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session, sessionmaker

from basilisk.conversation.attached_file import (
	AttachmentFile,
	AttachmentFileTypes,
	ImageFile,
)
from basilisk.conversation.conversation_model import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.custom_types import PydanticOrderedSet
from basilisk.provider_ai_model import AIModelInfo

from .models import (
	DBAttachment,
	DBCitation,
	DBConversation,
	DBConversationSystemPrompt,
	DBMessage,
	DBMessageAttachment,
	DBMessageBlock,
	DBSystemPrompt,
)

log = logging.getLogger(__name__)


def _set_sqlite_pragmas(dbapi_conn, connection_record):
	"""Set SQLite pragmas on each new connection."""
	cursor = dbapi_conn.cursor()
	cursor.execute("PRAGMA journal_mode=WAL")
	cursor.execute("PRAGMA foreign_keys=ON")
	cursor.close()


class ConversationDatabase:
	"""Manages all database operations for conversation persistence."""

	def __init__(self, db_path: Path):
		"""Initialize the database manager.

		Args:
			db_path: Path to the SQLite database file.
		"""
		self._db_path = db_path
		self._engine = create_engine(f"sqlite:///{db_path}", echo=False)
		event.listen(self._engine, "connect", _set_sqlite_pragmas)
		self._session_factory = sessionmaker(bind=self._engine)
		self._run_migrations()
		log.info("Database initialized at %s", db_path)

	def _run_migrations(self):
		"""Run Alembic migrations to bring the database up to date."""
		from alembic import command
		from alembic.config import Config

		alembic_dir = Path(__file__).parent / "alembic"
		cfg = Config()
		cfg.set_main_option("script_location", str(alembic_dir))
		cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self._db_path}")
		command.upgrade(cfg, "head")
		log.debug("Database migrations applied")

	def _get_session(self) -> Session:
		"""Create a new database session."""
		return self._session_factory()

	def close(self):
		"""Close the database engine and release all connections."""
		self._engine.dispose()
		log.debug("Database engine disposed")

	# --- Write operations ---

	def save_conversation(self, conversation: Conversation) -> int:
		"""Save a full conversation to the database.

		Args:
			conversation: The Pydantic conversation to save.

		Returns:
			The database ID of the saved conversation.
		"""
		with self._get_session() as session:
			with session.begin():
				db_conv = DBConversation(title=conversation.title)
				session.add(db_conv)
				session.flush()

				# Save system prompts
				csp_map = self._save_system_prompts(
					session, db_conv, conversation.systems
				)

				# Save message blocks
				for position, block in enumerate(conversation.messages):
					self._save_block(
						session, db_conv.id, position, block, csp_map
					)

				conv_id = db_conv.id
		log.debug("Saved conversation %d", conv_id)
		return conv_id

	def _save_system_prompts(
		self,
		session: Session,
		db_conv: DBConversation,
		systems: PydanticOrderedSet,
	) -> dict[int, DBConversationSystemPrompt]:
		"""Save system prompts and return a mapping of position to CSP."""
		csp_map: dict[int, DBConversationSystemPrompt] = {}
		for position, system_msg in enumerate(systems):
			sp_id = self._get_or_create_system_prompt(session, system_msg)

			# Create conversation-system_prompt link
			db_csp = DBConversationSystemPrompt(
				conversation_id=db_conv.id,
				system_prompt_id=sp_id,
				position=position,
			)
			session.add(db_csp)
			session.flush()
			csp_map[position] = db_csp

		return csp_map

	def _get_or_create_system_prompt(
		self, session: Session, system_msg: SystemMessage
	) -> int:
		"""Get or create a system prompt, using cached db_id if available.

		Returns:
			The database ID of the system prompt.
		"""
		if system_msg.db_id is not None:
			return system_msg.db_id

		content_hash = hashlib.sha256(
			system_msg.content.encode("utf-8")
		).hexdigest()

		db_sp = session.execute(
			select(DBSystemPrompt).where(
				DBSystemPrompt.content_hash == content_hash
			)
		).scalar_one_or_none()
		if db_sp is None:
			db_sp = DBSystemPrompt(
				content_hash=content_hash, content=system_msg.content
			)
			session.add(db_sp)
			session.flush()

		system_msg.db_id = db_sp.id
		return db_sp.id

	def _save_block(
		self,
		session: Session,
		conv_id: int,
		position: int,
		block: MessageBlock,
		csp_map: dict[int, "DBConversationSystemPrompt"],
	):
		"""Save a single message block."""
		csp_id = None
		if block.system_index is not None and block.system_index in csp_map:
			csp_id = csp_map[block.system_index].id

		db_block = self._create_db_block(
			session, conv_id, position, block, csp_id
		)

		self._save_message(session, db_block.id, "user", block.request)
		if block.response:
			self._save_message(
				session, db_block.id, "assistant", block.response
			)

	def _save_message(
		self, session: Session, block_id: int, role: str, message: Message
	):
		"""Save a message with its attachments and citations."""
		db_msg = DBMessage(
			message_block_id=block_id, role=role, content=message.content
		)
		session.add(db_msg)
		session.flush()

		# Save attachments
		if message.attachments:
			for pos, attachment in enumerate(message.attachments):
				self._save_attachment(session, db_msg.id, pos, attachment)

		# Save citations
		if message.citations:
			for pos, citation in enumerate(message.citations):
				db_citation = DBCitation(
					message_id=db_msg.id,
					position=pos,
					cited_text=citation.get("cited_text"),
					source_title=citation.get("source_title"),
					source_url=citation.get("source_url"),
					start_index=citation.get("start_index"),
					end_index=citation.get("end_index"),
				)
				session.add(db_citation)

	def _save_attachment(
		self,
		session: Session,
		message_id: int,
		position: int,
		attachment: AttachmentFile | ImageFile,
	):
		"""Save an attachment, deduplicating by content hash."""
		att_id = attachment.db_id

		if att_id is None:
			# Need to compute hash and get or create attachment
			is_url = attachment.type == AttachmentFileTypes.URL
			if is_url:
				content_bytes = str(attachment.location).encode("utf-8")
			else:
				try:
					content_bytes = attachment.read_as_bytes()
				except Exception:
					log.warning(
						"Could not read attachment %s, skipping",
						attachment.name,
					)
					return

			content_hash = hashlib.sha256(content_bytes).hexdigest()

			db_att = session.execute(
				select(DBAttachment).where(
					DBAttachment.content_hash == content_hash
				)
			).scalar_one_or_none()

			if db_att is None:
				is_image = isinstance(attachment, ImageFile)

				db_att = DBAttachment(
					content_hash=content_hash,
					name=attachment.name,
					mime_type=attachment.mime_type,
					size=attachment.size,
					location_type=attachment.type.value,
					url=str(attachment.location) if is_url else None,
					blob_data=None if is_url else content_bytes,
					is_image=is_image,
					image_width=(
						attachment.dimensions[0]
						if is_image and attachment.dimensions
						else None
					),
					image_height=(
						attachment.dimensions[1]
						if is_image and attachment.dimensions
						else None
					),
				)
				session.add(db_att)
				session.flush()

			attachment.db_id = db_att.id
			att_id = db_att.id

		# Create message-attachment link
		db_ma = DBMessageAttachment(
			message_id=message_id,
			attachment_id=att_id,
			position=position,
			description=attachment.description,
		)
		session.add(db_ma)

	def _delete_block_at(
		self, session: Session, conv_id: int, block_index: int
	):
		"""Delete any existing block at the given position."""
		existing = session.execute(
			select(DBMessageBlock).where(
				DBMessageBlock.conversation_id == conv_id,
				DBMessageBlock.position == block_index,
			)
		).scalar_one_or_none()
		if existing is not None:
			session.delete(existing)
			session.flush()

	def _resolve_csp_id(
		self,
		session: Session,
		conv_id: int,
		block: MessageBlock,
		system_message: SystemMessage | None,
	) -> int | None:
		"""Resolve the conversation-system-prompt link ID for a block."""
		if system_message is None or block.system_index is None:
			return None

		sp_id = self._get_or_create_system_prompt(session, system_message)

		db_csp = session.execute(
			select(DBConversationSystemPrompt).where(
				DBConversationSystemPrompt.conversation_id == conv_id,
				DBConversationSystemPrompt.position == block.system_index,
			)
		).scalar_one_or_none()
		if db_csp is None:
			db_csp = DBConversationSystemPrompt(
				conversation_id=conv_id,
				system_prompt_id=sp_id,
				position=block.system_index,
			)
			session.add(db_csp)
			session.flush()
		return db_csp.id

	def _create_db_block(
		self,
		session: Session,
		conv_id: int,
		block_index: int,
		block: MessageBlock,
		csp_id: int | None,
	) -> DBMessageBlock:
		"""Create and flush a DBMessageBlock, updating block.db_id."""
		db_block = DBMessageBlock(
			conversation_id=conv_id,
			position=block_index,
			conversation_system_prompt_id=csp_id,
			model_provider=block.model.provider_id,
			model_id=block.model.model_id,
			temperature=block.temperature,
			max_tokens=block.max_tokens,
			top_p=block.top_p,
			stream=block.stream,
			created_at=block.created_at,
			updated_at=block.updated_at,
		)
		session.add(db_block)
		session.flush()
		block.db_id = db_block.id
		return db_block

	def save_message_block(
		self,
		conv_id: int,
		block_index: int,
		block: MessageBlock,
		system_message: SystemMessage | None = None,
	):
		"""Save a single new message block to an existing conversation.

		If a block already exists at the given position (e.g. a draft),
		it is deleted first.

		Args:
			conv_id: The database conversation ID.
			block_index: The position index of the block.
			block: The Pydantic message block to save.
			system_message: Optional system message associated with the block.
		"""
		with self._get_session() as session:
			with session.begin():
				self._delete_block_at(session, conv_id, block_index)
				csp_id = self._resolve_csp_id(
					session, conv_id, block, system_message
				)
				db_block = self._create_db_block(
					session, conv_id, block_index, block, csp_id
				)

				self._save_message(session, db_block.id, "user", block.request)
				if block.response:
					self._save_message(
						session, db_block.id, "assistant", block.response
					)

				# Update conversation timestamp
				session.execute(
					DBConversation.__table__.update()
					.where(DBConversation.id == conv_id)
					.values(updated_at=block.updated_at)
				)

		log.debug("Saved block %d for conversation %d", block_index, conv_id)

	def save_draft_block(
		self,
		conv_id: int,
		block_index: int,
		block: MessageBlock,
		system_message: SystemMessage | None = None,
	):
		"""Save or replace a draft block (request only, no response).

		If a block already exists at the given position, it is deleted
		first and replaced with the new draft.

		Args:
			conv_id: The database conversation ID.
			block_index: The position index of the draft block.
			block: The draft MessageBlock (response should be None).
			system_message: Optional system message associated with the block.
		"""
		with self._get_session() as session:
			with session.begin():
				self._delete_block_at(session, conv_id, block_index)
				csp_id = self._resolve_csp_id(
					session, conv_id, block, system_message
				)
				db_block = self._create_db_block(
					session, conv_id, block_index, block, csp_id
				)
				self._save_message(session, db_block.id, "user", block.request)

		log.debug(
			"Saved draft block %d for conversation %d", block_index, conv_id
		)

	def delete_draft_block(self, conv_id: int, block_index: int):
		"""Delete the draft block at the given position if it has no response.

		Only deletes blocks that have no assistant message (i.e. drafts).

		Args:
			conv_id: The database conversation ID.
			block_index: The position index of the draft block.
		"""
		with self._get_session() as session:
			with session.begin():
				db_block = session.execute(
					select(DBMessageBlock).where(
						DBMessageBlock.conversation_id == conv_id,
						DBMessageBlock.position == block_index,
					)
				).scalar_one_or_none()
				if db_block is None:
					return
				# Check if it has an assistant message
				has_response = any(
					msg.role == "assistant" for msg in db_block.messages
				)
				if has_response:
					return
				session.delete(db_block)

		log.debug(
			"Deleted draft block %d for conversation %d", block_index, conv_id
		)

	def update_conversation_title(self, conv_id: int, title: str | None):
		"""Update the title of a conversation.

		Args:
			conv_id: The database conversation ID.
			title: The new title, or None to clear it.
		"""
		with self._get_session() as session:
			with session.begin():
				db_conv = session.get(DBConversation, conv_id)
				if db_conv:
					db_conv.title = title

	def delete_conversation(self, conv_id: int):
		"""Delete a conversation and all related data.

		Args:
			conv_id: The database conversation ID.
		"""
		with self._get_session() as session:
			with session.begin():
				db_conv = session.get(DBConversation, conv_id)
				if db_conv:
					session.delete(db_conv)
		log.debug("Deleted conversation %d", conv_id)

	# --- Read operations ---

	@staticmethod
	def _apply_search_filter(query, search: str | None):
		"""Apply search filtering to a conversation query."""
		if not search:
			return query
		search_term = f"%{search}%"
		msg_conv_ids = (
			select(DBMessageBlock.conversation_id)
			.join(DBMessage)
			.where(DBMessage.content.like(search_term))
			.distinct()
			.subquery()
		)
		return query.where(
			DBConversation.title.like(search_term)
			| DBConversation.id.in_(select(msg_conv_ids.c.conversation_id))
		)

	def list_conversations(
		self, search: str | None = None, limit: int = 100, offset: int = 0
	) -> list[dict]:
		"""List conversations with optional search filtering.

		Args:
			search: Optional search term to filter by title or content.
			limit: Maximum number of results.
			offset: Number of results to skip.

		Returns:
			List of dicts with id, title, message_count, updated_at.
		"""
		with self._get_session() as session:
			block_count = (
				select(
					DBMessageBlock.conversation_id,
					func.count(DBMessageBlock.id).label("message_count"),
				)
				.group_by(DBMessageBlock.conversation_id)
				.subquery()
			)

			query = (
				select(
					DBConversation.id,
					DBConversation.title,
					func.coalesce(block_count.c.message_count, 0).label(
						"message_count"
					),
					DBConversation.updated_at,
				)
				.outerjoin(
					block_count,
					DBConversation.id == block_count.c.conversation_id,
				)
				.order_by(DBConversation.updated_at.desc())
			)

			query = self._apply_search_filter(query, search)
			query = query.limit(limit).offset(offset)
			rows = session.execute(query).all()

			return [
				{
					"id": row.id,
					"title": row.title,
					"message_count": row.message_count,
					"updated_at": row.updated_at,
				}
				for row in rows
			]

	def get_conversation_count(self, search: str | None = None) -> int:
		"""Get the total number of conversations.

		Args:
			search: Optional search term to filter.

		Returns:
			The count of matching conversations.
		"""
		with self._get_session() as session:
			query = select(func.count(DBConversation.id))
			query = self._apply_search_filter(query, search)
			return session.execute(query).scalar_one()

	def load_conversation(self, conv_id: int) -> Conversation:
		"""Load a conversation from the database.

		Args:
			conv_id: The database conversation ID.

		Returns:
			A Pydantic Conversation instance.

		Raises:
			ValueError: If the conversation does not exist.
		"""
		with self._get_session() as session:
			db_conv = session.get(DBConversation, conv_id)
			if db_conv is None:
				raise ValueError(f"Conversation {conv_id} not found")

			# Rebuild systems OrderedSet
			systems = PydanticOrderedSet[SystemMessage]()
			csp_links = sorted(
				db_conv.system_prompt_links, key=lambda x: x.position
			)
			for csp in csp_links:
				sys_msg = SystemMessage(content=csp.system_prompt.content)
				sys_msg.db_id = csp.system_prompt.id
				systems.add(sys_msg)

			# Rebuild message blocks
			blocks = []
			sorted_blocks = sorted(db_conv.blocks, key=lambda x: x.position)
			for db_block in sorted_blocks:
				# Find request and response messages
				request_msg = None
				response_msg = None
				for db_msg in db_block.messages:
					if db_msg.role == "user":
						request_msg = self._load_message(db_msg)
					elif db_msg.role == "assistant":
						response_msg = self._load_message(db_msg)

				if request_msg is None:
					log.warning(
						"Block %d has no request, skipping", db_block.id
					)
					continue

				# Determine system_index
				system_index = None
				if db_block.system_prompt_link is not None:
					system_index = db_block.system_prompt_link.position

				block = MessageBlock(
					request=request_msg,
					response=response_msg,
					system_index=system_index,
					model=AIModelInfo(
						provider_id=db_block.model_provider,
						model_id=db_block.model_id,
					),
					temperature=db_block.temperature,
					max_tokens=db_block.max_tokens,
					top_p=db_block.top_p,
					stream=db_block.stream,
					created_at=db_block.created_at,
					updated_at=db_block.updated_at,
				)
				block.db_id = db_block.id
				blocks.append(block)

			from basilisk.consts import BSKC_VERSION

			return Conversation(
				messages=blocks,
				systems=systems,
				title=db_conv.title,
				version=BSKC_VERSION,
			)

	def _load_message(self, db_msg: DBMessage) -> Message:
		"""Convert a DB message to a Pydantic message."""
		role = (
			MessageRoleEnum.USER
			if db_msg.role == "user"
			else MessageRoleEnum.ASSISTANT
		)

		# Load attachments
		attachments = None
		if db_msg.attachment_links:
			attachments = []
			sorted_links = sorted(
				db_msg.attachment_links, key=lambda x: x.position
			)
			for link in sorted_links:
				db_att = link.attachment
				attachment = self._load_attachment(db_att, link.description)
				if attachment:
					attachments.append(attachment)

		# Load citations
		citations = None
		if db_msg.citations:
			citations = []
			sorted_cites = sorted(db_msg.citations, key=lambda x: x.position)
			for db_cit in sorted_cites:
				citation = {}
				if db_cit.cited_text is not None:
					citation["cited_text"] = db_cit.cited_text
				if db_cit.source_title is not None:
					citation["source_title"] = db_cit.source_title
				if db_cit.source_url is not None:
					citation["source_url"] = db_cit.source_url
				if db_cit.start_index is not None:
					citation["start_index"] = db_cit.start_index
				if db_cit.end_index is not None:
					citation["end_index"] = db_cit.end_index
				citations.append(citation)

		return Message(
			role=role,
			content=db_msg.content,
			attachments=attachments or None,
			citations=citations or None,
		)

	@staticmethod
	def _make_attachment(
		db_att: DBAttachment, location, description: str | None
	) -> AttachmentFile | ImageFile:
		"""Build an AttachmentFile or ImageFile from a DB record."""
		if db_att.is_image:
			return ImageFile(
				location=location,
				name=db_att.name,
				description=description,
				size=db_att.size,
				mime_type=db_att.mime_type,
				dimensions=(
					(db_att.image_width, db_att.image_height)
					if db_att.image_width is not None
					and db_att.image_height is not None
					else None
				),
			)
		return AttachmentFile(
			location=location,
			name=db_att.name,
			description=description,
			size=db_att.size,
			mime_type=db_att.mime_type,
		)

	def _load_attachment(
		self, db_att: DBAttachment, description: str | None
	) -> AttachmentFile | ImageFile | None:
		"""Convert a DB attachment to a Pydantic attachment."""
		from upath import UPath

		if db_att.location_type == AttachmentFileTypes.URL.value:
			return self._make_attachment(db_att, UPath(db_att.url), description)

		# BLOB attachment - write to memory filesystem
		if db_att.blob_data is None:
			log.warning("Attachment %s has no blob data", db_att.name)
			return None

		mem_path = UPath(
			f"memory://db_attachment_{db_att.id}/{db_att.name or 'file'}"
		)
		mem_path.parent.mkdir(parents=True, exist_ok=True)
		with mem_path.open("wb") as f:
			f.write(db_att.blob_data)

		return self._make_attachment(db_att, mem_path, description)
