"""OpenCode Go subscription API integration."""

from __future__ import annotations

import enum
import logging
from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Any

import httpx
from anthropic import Anthropic
from google import genai
from google.genai.types import HttpOptions

from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability

from .anthropic_engine import AnthropicEngine
from .gemini_engine import GeminiEngine
from .legacy_openai_engine import LegacyOpenAIEngine
from .openai_engine import OpenAIEngine

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)


class _Protocol(enum.Enum):
	CHAT_COMPLETIONS = enum.auto()
	RESPONSES = enum.auto()
	ANTHROPIC_MESSAGES = enum.auto()
	GEMINI = enum.auto()


@dataclass(frozen=True)
class _ProtocolResponse:
	protocol: _Protocol
	value: Any


# OpenCode Go exposes models through different API protocols. Keep these maps
# aligned with https://opencode.ai/docs/go/#endpoints. Newly added models use
# chat completions until their protocol is documented here.
_RESPONSES_MODELS = frozenset(
	{"grok-4.5", "gpt-5.6-luna", "muse-spark-1.2-contributor"}
)
_ANTHROPIC_MODELS = frozenset(
	{
		"minimax-m3",
		"minimax-m2.7",
		"minimax-m2.5",
		"qwen3.8-max",
		"qwen3.7-max",
		"qwen3.7-plus",
		"qwen3.6-plus",
	}
)
_VISION_MODELS = frozenset(
	{
		"deepseek-v4-flash-vision-exp",
		"kimi-k2.7-code",
		"mimo-v2.5",
		"qwen3.7-plus",
	}
)


class _SharedModelsMixin:
	"""Use the parent OpenCode engine's discovered model list."""

	def __init__(self, account: Account, model_source: _OpenCodeEngine):
		self._model_source = model_source
		super().__init__(account)

	@property
	def models(self) -> list[ProviderAIModel]:
		return self._model_source.models


class _OpenCodeResponsesEngine(_SharedModelsMixin, OpenAIEngine):
	"""OpenAI Responses adapter sharing the OpenCode model catalog."""


class _OpenCodeAnthropicEngine(_SharedModelsMixin, AnthropicEngine):
	"""Anthropic Messages adapter sharing the OpenCode model catalog."""

	@cached_property
	def client(self) -> Anthropic:
		base_url = str(self.account.provider.base_url).rstrip("/")
		return Anthropic(
			api_key=self.account.api_key.get_secret_value(),
			base_url=base_url.removesuffix("/v1"),
		)


class _OpenCodeGeminiEngine(_SharedModelsMixin, GeminiEngine):
	"""Gemini adapter sharing the OpenCode model catalog."""

	@cached_property
	def client(self) -> genai.Client:
		return genai.Client(
			api_key=self.account.api_key.get_secret_value(),
			http_options=HttpOptions(
				base_url=str(self.account.provider.base_url).rstrip("/")
			),
		)


