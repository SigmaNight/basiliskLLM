from __future__ import annotations

from abc import ABC, abstractmethod
from functools import cached_property
from os import linesep
from typing import TYPE_CHECKING, Any

from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

if TYPE_CHECKING:
	from basilisk.account import Account


class BaseEngine(ABC):
	capabilities: set[ProviderCapability] = set()

	def __init__(self, account: Account) -> None:
		self.account = account

	@cached_property
	@abstractmethod
	def client(self):
		"""
		Property to return the client object
		"""
		pass

	@cached_property
	@abstractmethod
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		pass

	@staticmethod
	def get_messages(
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
	) -> list[Message]:
		"""
		Get messages
		"""
		messages = []
		if system_message:
			messages.append(system_message.model_dump(mode="json"))
		for message_block in conversation.messages:
			if not message_block.response:
				continue
			messages.extend(
				[
					message_block.request.model_dump(mode="json"),
					message_block.response.model_dump(mode="json"),
				]
			)
		messages.append(new_block.request.model_dump(mode="json"))
		return messages

	@abstractmethod
	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	):
		"""
		Completion
		"""
		pass

	@abstractmethod
	def completion_response_with_stream(
		self, response: Any, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""
		Response with stream
		"""
		pass

	@abstractmethod
	def completion_response_without_stream(
		self, response: Any, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""
		Response without stream
		"""
		pass

	@staticmethod
	def normalize_linesep(text: str) -> str:
		"""
		Normalize new line characters using the system's line separator
		"""
		if text and isinstance(text, str) and linesep != "\n":
			text = text.replace('\n', linesep)
		return text

	@staticmethod
	def get_user_agent() -> str:
		"""
		Get user agent
		"""
		return f"{APP_NAME} ({APP_SOURCE_URL})"

	def get_transcription(self, *args, **kwargs) -> str:
		"""
		Get transcription from audio file
		"""
		raise NotImplementedError(
			"Transcription not implemented for this engine"
		)
