"""Module for OpenAI API integration.

This module provides the OpenAIEngine class for interacting with the OpenAI API,
implementing capabilities for text, image, and audio generation/processing.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any, Generator

from openai import OpenAI
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from openai.types.responses import WebSearchToolParam

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.content_utils import assistant_message_body_for_api
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.provider_engine.usage_utils import token_usage_openai_style

from .provider_ui_spec import AudioOutputUISpec, ReasoningUISpec
from .reasoning_api_enums import OpenRouterReasoningEffort
from .responses_api_engine import ResponsesAPIEngine, _audio_mime_to_format
from .stream_chunk_type import StreamChunkType

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)


class OpenAIEngine(ResponsesAPIEngine):
	"""Engine implementation for OpenAI API integration.

	Provides functionality for interacting with OpenAI's models, supporting text,
	image, speech-to-text, and text-to-speech capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.AUDIO,
		ProviderCapability.DOCUMENT,
		ProviderCapability.STT,
		ProviderCapability.TTS,
		ProviderCapability.WEB_SEARCH,
	}

	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
		"application/pdf",
		"text/plain",
		"text/csv",
		"text/tsv",
		"text/markdown",
		"text/html",
		"text/xml",
		"text/rtf",
		"application/json",
		"application/msword",
		"application/rtf",
		"application/vnd.openxmlformats-officedocument.wordprocessingml.document",
		"application/vnd.oasis.opendocument.text",
		"application/vnd.ms-excel",
		"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
		"application/vnd.ms-powerpoint",
		"application/vnd.openxmlformats-officedocument.presentationml.presentation",
		"audio/mpeg",
		"audio/wav",
		"audio/mp4",
		"audio/webm",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the OpenAI engine.

		Args:
			account: Account configuration for the OpenAI provider.
		"""
		super().__init__(account)
		self._last_used_chat_completions = False

	@cached_property
	def client(self) -> OpenAI:
		"""Creates and configures the OpenAI client.

		Returns:
			Configured OpenAI client instance.
		"""
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

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/openai.json"
	_REASONING_ONLY_IDS = frozenset({"o1", "o3", "o3-mini", "o4-mini"})
	_WEB_SEARCH_EXCLUDED_IDS = frozenset({"gpt-4.1-nano"})

	def _postprocess_models(
		self, models: list[ProviderAIModel]
	) -> list[ProviderAIModel]:
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

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""OpenAI: effort dropdown (low/medium/high). No adaptive or budget."""
		spec = super().get_reasoning_ui_spec(model)
		if not spec.show:
			return spec
		return ReasoningUISpec(
			show=True,
			show_adaptive=False,
			show_budget=False,
			show_effort=True,
			effort_options=("low", "medium", "high"),
			effort_label="Reasoning effort:",
		)

	# OpenAI TTS voices (https://platform.openai.com/docs/guides/text-to-speech)
	_AUDIO_VOICES = (
		"alloy",
		"ash",
		"ballad",
		"cedar",
		"coral",
		"echo",
		"fable",
		"marin",
		"nova",
		"onyx",
		"sage",
		"shimmer",
		"verse",
	)

	def get_audio_output_spec(
		self, model: ProviderAIModel
	) -> AudioOutputUISpec | None:
		"""OpenAI: TTS voices for audio output models."""
		if not model.audio:
			return None
		return AudioOutputUISpec(
			voices=self._AUDIO_VOICES, default_voice="alloy"
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
		params = super()._build_completion_params(
			new_block,
			conversation,
			system_message,
			stop_block_index,
			model,
			kwargs,
		)
		params["store"] = False
		if model.reasoning_capable and new_block.reasoning_mode:
			params["reasoning"] = {
				"effort": new_block.reasoning_effort
				or OpenRouterReasoningEffort.MEDIUM
			}
		return params

	def _has_audio_attachments(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None,
	) -> bool:
		"""Return True if any message contains audio attachments (any audio/* mime)."""

		def _msg_has_audio(msg: Message | None) -> bool:
			if not msg or not getattr(msg, "attachments", None):
				return False
			for att in msg.attachments:
				if att.mime_type and att.mime_type.startswith("audio/"):
					return True
			return False

		if _msg_has_audio(new_block.request):
			return True
		for i, block in enumerate(conversation.messages):
			if stop_block_index is not None and i >= stop_block_index:
				break
			if _msg_has_audio(block.request):
				return True
		return False

	def _to_chat_content_part(self, message: Message) -> list[dict[str, Any]]:
		"""Build Chat Completions content parts (text, image_url, input_audio)."""
		parts: list[dict[str, Any]] = [
			{"type": "text", "text": message.content or ""}
		]
		if not getattr(message, "attachments", None):
			return parts
		for attachment in message.attachments:
			mime = attachment.mime_type or ""
			url = attachment.url
			if mime.startswith("image/"):
				parts.append(
					{
						"type": "image_url",
						"image_url": {"url": url, "detail": "auto"},
					}
				)
			elif mime.startswith("audio/"):
				audio_format = _audio_mime_to_format(mime)
				if audio_format and url.startswith("data:"):
					_, _, data = url.partition(",")
					if data:
						parts.append(
							{
								"type": "input_audio",
								"input_audio": {
									"data": data,
									"format": audio_format,
								},
							}
						)
				else:
					raise ValueError(
						f"Audio format {mime} not supported for gpt-audio. "
						"Use mp3 or wav."
					)
		return parts

	def _get_chat_completion_messages(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None,
	) -> list[dict[str, Any]]:
		"""Build messages for Chat Completions API (supports input_audio)."""
		messages: list[dict[str, Any]] = []
		if system_message:
			messages.append(
				{"role": "system", "content": system_message.content or ""}
			)
		for i, block in enumerate(conversation.messages):
			if stop_block_index is not None and i >= stop_block_index:
				break
			if not block.response:
				continue
			messages.append(
				{
					"role": "user",
					"content": self._to_chat_content_part(block.request),
				}
			)
			messages.append(
				{
					"role": "assistant",
					"content": assistant_message_body_for_api(
						block.response.content
					),
				}
			)
		messages.append(
			{
				"role": "user",
				"content": self._to_chat_content_part(new_block.request),
			}
		)
		return messages

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs: Any,
	) -> Any:
		"""Generate completion. Uses Chat Completions API for gpt-audio + audio."""
		# Check audio routing BEFORE calling parent - parent uses Responses API
		# which does not support input_audio and would raise.
		model = self.get_model(new_block.model.model_id)
		has_audio = self._has_audio_attachments(
			new_block, conversation, system_message, stop_block_index
		)
		if has_audio and not model.audio:
			raise ValueError(
				"The selected model does not support audio input. "
				"GPT-5 and similar models do not accept audio files. "
				"Use gpt-audio or gpt-audio-mini for audio, or transcribe first (Ctrl+R)."
			)
		output_modality = getattr(new_block, "output_modality", "text")
		want_audio_output = output_modality == "audio"
		use_chat_completions = model.audio and (has_audio or want_audio_output)
		if use_chat_completions:
			self._last_used_chat_completions = True
			messages = self._get_chat_completion_messages(
				new_block, conversation, system_message, stop_block_index
			)

			params: dict[str, Any] = {
				"model": model.id,
				"messages": messages,
				"modalities": ["text", "audio"]
				if want_audio_output
				else ["text"],
				"stream": new_block.stream and not want_audio_output,
				"temperature": new_block.temperature,
				"top_p": new_block.top_p,
			}
			if want_audio_output:
				params["audio"] = {
					"voice": getattr(new_block, "audio_voice", "alloy"),
					"format": "wav",
				}
			if new_block.max_tokens:
				params["max_tokens"] = new_block.max_tokens
			params.update(self._get_block_generation_params(new_block, model))
			params["store"] = False
			params.update(kwargs)
			if want_audio_output:
				params["stream"] = False
			return self.client.chat.completions.create(**params)
		self._last_used_chat_completions = False
		return super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)

	def completion_response_with_stream(
		self,
		stream: Generator[ChatCompletionChunk, None, None] | Any,
		new_block: MessageBlock,
		**kwargs: Any,
	) -> Generator[tuple[StreamChunkType, Any], None, None]:
		"""Handle streaming response from Chat or Responses API."""
		if getattr(self, "_last_used_chat_completions", False):
			for chunk in stream:
				if not chunk.choices:
					if hasattr(chunk, "usage") and chunk.usage:
						new_block.usage = token_usage_openai_style(chunk.usage)
					continue
				delta = chunk.choices[0].delta
				if delta and delta.content:
					yield (StreamChunkType.CONTENT, delta.content)
		else:
			yield from super().completion_response_with_stream(
				stream, new_block=new_block, **kwargs
			)

	def completion_response_without_stream(
		self,
		response: ChatCompletion | Any,
		new_block: MessageBlock,
		**kwargs: Any,
	) -> MessageBlock:
		"""Handle non-streaming response from Chat or Responses API."""
		if isinstance(response, ChatCompletion):
			msg = response.choices[0].message
			audio = getattr(msg, "audio", None)
			if audio and getattr(audio, "data", None):
				fmt = getattr(audio, "format", None) or getattr(
					new_block, "audio_format", "wav"
				)
				audio_marker = _("<audio response>")
				new_block.response = Message(
					role=MessageRoleEnum.ASSISTANT,
					content=audio_marker,
					audio_data=audio.data,
					audio_format=fmt,
				)
			else:
				content = msg.content if msg.content is not None else ""
				new_block.response = Message(
					role=MessageRoleEnum.ASSISTANT, content=content
				)
			if hasattr(response, "usage") and response.usage:
				new_block.usage = token_usage_openai_style(response.usage)
			return new_block
		return super().completion_response_without_stream(
			response, new_block, **kwargs
		)

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
