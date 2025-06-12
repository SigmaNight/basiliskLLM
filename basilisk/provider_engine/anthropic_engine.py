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

from basilisk.conversation import (
	AttachmentFile,
	AttachmentFileTypes,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
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
		ProviderCapability.WEB_SEARCH,
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
				id="claude-sonnet-4-0",
				name="Claude Sonnet 4",
				# Translators: This is a model description
				description=_("High-performance model"),
				context_window=200000,
				max_output_tokens=64000,
				vision=True,
			),
			ProviderAIModel(
				id="claude-sonnet-4-0_reasoning",
				name="Claude Sonnet 4 (thinking)",
				# Translators: This is a model description
				description=_("High-performance model"),
				context_window=200000,
				max_output_tokens=64000,
				vision=True,
				reasoning=True,
			),
			ProviderAIModel(
				id="claude-opus-4-0",
				name="Claude Opus 4",
				# Translators: This is a model description
				description=_("Our most capable model"),
				context_window=200000,
				max_output_tokens=32000,
				vision=True,
			),
			ProviderAIModel(
				id="claude-opus-4-0_reasoning",
				name="Claude Opus 4 (thinking)",
				# Translators: This is a model description
				description=_("Our most capable model"),
				context_window=200000,
				max_output_tokens=32000,
				vision=True,
				reasoning=True,
			),
			ProviderAIModel(
				id="claude-3-7-sonnet-latest",
				name="Claude 3.7 Sonnet",
				# Translators: This is a model description
				description=_(
					"High-performance model with early extended thinking"
				),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-7-sonnet-latest_reasoning",
				name="Claude 3.7 Sonnet (thinking)",
				# Translators: This is a model description
				description=_(
					"High-performance model with early extended thinking"
				),
				context_window=200000,
				max_output_tokens=64000,
				vision=True,
				reasoning=True,
			),
			ProviderAIModel(
				id="claude-3-5-sonnet-latest",
				name="Claude 3.5 Sonnet",
				# Translators: This is a model description
				description=_("Our previous intelligent model"),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-5-haiku-latest",
				name="Claude 3.5 Haiku",
				# Translators: This is a model description
				description=_("Our fastest model"),
				context_window=200000,
				max_output_tokens=8192,
				vision=True,
			),
			ProviderAIModel(
				id="claude-3-opus-20240229",
				name="Claude Opus 3",
				# Translators: This is a model description
				description=_("Powerful model for complex tasks"),
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
		]

	def get_attachment_source(
		self, attachment: AttachmentFile | ImageFile
	) -> dict:
		"""Get the source for the attachment.

		Args:
			attachment: Attachment to process.

		Returns:
			Attachment source data.
		"""
		if attachment.type == AttachmentFileTypes.URL:
			return {"type": "url", "url": attachment.url}
		elif attachment.type != AttachmentFileTypes.UNKNOWN:
			source = {"media_type": attachment.mime_type}
			match attachment.mime_type.split("/")[0]:
				case "image" | "application":
					source["type"] = "base64"
					source["data"] = attachment.encode_base64()
				case "text":
					source["type"] = "text"
					source["data"] = attachment.read_as_plain_text()
				case _:
					raise ValueError(
						f"Unsupported attachment type: {attachment.type}"
					)
			return source

	def get_attachment_extras(
		self, attachment: AttachmentFile | ImageFile
	) -> dict:
		"""Get the extras for the attachment.

		Args:
			attachment: Attachment to process.

		Returns:
			Attachment extra data.
		"""
		extras = {}
		match attachment.mime_type.split('/')[0]:
			case "image":
				extras["type"] = "image"
			case "application" | "text":
				extras["type"] = "document"
				extras["citations"] = {"enabled": True}
			case _:
				raise ValueError(
					f"Unsupported attachment type: {attachment.type}"
				)
		return extras

	def convert_message(self, message: Message) -> dict:
		"""Converts internal message format to Anthropic API format.

		Args:
			message: Message to be converted.

		Returns:
			Message in Anthropic API format with role and content.
		"""
		contents = [TextBlock(text=message.content, type="text")]
		if message.attachments:
			# TODO: implement "context" and "title" for documents
			# TODO: add support for custom content document format
			for attachment in message.attachments:
				source = self.get_attachment_source(attachment)
				extras = self.get_attachment_extras(attachment)
				if not source or not extras:
					raise ValueError(
						f"Unsupported attachment type: {attachment.type}"
					)
				contents.append({"source": source} | extras)
		return {"role": message.role.value, "content": contents}

	prepare_message_request = convert_message
	prepare_message_response = convert_message

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: SystemMessage | None,
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
		tools = None
		web_search = kwargs.pop("web_search_mode", False)
		if web_search:
			tools = [{"type": "web_search_20250305", "name": "web_search"}]
		model = self.get_model(new_block.model.model_id)
		params = {
			"model": model.id,
			"messages": self.get_messages(new_block, conversation),
			"temperature": new_block.temperature,
			"max_tokens": new_block.max_tokens or model.max_output_tokens,
			"top_p": new_block.top_p,
			"tools": tools,
			"stream": new_block.stream,
		}
		if system_message:
			params["system"] = system_message.content
		if model.reasoning:
			params.pop("top_p", None)
			params["model"] = model.id.replace("_reasoning", "")
			params["thinking"] = {
				"type": "enabled",
				"budget_tokens": kwargs.get("budget_tokens", 16000),
			}
		params.update(kwargs)
		response = self.client.messages.create(**params)
		return response

	def _handle_citation(self, citation: dict) -> dict:
		"""Processes citation data from the API response.

		Args:
			citation: Citation data from the API response.

		Returns:
			Processed citation data.
		"""
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
				log.warning("Unsupported citation type: %s", citation.type)
		return citation_chunk_data

	def _handle_thinking(
		self, started: bool, event: MessageStreamEvent
	) -> tuple[str, bool]:
		"""Handles the 'thinking' content in the API response.

		Args:
			started: Flag indicating if thinking content has started.
			event: Event data from the API response.

		Returns:
			Tuple containing the thinking content and updated started flag.
		"""
		if not started:
			started = True
			content = f"```think\n {event.delta.thinking}"
			return content, started
		else:
			return event.delta.thinking, started

	def _handle_content_block_stop(
		self, thinking_content_started: bool, current_block_type: str
	) -> tuple[str | None, bool]:
		"""Handles content block stop events from the stream.

		Args:
			thinking_content_started: Flag indicating if thinking content has started.
			current_block_type: Type of the current content block.

		Returns:
			Tuple containing optional yield content and updated thinking_started flag.
		"""
		if thinking_content_started and current_block_type == "thinking":
			return "\n```\n\n", False
		return None, thinking_content_started

	def _handle_content_block_delta(
		self, event: MessageStreamEvent, thinking_content_started: bool
	) -> tuple[str | tuple[str, dict] | None, bool]:
		"""Handles content block delta events from the stream.

		Args:
			event: The stream event to process.
			thinking_content_started: Flag indicating if thinking content has started.

		Returns:
			Tuple containing yield content and updated thinking_started flag.
		"""
		match event.delta.type:
			case "text_delta":
				return event.delta.text, thinking_content_started
			case "thinking_delta":
				text, updated_started = self._handle_thinking(
					thinking_content_started, event
				)
				return text, updated_started
			case "citations_delta":
				return (
					("citation", self._handle_citation(event.delta.citation)),
					thinking_content_started,
				)
		return None, thinking_content_started

	def completion_response_with_stream(
		self, stream: Stream[MessageStreamEvent]
	) -> Iterator[TextBlock | dict]:
		"""Processes streaming response from Anthropic API.

		Args:
			stream: Stream of message events from the API.

		Yields:
			Text content from each event or thinking content.
		"""
		thinking_content_started = False
		current_block_type = None
		for event in stream:
			match event.type:
				case "content_block_start":
					current_block_type = event.content_block.type
				case "content_block_stop":
					content, thinking_content_started = (
						self._handle_content_block_stop(
							thinking_content_started, current_block_type
						)
					)
					if content:
						yield content
				case "content_block_delta":
					content, thinking_content_started = (
						self._handle_content_block_delta(
							event, thinking_content_started
						)
					)
					if content:
						yield content
				case "message_stop":
					if thinking_content_started:
						yield "\n```\n"
					break

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
		citations = []
		text = []
		thinking_content = None
		if hasattr(response, "thinking") and response.thinking:
			thinking_content = response.thinking
		for content in response.content:
			if content.citations:
				for citation in content.citations:
					citations.append(self._handle_citation(citation))
			text.append(content.text)
		final_content = ''.join(text)
		if thinking_content:
			final_content = (
				f"```think\n{thinking_content}\n```\n\n{final_content}"
			)
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=final_content,
			citations=citations,
		)
		return new_block
