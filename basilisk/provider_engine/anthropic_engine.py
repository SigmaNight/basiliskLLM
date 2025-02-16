"""Module for Anthropic API integration.

This module provides the AnthropicEngine class for interacting with the Anthropic API,
implementing capabilities for text and image generation.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Iterator

from anthropic import Anthropic
from anthropic.types import Message as AnthropicMessage
from anthropic.types import TextBlock
from anthropic.types.document_block_param import DocumentBlockParam
from anthropic.types.image_block_param import ImageBlockParam, Source
from anthropic.types.text_block_param import TextBlockParam

from basilisk.conversation import (
	AttachmentFileTypes,
	Conversation,
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
	"""Engine implementation for Anthropic API integration.

	Provides functionality for interacting with Anthropic's Claude models,
	supporting both text and image processing capabilities.

	Attributes:
		capabilities: Set of supported capabilities including
			text and image generation.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
		ProviderCapability.DOCUMENT,
		ProviderCapability.CITATION,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
		"application/pdf",
		"text/plain",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the engine with the given account.

		Args:
			account: The provider account configuration.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> Anthropic:
		"""Property to return the client object for the Anthropic API.

		Returns:
			The client object for the Anthropic API initialized with the account API key.
		"""
		super().client
		return Anthropic(api_key=self.account.api_key.get_secret_value())

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the Anthropic ai provider.

		Returns:
			List of Anthropic models.
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

	def convert_message(self, message: Message) -> dict:
		"""Converts internal message format to Anthropic API format.

		Args:
			message: Message to be converted.

		Returns:
			Message in Anthropic API format with role and content.
		"""
		contents = [TextBlock(text=message.content, type="text")]
		if message.attachments:
			for attachment in message.attachments:
				mime_type = attachment.mime_type
				if attachment.type != AttachmentFileTypes.URL:
					source = Source(
						data=None,
						media_type=attachment.mime_type,
						type="base64",
					)
					if mime_type.startswith("image/"):
						source["data"] = attachment.encode_image()
						contents.append(
							ImageBlockParam(source=source, type="image")
						)
					elif mime_type.startswith("application/"):
						source["data"] = attachment.encode_base64()
						contents.append(
							DocumentBlockParam(
								type="document",
								source=source,
								citations={"enabled": True},
							)
						)
					elif mime_type in ("text/plain"):
						source["data"] = attachment.read_as_str()
						source["type"] = "text"
						contents.append(
							TextBlockParam(
								type="document",
								source=source,
								citations={"enabled": True},
							)
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
		"""Sends a completion request to the Anthropic API.

		Args:
			new_block: Message block with generation parameters.
			conversation: Current conversation context.
			system_message: Optional system-level instruction message.
			**kwargs: Additional API request parameters.

		Returns:
			Either a complete message or a stream of message events.
		"""
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
	) -> Iterator[TextBlock | dict]:
		"""Processes streaming response from Anthropic API.

		Args:
			stream: Stream of message events from the API.

		Yields:
			Text content from each event.
		"""
		for event in stream:
			match event.type:
				case "content_block_delta":
					match event.delta.type:
						case "text_delta":
							yield event.delta.text
						case "citations_delta":
							citation = event.delta.citation
							citation_chunk_data = {
								"type": citation.type,
								"cited_text": citation.cited_text,
								"document_index": citation.document_index,
								"document_title": citation.document_title,
							}
							match citation.type:
								case "char_location":
									citation_chunk_data.update(
										{
											"start_char_index": citation.start_char_index,
											"end_char_index": citation.end_char_index,
										}
									)
								case "page_location":
									citation_chunk_data.update(
										{
											"start_page_number": citation.start_page_number,  # inclusive,
											"end_page_number": citation.end_page_number,  # exclusive
										}
									)
								case _:
									log.warning(
										f"Unsupported citation type: {citation.type}"
									)
							yield ("citation", citation_chunk_data)

	def completion_response_without_stream(
		self, response: AnthropicMessage, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Processes non-streaming response from Anthropic API.

		Args:
			response: Complete message from the API.
			new_block: Message block to update.
			**kwargs: Additional processing parameters.

		Returns:
			Updated message block with response.
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content=response.content[0].text
		)
		return new_block
