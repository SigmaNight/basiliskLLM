"""Module for Google Gemini API integration.

This module provides the GeminiEngine class for interacting with the Google Gemini API,
implementing capabilities for text and image handling using Google's generative AI models.
"""

from __future__ import annotations

import base64
import logging
from functools import cached_property
from typing import Any, Iterator

from google import genai
from google.genai.types import (
	Content,
	GenerateContentConfig,
	GenerateContentResponse,
	GoogleSearch,
	Part,
	ThinkingConfig,
	ThinkingLevel,
	Tool,
)

from basilisk.conversation import (
	AttachmentFile,
	AttachmentFileTypes,
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.content_utils import assistant_message_body_for_api

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability
from .provider_ui_spec import (
	DEFAULT_AUDIO_VOICES,
	AudioOutputUISpec,
	ReasoningUISpec,
)
from .reasoning_api_enums import GeminiThinkingEffortKey
from .stream_chunk_type import StreamChunkType
from .usage_utils import token_usage_gemini

logger = logging.getLogger(__name__)


def _gemini_audio_mime_to_file_format(mime_type: str | None) -> str:
	"""Map Gemini / Lyria audio MIME type to a file format label (OpenAI-compatible)."""
	if not mime_type:
		return "mp3"
	lower = mime_type.lower()
	if "wav" in lower:
		return "wav"
	if "mpeg" in lower or "mp3" in lower:
		return "mp3"
	return "mp3"


class GeminiEngine(BaseEngine):
	"""Engine implementation for Google Gemini API integration.

	Provides specific functionality for interacting with Google's Gemini models,
	supporting both text and image capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text and image processing.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.AUDIO,
		ProviderCapability.DOCUMENT,
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
		ProviderCapability.WEB_SEARCH,
		ProviderCapability.VIDEO,
	}

	supported_attachment_formats: set[str] = {
		"application/pdf",
		"application/javascript",
		"audio/wav",
		"audio/mpeg",
		"audio/aac",
		"audio/ogg",
		"audio/x-aiff",
		"audio/x-flac",
		"image/png",
		"image/jpeg",
		"image/webp",
		"image/heic",
		"image/heif",
		"text/css",
		"text/csv",
		"text/html",
		"text/plain",
		"text/xml",
		"text/x-python",
		"video/avi",
		"video/mp4",
		"video/mpeg",
		"video/quicktime",
		"video/webm",
		"video/3gpp",
	}

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/google.json"

	@cached_property
	def client(self) -> genai.Client:
		"""Property to return the client object for the provider.

		Returns:
			Client object for the provider, initialized with the API key.
		"""
		return genai.Client(api_key=self.account.api_key.get_secret_value())

	def model_supports_web_search(self, model: ProviderAIModel) -> bool:
		"""Gemini supports Google Search via tools for models with tools capability."""
		return super().model_supports_web_search(model)

	def get_web_search_tool_definitions(
		self, model: ProviderAIModel
	) -> list[Tool]:
		"""Return Google Search tool for grounding."""
		return [Tool(google_search=GoogleSearch())]

	def get_audio_output_spec(
		self, model: ProviderAIModel
	) -> AudioOutputUISpec | None:
		"""Gemini: Lyria and other models that return audio via response modalities."""
		if not model.audio_output:
			return None
		return AudioOutputUISpec(
			voices=DEFAULT_AUDIO_VOICES, default_voice=DEFAULT_AUDIO_VOICES[0]
		)

	def _wants_gemini_audio_in_response(
		self, model: ProviderAIModel | None, new_block: MessageBlock
	) -> bool:
		"""Whether to request AUDIO+TEXT modalities (Lyria 3 Clip/Pro per Gemini API docs)."""
		if not model or not model.audio_output:
			return False
		model_id = (model.id or "").lower()
		if "lyria" in model_id:
			return True
		return new_block.output_modality == "audio"

	def _assistant_message_from_gemini_parts(
		self, response: GenerateContentResponse
	) -> Message:
		"""Parse Lyria-style multimodal parts (text order not guaranteed per Google docs)."""
		text_parts: list[str] = []
		audio_bytes: bytes | None = None
		audio_mime: str | None = None
		for part in getattr(response, "parts", None) or ():
			if part.text:
				text_parts.append(part.text)
			inline = part.inline_data
			if inline is not None and inline.data:
				audio_bytes = inline.data
				audio_mime = inline.mime_type
		lyrics = "\n\n".join(text_parts).strip()
		if audio_bytes:
			fmt = _gemini_audio_mime_to_file_format(audio_mime)
			audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
			return Message(
				role=MessageRoleEnum.ASSISTANT,
				content=lyrics or _("<audio response>"),
				audio_data=audio_b64,
				audio_format=fmt,
			)
		return Message(
			role=MessageRoleEnum.ASSISTANT,
			content=(response.text or lyrics or ""),
		)

	def get_reasoning_ui_spec(self, model: ProviderAIModel) -> ReasoningUISpec:
		"""Gemini: 2.5 uses thinkingBudget; 3 uses thinkingLevel (minimal/low/medium/high)."""
		spec = super().get_reasoning_ui_spec(model)
		if not spec.show:
			return spec
		model_id = (model.id or "").lower()
		if "gemini-3" in model_id:
			return ReasoningUISpec(
				show=True,
				show_adaptive=False,
				show_budget=False,
				show_effort=True,
				effort_options=("minimal", "low", "medium", "high"),
				effort_label="Thinking level:",
			)
		# Gemini 2.5: thinkingBudget 0-24576 (Flash) or 128-32768 (Pro); -1=dynamic
		return ReasoningUISpec(
			show=True,
			show_adaptive=False,
			show_budget=True,
			show_effort=False,
			budget_default=8192,
			budget_max=32768,
		)

	def convert_role(self, role: MessageRoleEnum) -> str:
		"""Converts internal role enum to Gemini API role string.

		Args:
			role: Internal message role enum value.

		Returns:
			String representation of the role for Gemini API.

		Raises:
			NotImplementedError: If system role is used (not supported by Gemini).
		"""
		if role == MessageRoleEnum.ASSISTANT:
			return "model"
		elif role == MessageRoleEnum.USER:
			return "user"
		elif role == MessageRoleEnum.SYSTEM:
			raise NotImplementedError(
				"System role must be set on the model instance"
			)

	def convert_attachment(self, attachment: AttachmentFile) -> Part:
		"""Converts internal attachment representation to Gemini 'part'.

		Args:
			attachment: Internal attachment object.

		Returns:
			Gemini API compatible content part.

		Raises:
			ValueError: If the attachment type is not supported.
		"""
		if not attachment.mime_type:
			raise ValueError("Attachment mime type is not set")
		if attachment.type == AttachmentFileTypes.URL:
			return Part.from_uri(
				file_uri=attachment.url, mime_type=attachment.mime_type
			)
		with attachment.send_location.open("rb") as f:
			return Part.from_bytes(
				mime_type=attachment.mime_type, data=f.read()
			)

	def convert_message_content(self, message: Message) -> Content:
		"""Converts internal message to Gemini API content format.

		Args:
			message: Internal message object.

		Returns:
			Gemini API compatible content object.
		"""
		role = self.convert_role(message.role)
		text = message.content or ""
		if message.role == MessageRoleEnum.ASSISTANT:
			text = assistant_message_body_for_api(text)
		parts = [Part(text=text)]
		if message.attachments:
			for attachment in message.attachments:
				parts.append(self.convert_attachment(attachment))
		return Content(role=role, parts=parts)

	# Implement abstract methods from BaseEngine with the same method for request and response
	prepare_message_request = convert_message_content
	prepare_message_response = convert_message_content

	def _build_thinking_config(
		self, model: ProviderAIModel | None, new_block: MessageBlock
	) -> ThinkingConfig | None:
		"""Build ThinkingConfig for Gemini 2.5 (thinking_budget) or 3 (thinking_level).

		Gemini 2.5 uses thinking_budget (tokens, -1=auto); Gemini 3 uses thinking_level.
		Only add config when reasoning_mode is on and model supports it.
		"""
		if (
			not model
			or not model.reasoning_capable
			or not new_block.reasoning_mode
		):
			return None
		model_id = (model.id or "").lower()
		if "gemini-3" in model_id:
			effort_raw = (
				new_block.reasoning_effort or GeminiThinkingEffortKey.HIGH.value
			).lower()
			level_map = {
				GeminiThinkingEffortKey.MINIMAL: "minimal",
				GeminiThinkingEffortKey.LOW: ThinkingLevel.LOW,
				GeminiThinkingEffortKey.MEDIUM: ThinkingLevel.MEDIUM,
				GeminiThinkingEffortKey.HIGH: ThinkingLevel.HIGH,
			}
			try:
				ek = GeminiThinkingEffortKey(effort_raw)
			except ValueError:
				thinking_level = ThinkingLevel.HIGH
			else:
				thinking_level = level_map.get(ek, ThinkingLevel.HIGH)
			return ThinkingConfig(thinking_level=thinking_level)
		# Gemini 2.5: thinking_budget (tokens). -1 = auto/dynamic per API.
		budget = new_block.reasoning_budget_tokens
		if budget is None:
			budget = -1
		return ThinkingConfig(thinking_budget=budget)

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> GenerateContentResponse | Iterator[GenerateContentResponse]:
		"""Generates a completion response using the Gemini AI model with specified configuration.

		Processes a message block and conversation to generate AI-generated content through the Gemini API. Configures the generative model with optional system instructions, generation parameters, and streaming preferences.

		Args:
			new_block: Configuration block containing message request, model and other generation settings
			conversation: The current conversation context (past message request and response)
			system_message: Optional system-level instruction message
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			The generated content response from the Gemini model
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model = self.get_model(new_block.model.model_id)
		want_audio_response = self._wants_gemini_audio_in_response(
			model, new_block
		)
		tools = None
		web_search = kwargs.pop("web_search_mode", False)
		if web_search and model and self.model_supports_web_search(model):
			tools = self.get_web_search_tool_definitions(model)

		thinking_config = (
			None
			if want_audio_response
			else self._build_thinking_config(model, new_block)
		)

		config_kw: dict[str, Any] = {
			"system_instruction": system_message.content
			if system_message
			else None,
			"max_output_tokens": new_block.max_tokens
			if new_block.max_tokens
			else None,
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
			"tools": tools,
			"thinking_config": thinking_config,
		}
		gen_params = self._get_block_generation_params(new_block, model)
		if "top_k" in gen_params:
			config_kw["top_k"] = gen_params["top_k"]
		if "seed" in gen_params:
			config_kw["seed"] = gen_params["seed"]
		if "stop" in gen_params:
			config_kw["stop_sequences"] = gen_params["stop"]
		if want_audio_response:
			# https://ai.google.dev/gemini-api/docs/music-generation — Lyria 3
			# requires AUDIO + TEXT so lyrics/structure can accompany audio.
			config_kw["response_modalities"] = ["AUDIO", "TEXT"]
		config = GenerateContentConfig(**config_kw)

		generate_kwargs = {
			"model": new_block.model.model_id,
			"config": config,
			"contents": self.get_messages(
				new_block, conversation, stop_block_index=stop_block_index
			),
		}
		use_stream = new_block.stream and not want_audio_response
		if use_stream:
			return self.client.models.generate_content_stream(**generate_kwargs)
		return self.client.models.generate_content(**generate_kwargs)

	def completion_response_without_stream(
		self,
		response: GenerateContentResponse,
		new_block: MessageBlock,
		**kwargs,
	) -> MessageBlock:
		"""Handle completion response without stream.

		Args:
			response: Response from the provider
			new_block: Configuration block containing message request and model
			**kwargs: Additional keyword arguments for flexible configuration

		Returns:
			Message block containing the response content
		"""
		model = self.get_model(new_block.model.model_id)
		if self._wants_gemini_audio_in_response(model, new_block):
			new_block.response = self._assistant_message_from_gemini_parts(
				response
			)
		else:
			new_block.response = Message(
				role=MessageRoleEnum.ASSISTANT, content=response.text or ""
			)
		if hasattr(response, "usage_metadata") and response.usage_metadata:
			new_block.usage = token_usage_gemini(response.usage_metadata)
		return new_block

	def completion_response_with_stream(
		self,
		stream: Iterator[GenerateContentResponse],
		new_block: MessageBlock,
		**kwargs,
	) -> Iterator[tuple[str, Any]]:
		"""Handle completion response with stream.

		Args:
			stream: Stream response from the provider
			new_block: Block to set usage on when available
			**kwargs: Additional keyword arguments for flexible configuration.

		Returns:
			Stream response from the provider
		"""
		for chunk in stream:
			chunk_text = chunk.text
			if chunk_text:
				yield (StreamChunkType.CONTENT, chunk_text)
			if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
				new_block.usage = token_usage_gemini(chunk.usage_metadata)
