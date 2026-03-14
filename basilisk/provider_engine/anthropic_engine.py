"""Module for Anthropic API integration.

This module provides the AnthropicEngine class for interacting with the Anthropic API,
implementing capabilities for text and image generation.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Iterator

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
from basilisk.conversation.content_utils import assistant_message_body_for_api

if TYPE_CHECKING:
	from anthropic._streaming import Stream
	from anthropic.types.message_stream_event import MessageStreamEvent

	from basilisk.config import Account

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability
from .provider_ui_spec import ReasoningUISpec
from .reasoning_api_enums import (
	AnthropicCitationLocationType,
	AnthropicContentBlockType,
	AnthropicReasoningEffort,
	AnthropicStreamDeltaType,
	AnthropicStreamEventType,
)
from .stream_chunk_type import StreamChunkType
from .usage_utils import token_usage_anthropic

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
		return Anthropic(api_key=self.account.api_key.get_secret_value())

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/anthropic.json"

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[dict[str, Any]]:
		"""Return web_search_20250305 tool for Anthropic Messages API."""
		return [{"type": "web_search_20250305", "name": "web_search"}]

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""Anthropic: adaptive thinking + budget tokens. 4.6 adds effort for adaptive."""
		spec = super().get_reasoning_ui_spec(model)
		if not spec.show:
			return spec
		model_id = model.id or ""
		show_adaptive = "4.6" in model_id or "4-6" in model_id
		# 4.6 adaptive uses output_config.effort (low/medium/high; max for Opus only)
		effort_opts = ("low", "medium", "high")
		if "opus" in model_id.lower() and "4.6" in model_id:
			effort_opts = ("low", "medium", "high", "max")
		return ReasoningUISpec(
			show=True,
			show_adaptive=show_adaptive,
			show_budget=True,
			show_effort=show_adaptive,
			effort_options=effort_opts,
			effort_label="Adaptive effort:",
			budget_default=16000,
			budget_max=128000,
		)

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
		match attachment.mime_type.split("/")[0]:
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
		text = (
			assistant_message_body_for_api(message.content)
			if message.role == MessageRoleEnum.ASSISTANT
			else (message.content or "")
		)
		contents = [TextBlock(text=text, type="text")]
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
		stop_block_index: int | None = None,
		**kwargs,
	) -> Message | Stream[MessageStreamEvent]:
		"""Sends a completion request to the Anthropic API.

		Args:
			new_block: Message block with generation parameters.
			conversation: Current conversation context.
			system_message: Optional system-level instruction message.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional API request parameters.

		Returns:
			Either a complete message or a stream of message events.
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model = self.get_model(new_block.model.model_id)
		tools = []
		web_search = kwargs.pop("web_search_mode", False)
		if web_search and model and self.model_supports_web_search(model):
			tools.extend(self.get_web_search_tool_definitions(model))
		params = {
			"model": model.id,
			"messages": self.get_messages(
				new_block, conversation, stop_block_index=stop_block_index
			),
			"temperature": new_block.temperature,
			"stream": new_block.stream,
		}
		# When 0, use model max (Anthropic requires max_tokens); else use block value
		params["max_tokens"] = (
			new_block.max_tokens or model.effective_max_output_tokens
		)
		# Only include top_p if it's not the default value (1.0)
		# New Claude 4 models don't allow both temperature and top_p
		if new_block.top_p != 1.0:
			params["top_p"] = new_block.top_p
		gen_params = self._get_block_generation_params(new_block, model)
		if "stop" in gen_params:
			params["stop_sequences"] = gen_params["stop"]
			gen_params = {k: v for k, v in gen_params.items() if k != "stop"}
		params.update(gen_params)
		if system_message:
			params["system"] = system_message.content
		if tools:
			params["tools"] = tools
		if model.reasoning:
			params.pop("top_p", None)
			params["thinking"] = {
				"type": "enabled",
				"budget_tokens": new_block.reasoning_budget_tokens or 16000,
			}
		elif model.reasoning_capable and new_block.reasoning_mode:
			params.pop("top_p", None)
			_supports_adaptive = "4.6" in (model.id or "") or "4-6" in (
				model.id or ""
			)
			if new_block.reasoning_adaptive and _supports_adaptive:
				params["thinking"] = {"type": "adaptive"}
				if new_block.reasoning_effort:
					effort = new_block.reasoning_effort.lower()
					if AnthropicReasoningEffort.is_valid(effort):
						params["output_config"] = {"effort": effort}
			else:
				params["thinking"] = {
					"type": "enabled",
					"budget_tokens": new_block.reasoning_budget_tokens or 16000,
				}
		params.update(kwargs)
		params = self._filter_params_for_model(model, params)
		response = self.client.messages.create(**params)
		return response

	def _handle_citation(self, citation: dict) -> dict:
		"""Processes citation data from the API response.

		Args:
			citation: Citation data from the API response.

		Returns:
			Processed citation data.
		"""
		citation_chunk_data = {}
		try:
			AnthropicCitationLocationType(citation.type)
		except ValueError:
			log.warning("Unsupported citation type: %s", citation.type)
		else:
			citation_chunk_data = dict(citation)
		return citation_chunk_data

	def _handle_content_block_delta(
		self, event: MessageStreamEvent
	) -> str | tuple[StreamChunkType, Any] | None:
		"""Handles content block delta events from the stream."""
		match event.delta.type:
			case AnthropicStreamDeltaType.TEXT_DELTA:
				return event.delta.text
			case AnthropicStreamDeltaType.THINKING_DELTA:
				return (StreamChunkType.REASONING, event.delta.thinking)
			case AnthropicStreamDeltaType.CITATIONS_DELTA:
				return (
					StreamChunkType.CITATION,
					self._handle_citation(event.delta.citation),
				)
		return None

	def completion_response_with_stream(
		self,
		stream: Stream[MessageStreamEvent],
		new_block: MessageBlock,
		**kwargs,
	) -> Iterator[tuple[StreamChunkType, Any]]:
		"""Processes streaming response from Anthropic API.

		Yields reasoning, content, or citation chunks.
		"""
		for event in stream:
			match event.type:
				case AnthropicStreamEventType.CONTENT_BLOCK_DELTA:
					content = self._handle_content_block_delta(event)
					if content is not None:
						if isinstance(content, tuple):
							yield content
						else:
							yield (StreamChunkType.CONTENT, content)
				case AnthropicStreamEventType.MESSAGE_DELTA:
					if hasattr(event, "usage") and event.usage:
						new_block.usage = token_usage_anthropic(event.usage)
				case AnthropicStreamEventType.MESSAGE_STOP:
					break

	def completion_response_without_stream(
		self, response: AnthropicMessage, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Processes non-streaming response from Anthropic API.

		Response content is an array of blocks: ThinkingBlock (type=thinking)
		and TextBlock (type=text). Per API docs, there is no top-level
		thinking field—thinking lives inside content blocks.

		Args:
			response: Complete message from the API.
			new_block: Message block to update.
			**kwargs: Additional processing parameters.

		Returns:
			Updated message block with response.
		"""
		citations = []
		text_parts = []
		reasoning_parts = []
		for block in response.content:
			block_type = getattr(block, "type", None)
			if block_type == AnthropicContentBlockType.THINKING:
				thinking = getattr(block, "thinking", None) or ""
				if thinking:
					reasoning_parts.append(thinking)
			elif block_type == AnthropicContentBlockType.TEXT:
				text_parts.append(getattr(block, "text", None) or "")
				for citation in getattr(block, "citations", None) or []:
					citations.append(self._handle_citation(citation))
		content = "".join(text_parts)
		reasoning = "\n\n".join(reasoning_parts) if reasoning_parts else None
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=content,
			reasoning=reasoning,
			citations=citations,
		)
		if hasattr(response, "usage") and response.usage:
			new_block.usage = token_usage_anthropic(response.usage)
		return new_block
