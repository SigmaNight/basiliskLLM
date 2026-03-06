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
	ResponseInputImageParam,
	ResponseInputTextParam,
	ResponseOutputMessage,
	ResponseOutputRefusal,
	ResponseOutputText,
	ResponseOutputTextParam,
	ResponseStreamEvent,
	ResponseTextDeltaEvent,
)

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import ProviderAIModel

from .base_engine import BaseEngine

log = logging.getLogger(__name__)


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
		content: list[ResponseInputTextParam | ResponseInputImageParam] = [
			ResponseInputTextParam(text=message.content, type="input_text")
		]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				content.append(
					ResponseInputImageParam(
						image_url=attachment.url,
						detail="auto",
						type="input_image",
					)
				)
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
					text=response.content, type="output_text"
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
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
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
		self, stream: Generator[ResponseStreamEvent, None, None], **kwargs
	):
		"""Processes a streaming Responses API response."""
		for event in stream:
			if isinstance(event, ResponseTextDeltaEvent):
				yield event.delta
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
		return new_block
