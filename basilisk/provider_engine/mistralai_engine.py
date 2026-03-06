"""Module for MistralAI API integration.

This module provides the MistralAIEngine class for interacting with the MistralAI API,
implementing capabilities for text and image generation/processing.
"""

from __future__ import annotations

import logging
import os
from functools import cached_property
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Generator

from mistralai import Mistral
from mistralai.models import ChatCompletionResponse, CompletionEvent
from mistralai.utils.eventstreaming import EventStream

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.attached_file import AttachmentFile
from basilisk.provider_engine.usage_utils import token_usage_openai_style

from .mistralai_ocr import handle_ocr

if TYPE_CHECKING:
	from basilisk.config import Account
from .base_engine import BaseEngine, ProviderCapability

log = logging.getLogger(__name__)


class MistralAIEngine(BaseEngine):
	"""Engine implementation for MistralAI API integration.

	Provides functionality for interacting with MistralAI's models, supporting text,
	image and document capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, document, and OCR.
	"""

	# Voxtral models support audio in chat; transcription uses dedicated endpoint
	_STT_MODEL = "voxtral-mini-latest"

	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
		ProviderCapability.AUDIO,
		ProviderCapability.DOCUMENT,
		ProviderCapability.OCR,
		ProviderCapability.STT,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
		"application/pdf",
		"audio/mpeg",
		"audio/wav",
		"audio/mp4",
		"audio/webm",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the MistralAI engine.

		Args:
			account: Account configuration for the MistralAI provider.
		"""
		super().__init__(account)

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/mistralai.json"

	@cached_property
	def client(self) -> Mistral:
		"""Creates and configures the Mistral client.

		Returns:
			Configured MistralAI client instance.
		"""
		return Mistral(
			api_key=self.account.api_key.get_secret_value(),
			server_url=self.account.custom_base_url
			or self.account.provider.base_url,
		)

	def prepare_message_request(self, message: Message) -> dict[str, Any]:
		"""Prepares a message for MistralAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			MistralAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [{"type": "text", "text": message.content}]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				mime_type = attachment.mime_type or ""
				if mime_type.startswith("image/"):
					content.append(
						{"type": "image_url", "image_url": attachment.url}
					)
				elif mime_type.startswith("audio/"):
					url = attachment.url
					if url.startswith("data:"):
						parts = url.split(",", 1)
						audio_data = parts[1] if len(parts) == 2 else url
					else:
						audio_data = url
					content.append(
						{"type": "input_audio", "input_audio": audio_data}
					)
				else:
					content.append(
						{"type": "document_url", "document_url": attachment.url}
					)
		return {"role": message.role.value, "content": content}

	def prepare_message_response(self, response: Message) -> dict[str, Any]:
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			MistralAI API compatible assistant message parameter.
		"""
		super().prepare_message_response(response)
		return {
			"role": response.role.value,
			"content": [{"type": "text", "text": response.content}],
		}

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> ChatCompletionResponse | EventStream[CompletionEvent]:
		"""Generates a chat completion using the MistralAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			The chat completion response.
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		params = {
			"model": new_block.model.model_id,
			"messages": self.get_messages(
				new_block,
				conversation,
				system_message,
				stop_block_index=stop_block_index,
			),
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		if new_block.stream:
			return self.client.chat.stream(**params)
		return self.client.chat.complete(**params)

	def completion_response_with_stream(
		self,
		stream: Generator[CompletionEvent, None, None],
		new_block: MessageBlock,
		**kwargs,
	):
		"""Processes a streaming completion response.

		Args:
			stream: Generator of chat completion chunks.
			new_block: Block to set usage on when available.
			**kwargs: Additional arguments passed through.

		Yields:
			Content from each chunk in the stream.
		"""
		for chunk in stream:
			data = chunk.data
			if not data.choices:
				if hasattr(data, "usage") and data.usage:
					new_block.usage = token_usage_openai_style(data.usage)
				continue
			delta = data.choices[0].delta
			if delta and delta.content:
				yield delta.content

	def completion_response_without_stream(
		self,
		response: ChatCompletionResponse,
		new_block: MessageBlock,
		**kwargs,
	) -> MessageBlock:
		"""Processes a non-streaming completion response.

		Args:
			response: The chat completion response.
			new_block: The message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			Updated message block containing the response.
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=response.choices[0].message.content,
		)
		if hasattr(response, "usage") and response.usage:
			new_block.usage = token_usage_openai_style(response.usage)
		return new_block

	def get_transcription(
		self, audio_file_path: str, response_format: str = "json"
	):
		"""Transcribe audio using Mistral's Voxtral transcription API.

		Uses POST /v1/audio/transcriptions with voxtral-mini-latest.
		Supports WAV (from recording) and other formats per Mistral docs.

		Args:
			audio_file_path: Path to the audio file.
			response_format: Ignored; Mistral returns text directly.

		Returns:
			Object with .text attribute (matches OpenAI Whisper interface).
		"""
		with open(audio_file_path, "rb") as f:
			result = self.client.audio.transcriptions.complete(
				model=self._STT_MODEL,
				file={
					"file_name": os.path.basename(audio_file_path),
					"content": f,
				},
			)
		# Normalize to match OpenAI interface: object with .text
		text = getattr(result, "text", None) or ""
		return SimpleNamespace(text=text)

	@staticmethod
	def handle_ocr(
		api_key: str, base_url: str, attachments: list[AttachmentFile], **kwargs
	) -> tuple[str, Any]:
		"""Extracts text from images using OCR.

		Args:
			api_key: The API key for the MistralAI account
			base_url: The base URL for the MistralAI API
			attachments: List of attachments to extract text from
			**kwargs: Additional keyword arguments

		Returns:
			List of file paths containing the extracted text.
		"""
		return handle_ocr(api_key, base_url, attachments, **kwargs)
