from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage
from anthropic.types import TextBlock
from anthropic.types.image_block_param import ImageBlockParam, Source

from basilisk.conversation import (
	Conversation,
	ImageFileTypes,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

if TYPE_CHECKING:
	from anthropic._streaming import Stream
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
		"""Property to return the client object"""
		super().client
		return Anthropic(api_key=self.account.api_key.get_secret_value())

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Get models"""
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

	def convert_message(self, message: Message) -> dict:
		contents = [TextBlock(text=message.content, type="text")]
		if message.attachments:
			for attachment in message.attachments:
				if attachment.type != ImageFileTypes.IMAGE_URL:
					source = Source(
						data=attachment.encode_image(),
						media_type=attachment.mime_type,
						type="base64",
					)
					contents.append(
						ImageBlockParam(source=source, type="image")
					)
		return {"role": message.role.value, "content": contents}

	prepare_message_request = convert_message
	prepare_message_response = convert_message

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> Message | Stream[MessageStreamEvent]:
		super().completion(new_block, conversation, system_message, **kwargs)
		model = self.get_model(new_block.model.model_id)
		params = {
			"model": model.id,
			"messages": self.get_messages(new_block, conversation),
			"temperature": new_block.temperature,
			"max_tokens": new_block.max_tokens or model.max_output_tokens,
			"top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		if system_message:
			params["system"] = system_message.content
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
			role=MessageRoleEnum.ASSISTANT, content=response.content[0].text
		)
		return new_block
