"""Base engine for OpenAI-compatible Responses API (OpenAI, xAI).

Shared message format, streaming, and response parsing for providers that use
client.responses.create() instead of chat completions.
"""

from __future__ import annotations

import logging
from typing import Any, Generator

from openai.types.responses import (
	EasyInputMessageParam,
	Response,
	ResponseCompletedEvent,
	ResponseInputFileContentParam,
	ResponseInputImageParam,
	ResponseInputTextParam,
	ResponseOutputMessage,
	ResponseOutputRefusal,
	ResponseOutputText,
	ResponseOutputTextParam,
	ResponseReasoningTextDeltaEvent,
	ResponseStreamEvent,
	ResponseTextDeltaEvent,
)

from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.content_utils import assistant_message_body_for_api
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.provider_engine.usage_utils import token_usage_responses_api

from .base_engine import BaseEngine

log = logging.getLogger(__name__)


def _audio_mime_to_format(mime_type: str) -> str | None:
	"""Map audio MIME type to OpenAI InputAudio format (mp3 or wav)."""
	if not mime_type or not mime_type.startswith("audio/"):
		return None
	if "mpeg" in mime_type or "mp3" in mime_type:
		return "mp3"
	if "wav" in mime_type:
		return "wav"
	return None


def _attachment_to_input_item(
	attachment: AttachmentFile | ImageFile,
	capabilities: set[ProviderCapability],
) -> ResponseInputImageParam | ResponseInputFileContentParam | None:
	"""Convert attachment to Responses API input item based on MIME type."""
	mime_type = attachment.mime_type or ""
	url = attachment.url

	if mime_type.startswith("image/"):
		return ResponseInputImageParam(
			image_url=url, detail="auto", type="input_image"
		)

	if mime_type.startswith("audio/"):
		# Responses API does not support input_audio. Use Chat Completions
		# (OpenAI gpt-audio) or transcribe first.
		return None

	if (
		mime_type.startswith("application/") or mime_type.startswith("text/")
	) and ProviderCapability.DOCUMENT in capabilities:
		return ResponseInputFileContentParam(
			type="input_file", file_url=url, filename=attachment.name
		)

	return None


class ResponsesAPIEngine(BaseEngine):
	"""Base for engines using OpenAI-compatible Responses API.

	Provides shared message preparation, streaming, and response parsing.
	Subclasses implement client, models, and _build_completion_params.
	"""

	def prepare_message_request(
		self, message: Message
	) -> EasyInputMessageParam:
		"""Prepares a message for Responses API input format."""
		super().prepare_message_request(message)
		content: list[
			ResponseInputTextParam
			| ResponseInputImageParam
			| ResponseInputFileContentParam
		] = [ResponseInputTextParam(text=message.content, type="input_text")]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				item = _attachment_to_input_item(attachment, self.capabilities)
				if item is None:
					mime = attachment.mime_type or ""
					if mime.startswith("audio/"):
						raise ValueError(
							"Audio attachments are not supported in the Responses API. "
							"Use a provider that supports audio in chat, or transcribe first (Ctrl+R)."
						)
					raise ValueError(f"Unsupported attachment format: {mime}")
				content.append(item)
		return EasyInputMessageParam(
			role=message.role.value, content=content, type="message"
		)

	def prepare_message_response(
		self, response: Message
	) -> EasyInputMessageParam:
		"""Prepares an assistant message for Responses API input format."""
		super().prepare_message_response(response)
		return EasyInputMessageParam(
			role=response.role.value,
			content=[
				ResponseOutputTextParam(
					text=assistant_message_body_for_api(response.content),
					type="output_text",
				)
			],
			type="message",
		)

	def _build_completion_params(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None,
		model: ProviderAIModel,
		kwargs: dict[str, Any],
	) -> dict[str, Any]:
		"""Build completion params. Subclasses override to add tools, reasoning, etc."""
		params: dict[str, Any] = {
			"model": model.id,
			"input": self.get_messages(
				new_block,
				conversation,
				system_message,
				stop_block_index=stop_block_index,
			),
			"stream": new_block.stream,
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
		}
		# Responses API does not support stream_options.include_usage; usage comes
		# automatically in ResponseCompletedEvent.
		if new_block.max_tokens:
			params["max_output_tokens"] = new_block.max_tokens
		params.update(self._get_block_generation_params(new_block, model))
		web_search = kwargs.pop("web_search_mode", False)
		if web_search and self.model_supports_web_search(model):
			tools = self.get_web_search_tool_definitions(model)
			if tools:
				params["tools"] = tools
		return params

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs: Any,
	) -> Response | Generator[ResponseStreamEvent, None, None]:
		"""Generates a completion using the Responses API."""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model = self.get_model(new_block.model.model_id)
		params = self._build_completion_params(
			new_block,
			conversation,
			system_message,
			stop_block_index,
			model,
			kwargs,
		)
		params.update(kwargs)
		params = self._filter_params_for_model(model, params)
		return self.client.responses.create(**params)

	def completion_response_with_stream(
		self,
		stream: Generator[ResponseStreamEvent, None, None],
		new_block: MessageBlock,
		**kwargs,
	):
		"""Processes a streaming Responses API response.

		Yields ("content", delta) tuples for CompletionHandler compatibility.
		Subclasses that support reasoning/audio override to yield additional
		chunk types ("reasoning", "citation", etc.).
		"""
		for event in stream:
			if (
				isinstance(event, ResponseReasoningTextDeltaEvent)
				and event.delta
			):
				yield ("reasoning", event.delta)
			elif isinstance(event, ResponseTextDeltaEvent) and event.delta:
				yield ("content", event.delta)
			elif isinstance(event, ResponseCompletedEvent) and event.response:
				if hasattr(event.response, "usage") and event.response.usage:
					new_block.usage = token_usage_responses_api(
						event.response.usage
					)
			else:
				log.warning(
					"Received unexpected event type: %s", type(event).__name__
				)
				continue

	def completion_response_without_stream(
		self, response: Response, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Processes a non-streaming Responses API response."""
		txt_parts = []
		for res_output in response.output:
			if isinstance(res_output, ResponseOutputMessage):
				for res_content in res_output.content:
					if isinstance(res_content, ResponseOutputText):
						txt_parts.append(res_content.text)
					elif isinstance(res_content, ResponseOutputRefusal):
						raise ValueError(
							f"Provider refused to answer: {res_content.refusal}"
						)
			else:
				log.warning(
					"Received unexpected output type: %s",
					type(res_output).__name__,
				)
				continue
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content="".join(txt_parts)
		)
		if hasattr(response, "usage") and response.usage:
			new_block.usage = token_usage_responses_api(response.usage)
		return new_block