class _OpenCodeEngine(LegacyOpenAIEngine):
	"""Route OpenCode models to their documented API protocol."""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
	}
	VISION_MODELS = _VISION_MODELS

	@cached_property
	def _responses_engine(self) -> _OpenCodeResponsesEngine:
		return _OpenCodeResponsesEngine(self.account, self)

	@cached_property
	def _anthropic_engine(self) -> _OpenCodeAnthropicEngine:
		return _OpenCodeAnthropicEngine(self.account, self)

	@cached_property
	def _gemini_engine(self) -> _OpenCodeGeminiEngine:
		return _OpenCodeGeminiEngine(self.account, self)

	def _load_models(self) -> list[ProviderAIModel]:
		"""Fetch the models currently available from this provider."""
		url = f"{str(self.account.provider.base_url).rstrip('/')}/models"
		response = httpx.get(
			url,
			headers={
				"Authorization": (
					f"Bearer {self.account.api_key.get_secret_value()}"
				),
				"User-Agent": self.get_user_agent(),
			},
			timeout=30.0,
		)
		if response.status_code != 200:
			raise httpx.HTTPStatusError(
				(
					f"Failed to get models from '{url}' "
					f"(status={response.status_code}): {response.text}"
				),
				request=response.request,
				response=response,
			)
		data = response.json()
		rows = data.get("data", [])
		if not isinstance(rows, list):
			raise ValueError("OpenCode returned an invalid model list")

		models = []
		for row in rows:
			if not isinstance(row, dict):
				continue
			model_id = row.get("id")
			if not isinstance(model_id, str) or not model_id:
				continue
			created = row.get("created", 0)
			if not isinstance(created, int):
				created = 0
			models.append(
				ProviderAIModel(
					id=model_id,
					description=_(
						"Model available from this OpenCode provider."
					),
					max_output_tokens=8192,
					vision=model_id in self.VISION_MODELS,
					created=created,
					extra_info={"owned_by": row.get("owned_by")},
				)
			)
		return models

	@staticmethod
	def _protocol_for_model(model_id: str) -> _Protocol:
		if model_id in _RESPONSES_MODELS:
			return _Protocol.RESPONSES
		if model_id in _ANTHROPIC_MODELS:
			return _Protocol.ANTHROPIC_MESSAGES
		return _Protocol.CHAT_COMPLETIONS

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> _ProtocolResponse:
		"""Create a completion with the model's required protocol."""
		protocol = self._protocol_for_model(new_block.model.model_id)
		if protocol == _Protocol.RESPONSES:
			value = self._responses_engine.completion(
				new_block,
				conversation,
				system_message,
				stop_block_index,
				**kwargs,
			)
		elif protocol == _Protocol.ANTHROPIC_MESSAGES:
			value = self._anthropic_engine.completion(
				new_block,
				conversation,
				system_message,
				stop_block_index,
				**kwargs,
			)
		elif protocol == _Protocol.GEMINI:
			value = self._gemini_engine.completion(
				new_block,
				conversation,
				system_message,
				stop_block_index,
				**kwargs,
			)
		else:
			value = super().completion(
				new_block,
				conversation,
				system_message,
				stop_block_index,
				**kwargs,
			)
		return _ProtocolResponse(protocol=protocol, value=value)

	def completion_response_with_stream(self, stream: _ProtocolResponse):
		"""Yield response text using the selected protocol adapter."""
		if stream.protocol == _Protocol.RESPONSES:
			return self._responses_engine.completion_response_with_stream(
				stream.value
			)
		if stream.protocol == _Protocol.ANTHROPIC_MESSAGES:
			return self._anthropic_engine.completion_response_with_stream(
				stream.value
			)
		if stream.protocol == _Protocol.GEMINI:
			return self._gemini_engine.completion_response_with_stream(
				stream.value
			)
		return super().completion_response_with_stream(stream.value)

	def cancel_completion(self, response: _ProtocolResponse) -> None:
		"""Cancel the active stream for every OpenCode protocol."""
		if response.protocol == _Protocol.GEMINI:
			# A running Google Gen AI generator raises ``ValueError`` when its
			# ``close`` method is called from another thread. Closing the client
			# interrupts the HTTP stream; removing the cached client lets the next
			# request create a fresh connection pool.
			try:
				super().cancel_completion(response.value)
			except ValueError:
				pass
			client = self._gemini_engine.__dict__.pop("client", None)
			if client is not None:
				client.close()
			return
		super().cancel_completion(response.value)

	def completion_response_without_stream(
		self, response: _ProtocolResponse, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Process a complete response with the selected adapter."""
		if response.protocol == _Protocol.RESPONSES:
			return self._responses_engine.completion_response_without_stream(
				response.value, new_block, **kwargs
			)
		if response.protocol == _Protocol.ANTHROPIC_MESSAGES:
			return self._anthropic_engine.completion_response_without_stream(
				response.value, new_block, **kwargs
			)
		if response.protocol == _Protocol.GEMINI:
			return self._gemini_engine.completion_response_without_stream(
				response.value, new_block, **kwargs
			)
		return super().completion_response_without_stream(
			response.value, new_block, **kwargs
		)


class OpenCodeGoEngine(_OpenCodeEngine):
	"""OpenCode Go subscription engine."""


class OpenCodeZenEngine(_OpenCodeEngine):
	"""OpenCode Zen pay-as-you-go engine."""

	VISION_MODELS = frozenset(
		{
			"gemini-3.7-flash",
			"gemini-3.6-flash",
			"gemini-3.5-flash",
			"gemini-3.5-flash-lite",
			"gemini-3.1-pro",
			"gemini-3-flash",
			"kimi-k2.7-code",
			"qwen3.7-plus",
		}
	)

	@staticmethod
	def _protocol_for_model(model_id: str) -> _Protocol:
		if model_id.startswith("gemini-"):
			return _Protocol.GEMINI
		if model_id.startswith(("claude-", "qwen")):
			return _Protocol.ANTHROPIC_MESSAGES
		if model_id.startswith(("gpt-", "grok-", "muse-")):
			return _Protocol.RESPONSES
		return _Protocol.CHAT_COMPLETIONS
