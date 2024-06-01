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
	from account import Account
from .baseengine import BaseEngine, ProviderAIModel

log = logging.getLogger(__name__)


class AnthropicAIEngine(BaseEngine):
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
		return [
			ProviderAIModel(
				id="claude-3-opus-20240229",
				name="Claude 3 Opus",
				# Translators: This is a ProviderAIModel description
				description=_("Most powerful model for highly complex tasks"),
				# Translators: This is a model description
				context_window=200000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-sonnet-20240229",
				name="Claude 3 Sonnet",
				# Translators: This is a model description
				description=_(
					"Ideal balance of intelligence and speed for enterprise workloads"
				),
				context_window=200000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-haiku-20240307",
				name="claude-3-haiku-20240307",
				# Translators: This is a model description
				description=_(
					"Fastest and most compact model fornear-instant responsiveness"
				),
				context_window=200000,
				max_output_tokens=4096,
				vision=True,
			),
		]

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	):
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.id,
			"messages": self.get_messages(new_block, conversation, None),
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

	def completion_response_with_stream(self, stream):
		for event in stream:
			match event.type:
				case "content_block_delta":
					yield event.delta.text

	def completion_response_without_stream(
		self, response, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=self.normalize_linesep(response.content[0].text),
		)
		return new_block
