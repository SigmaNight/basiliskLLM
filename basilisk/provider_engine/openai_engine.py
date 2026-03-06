"""Module for OpenAI API integration.

This module provides the OpenAIEngine class for interacting with the OpenAI API,
implementing capabilities for text, image, and audio generation/processing.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Any

from openai import OpenAI
from openai.types.responses import WebSearchToolParam

from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .responses_api_engine import ResponsesAPIEngine

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
				"effort": new_block.reasoning_effort or "medium"
			}
		return params

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
