"""Module for OpenAI API integration.

This module provides the OpenAIEngine class for interacting with the OpenAI API,
implementing capabilities for text, image, and audio generation/processing.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Generator

from openai import OpenAI
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
	WebSearchToolParam,
)

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .base_engine import BaseEngine
from .dynamic_model_loader import load_models_from_url

OPENAI_MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/openai.json"

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)


class OpenAIEngine(BaseEngine):
	"""Engine implementation for OpenAI API integration.

	Provides functionality for interacting with OpenAI's models, supporting text,
	image, speech-to-text, and text-to-speech capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.STT,
		ProviderCapability.TTS,
		ProviderCapability.WEB_SEARCH,
	}

	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the OpenAI engine.

		Args:
			account: Account configuration for the OpenAI provider.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> OpenAI:
		"""Creates and configures the OpenAI client.

		Returns:
			Configured OpenAI client instance.
		"""
		super().client
		organization_key = (
			self.account.active_organization_key.get_secret_value()
			if self.account.active_organization_key
			else None
		)
		return OpenAI(
			api_key=self.account.api_key.get_secret_value(),
			organization=organization_key,
			base_url=self.account.custom_base_url
			or str(self.account.provider.base_url),
		)

	_REASONING_ONLY_IDS = frozenset({"o1", "o3", "o3-mini", "o4-mini"})
	_WEB_SEARCH_EXCLUDED_IDS = frozenset({"gpt-4.1-nano"})

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available OpenAI models from model-metadata JSON.

		Returns:
			List of supported OpenAI models, sorted by created (newest first).
		"""
		super().models
		log.debug("Getting OpenAI models")
		models = load_models_from_url(OPENAI_MODELS_JSON_URL)
		for m in models:
			if m.id in self._REASONING_ONLY_IDS:
				m.reasoning = True
				m.reasoning_capable = False
		return models

	def model_supports_web_search(self, model: ProviderAIModel) -> bool:
		"""Exclude gpt-4.1-nano and gpt-5 (minimal reasoning) per OpenAI docs."""
		if model.id in self._WEB_SEARCH_EXCLUDED_IDS:
			return False
		return super().model_supports_web_search(model)

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[WebSearchToolParam]:
		"""Return web_search_preview tool for Responses API."""
		return [
			WebSearchToolParam(
				type="web_search_preview", search_context_size="medium"
			)
		]

	def prepare_message_request(
		self, message: Message
	) -> EasyInputMessageParam:
		"""Prepares a message for OpenAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			OpenAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [
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
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			OpenAI API compatible assistant message parameter.
		"""
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

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> Response | Generator[ResponseStreamEvent, None, None]:
		"""Generates a chat completion using the OpenAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			Either a complete chat completion response or a generator for streaming
			chat completion chunks.
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
			"input": self.get_messages(
				new_block,
				conversation,
				system_message,
				stop_block_index=stop_block_index,
			),
			"stream": new_block.stream,
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
			"store": False,
		}
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		if tools:
			params["tools"] = tools
		params.update(kwargs)
		response = self.client.responses.create(**params)
		return response

	def completion_response_with_stream(
		self, stream: Generator[ResponseStreamEvent, None, None]
	):
		"""Processes a streaming completion response.

		Args:
			stream: Generator of chat completion chunks.

		Yields:
			Content from each chunk in the stream.
		"""
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
		"""Processes a non-streaming completion response.

		Args:
			response: The chat completion response.
			new_block: The message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			Updated message block containing the response.
		"""
		txt_parts = []
		for res_output in response.output:
			if isinstance(res_output, ResponseOutputMessage):
				for res_content in res_output.content:
					if isinstance(res_content, ResponseOutputText):
						txt_parts.append(res_content.text)
					elif isinstance(res_content, ResponseOutputRefusal):
						raise ValueError(
							f"OpenAI refused to answer the question: {res_content.refusal}"
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

	def get_transcription(
		self, audio_file_path: str, response_format: str = "json"
	) -> str:
		"""Transcribes audio to text using OpenAI's Whisper model.

		Args:
			audio_file_path: Path to the audio file.
			response_format: Format of the response (defaults to "json").

		Returns:
			Transcription of the audio content.
		"""
		file = open(audio_file_path, "rb")
		transcription = self.client.audio.transcriptions.create(
			model="whisper-1", file=file, response_format=response_format
		)
		file.close()
		return transcription
