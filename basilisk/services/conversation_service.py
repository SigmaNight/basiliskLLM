"""Service layer for conversation persistence and business logic.

Handles database operations, draft management, and title generation
without any wx dependency.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

import basilisk.config as config
from basilisk.conversation import (
	PROMPT_TITLE,
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.provider_ai_model import AIModelInfo
from basilisk.sound_manager import play_sound, stop_sound

if TYPE_CHECKING:
	from basilisk.conversation.database import ConversationDatabase
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class ConversationService:
	"""Encapsulates database persistence and business logic for a conversation.

	This class is free of wx dependencies and operates on primitive values
	and model objects, making it fully testable without a GUI.

	Attributes:
		db_conv_id: Database conversation ID, or None if not yet persisted.
		private: Whether the conversation is in private mode.
	"""

	def __init__(self, conv_db_getter: Callable[[], ConversationDatabase]):
		"""Initialize the conversation service.

		Args:
			conv_db_getter: Callable that returns the ConversationDatabase
				singleton (deferred to avoid import-time wx dependency).
		"""
		self._get_conv_db = conv_db_getter
		self.db_conv_id: Optional[int] = None
		self.private: bool = False

	def auto_save_to_db(
		self, conversation: Conversation, new_block: MessageBlock
	):
		"""Auto-save the conversation or new block to the database.

		Args:
			conversation: The current conversation.
			new_block: The newly completed message block to save.
		"""
		if not config.conf().conversation.auto_save_to_db:
			return
		if self.private:
			return
		try:
			if self.db_conv_id is None:
				self.db_conv_id = self._get_conv_db().save_conversation(
					conversation
				)
			else:
				block_index = conversation.messages.index(new_block)
				system_msg = None
				if new_block.system_index is not None:
					system_msg = conversation.systems[new_block.system_index]
				self._get_conv_db().save_message_block(
					self.db_conv_id, block_index, new_block, system_msg
				)
		except Exception:
			log.error(
				"Failed to auto-save conversation to database", exc_info=True
			)

	def update_db_title(self, title: Optional[str]):
		"""Update the conversation title in the database.

		Args:
			title: The new title for the conversation.
		"""
		if self.db_conv_id is None:
			return
		try:
			self._get_conv_db().update_conversation_title(
				self.db_conv_id, title
			)
		except Exception:
			log.error(
				"Failed to update conversation title in database", exc_info=True
			)

	def should_auto_save_draft(self) -> bool:
		"""Return True if auto-save draft is active for this conversation."""
		conf = config.conf()
		return (
			conf.conversation.auto_save_to_db
			and conf.conversation.auto_save_draft
			and not self.private
			and self.db_conv_id is not None
		)

	def set_private(self, private: bool) -> tuple[bool, bool]:
		"""Set the private flag. If enabling, delete conversation from DB.

		Args:
			private: Whether the conversation should be private.

		Returns:
			A tuple of (success, should_stop_timer). success is False when a
			DB deletion was required but failed; the private flag and
			db_conv_id are left unchanged so the caller can retry or notify
			the user. should_stop_timer is True only on a successful
			transition to private with an existing DB record.
		"""
		should_stop_timer = False
		if private and self.db_conv_id is not None:
			try:
				self._get_conv_db().delete_conversation(self.db_conv_id)
				self.db_conv_id = None
				should_stop_timer = True
			except Exception:
				log.error(
					"Failed to delete conversation from DB", exc_info=True
				)
				return False, False
		self.private = private
		return True, should_stop_timer

	def save_conversation(
		self,
		conversation: Conversation,
		file_path: str,
		draft_block: Optional[MessageBlock] = None,
	) -> tuple[bool, Optional[Exception]]:
		"""Save the conversation to a file.

		If a draft block is provided, it is temporarily appended before
		saving and then removed.

		Args:
			conversation: The conversation to save.
			file_path: The target file path.
			draft_block: Optional draft block to include.

		Returns:
			A tuple of (success, exception_or_none).
		"""
		log.debug("Saving conversation to %s", file_path)
		if draft_block is not None:
			conversation.messages.append(draft_block)
		try:
			conversation.save(file_path)
			return True, None
		except Exception as e:
			return False, e
		finally:
			if draft_block is not None:
				conversation.messages.pop()

	def save_draft_to_db(
		self,
		conversation: Conversation,
		draft_block: Optional[MessageBlock],
		system_msg: Optional[SystemMessage],
	):
		"""Save (or delete) the current draft in the database.

		Args:
			conversation: The current conversation.
			draft_block: The draft message block, or None to delete.
			system_msg: The current system message.
		"""
		if self.db_conv_id is None:
			return
		if draft_block is None:
			try:
				self._get_conv_db().delete_draft_block(
					self.db_conv_id, len(conversation.messages)
				)
			except Exception:
				log.error("Failed to delete draft", exc_info=True)
			return
		try:
			self._get_conv_db().save_draft_block(
				self.db_conv_id,
				len(conversation.messages),
				draft_block,
				system_msg,
			)
		except Exception:
			log.error("Failed to save draft", exc_info=True)

	def generate_title(
		self,
		engine: BaseEngine,
		conversation: Conversation,
		provider_id: str,
		model_id: str,
		temperature: float,
		top_p: float,
		max_tokens: int,
		stream: bool,
	) -> Optional[str]:
		"""Generate a conversation title using the AI model.

		Args:
			engine: The provider engine to use.
			conversation: The conversation to generate a title for.
			provider_id: The provider ID for the message block.
			model_id: The model ID for the message block.
			temperature: Temperature setting.
			top_p: Top-p setting.
			max_tokens: Max tokens setting.
			stream: Stream mode setting.

		Returns:
			The generated title string, or None on failure.
		"""
		play_sound("progress", loop=True)
		try:
			new_block = MessageBlock(
				request=Message(
					role=MessageRoleEnum.USER, content=PROMPT_TITLE
				),
				model=AIModelInfo(provider_id=provider_id, model_id=model_id),
				temperature=temperature,
				top_p=top_p,
				max_tokens=max_tokens,
				stream=stream,
			)
			completion_kw = {
				"system_message": None,
				"conversation": conversation,
				"new_block": new_block,
				"stream": False,
			}
			response = engine.completion(**completion_kw)
			new_block = engine.completion_response_without_stream(
				response=response, **completion_kw
			)
			return new_block.response.content
		except Exception:
			log.error("Title generation failed", exc_info=True)
			return None
		finally:
			stop_sound()
