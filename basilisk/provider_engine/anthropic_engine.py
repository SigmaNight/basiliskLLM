from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

from anthropic import Anthropic

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

if TYPE_CHECKING:
	from anthropic._streaming import Stream
	from anthropic.types import Message as AnthropicMessage
	from anthropic.types.message_stream_event import MessageStreamEvent

	from basilisk.config import Account
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class AnthropicEngine(BaseEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	def __init__(self, account: Account) -> None:
		super().__init__(account)

	@cached_property
	def client(self) -> Anthropic:
		"""
		Property to return the client object
		"""
		super().client
		return Anthropic(api_key=self.account.api_key.get_secret_value())
		log.debug("New Anthropic client initialized")

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		super().models
		log.debug("Getting Anthropic models")
		# See <https://docs.anthropic.com/en/docs/about-claude/models>
		return [
			ProviderAIModel(
				id="claude-3-5-sonnet-latest",
				name="Claude 3.5 Sonnet",
				# Translators: This is a model description
				description=_(
					"Point to the most recent snapshot of Claude 3.5 Sonnet"
				),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-5-haiku-latest",
				name="Claude 3.5 Haiku",
				# Translators: This is a model description
				description=_(
					"Point to the most recent snapshot of Claude 3.5 Haiku"
				),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-5-haiku-20241022",
				# Translators: This is a model description
				description=_(
					"Our fastest model. Intelligence at blazing speeds"
				),
				context_window=200000,
				max_output_tokens=8192,
				vision=False,
			),
			ProviderAIModel(
				id="claude-3-5-sonnet-20241022",
				# Translators: This is a model description
				description=_(
					"Most intelligent model. Highest level of intelligence and capability"
				),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-5-sonnet-20240620",
				# Translators: This is a model description
				description=_("Most intelligent model, previous version"),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-opus-20240229",
				name="Claude 3 Opus",
				# Translators: This is a model description
				description=_("Powerful model for highly complex tasks"),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-sonnet-20240229",
				name="Claude 3 Sonnet",
				# Translators: This is a model description
				description=_("Balance of intelligence and speed"),
				context_window=200000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-haiku-20240307",
				name="Claude 3 Haiku",
				# Translators: This is a model description
				description=_(
					"Fastest and most compact model for near-instant responsiveness"
				),
				context_window=200000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="claude-2.1",
				name="Claude 2.1",
				# Translators: This is a model description
				description=_(
					"Updated version of Claude 2 with improved accuracy"
				),
				context_window=200000,
				max_output_tokens=4096,
				vision=False,
			),
			ProviderAIModel(
				id="claude-2.0",
				name="Claude 2",
				# Translators: This is a model description
				description=_(
					"Predecessor to Claude 3, offering strong all-round performance"
				),
				context_window=100000,
				max_output_tokens=4096,
				vision=False,
			),
		]

	def get_message(self, message: Message) -> dict[str, str]:
		if isinstance(message.content, list):
			content = []
			for item in message.content:
				if item.type == "text":
					content.append(item)
				elif (
					item.type == "image_url"
					and isinstance(item.image_url, dict)
					and item.image_url["url"].startswith("data:")
				):
					image1_media_type, image1_data = item.image_url[
						"url"
					].split(";", 1)
					image1_media_type = image1_media_type.split(":", 1)[1]
					image1_data = image1_data.split(",", 1)[1]
					content.append(
						{
							"type": "image",
							"source": {
								"type": "base64",
								"media_type": image1_media_type,
								"data": image1_data,
							},
						}
					)
				else:
					raise ValueError("Unsupported content type")
			return {"role": message.role.value, "content": content}
		if isinstance(message.content, str):
			return message.model_dump(mode="json")
		raise ValueError("Unsupported content message type")

	def get_messages(
		self, new_block: MessageBlock, conversation: Conversation
	) -> list[Message]:
		"""
		Get messages
		"""
		messages = []
		for message_block in conversation.messages:
			if not message_block.response:
				continue
			messages.append(self.get_message(message_block.request))
			messages.append(self.get_message(message_block.response))
		messages.append(self.get_message(new_block.request))
		log.debug("Messages: %s", messages)
		return messages

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> Message | Stream[MessageStreamEvent]:
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.id,
			"messages": self.get_messages(new_block, conversation),
			"temperature": new_block.temperature,
			"max_tokens": new_block.max_tokens
			or new_block.model.max_output_tokens,
			"top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		if system_message:
			params["system"] = system_message.model_dump(mode="json")["content"]
		params.update(kwargs)
		response = self.client.messages.create(**params)
		return response

	def completion_response_with_stream(
		self, stream: Stream[MessageStreamEvent]
	):
		for event in stream:
			match event.type:
				case "content_block_delta":
					yield event.delta.text

	def completion_response_without_stream(
		self, response: AnthropicMessage, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=self.normalize_linesep(response.content[0].text),
		)
		return new_block
