"""Base module for AI provider engines.

This module defines the abstract base class for all AI provider engines,
establishing the common interface and shared functionality.
"""

from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import asdict
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

import basilisk.config as config
from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.provider_engine.dynamic_model_loader import load_models_from_url
from basilisk.provider_engine.model_cache_registry import (
	get_models_cache_dir,
	get_registry_filename,
	prune_model_cache_registry,
	register_model_cache_file,
	remove_cache_file_from_registry,
	write_json_atomic,
)

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)
_MODELS_CACHE_PAYLOAD_VERSION = 1
_CACHE_PRUNE_INTERVAL_SECONDS = 3600
_CACHE_STALE_MULTIPLIER = 7


class BaseEngine(ABC):
	"""Abstract base class for AI provider engines.

	Defines the interface that all provider-specific engines must implement,
	providing common functionality and type definitions.

	Attributes:
		capabilities: Set of supported provider capabilities.
		supported_attachment_formats: Set of MIME types for supported attachments.
	"""

	capabilities: set[ProviderCapability] = set()
	supported_attachment_formats: set[str] = set()
	MODELS_JSON_URL: str | None = None
	_last_cache_prune_at: float = 0.0
	_cache_prune_lock = threading.Lock()

	def __init__(self, account: Account) -> None:
		"""Initializes the engine with the given account.

		Args:
		account: The provider account configuration.
		"""
		self.account = account
		self._models_cache: list[ProviderAIModel] | None = None
		self._models_cached_at: float | None = None
		self._models_last_error: str | None = None
		self._models_cache_lock = threading.Lock()

	@cached_property
	@abstractmethod
	def client(self):
		"""Property to return the provider client object."""
		pass

	def _postprocess_models(
		self, models: list[ProviderAIModel]
	) -> list[ProviderAIModel]:
		"""Hook to adjust dynamically loaded models for provider-specific parity."""
		return models

	def _load_models(self) -> list[ProviderAIModel]:
		"""Load provider models without applying engine-level cache."""
		if not self.MODELS_JSON_URL:
			raise NotImplementedError(
				f"{self.__class__.__name__} must override models or set MODELS_JSON_URL"
			)
		return self._postprocess_models(
			load_models_from_url(self.MODELS_JSON_URL)
		)

	def _get_models_cache_ttl_seconds(self) -> int:
		"""Return model-list cache TTL in seconds from configuration."""
		return config.conf().general.model_metadata_cache_ttl_seconds

	def _get_models_cache_max_stale_seconds(self, ttl_seconds: int) -> int:
		"""Return max age allowed for stale cache fallback."""
		return ttl_seconds * _CACHE_STALE_MULTIPLIER

	@cached_property
	def _models_cache_file_path(self) -> Path:
		"""Return persistent cache file path for this engine/account."""
		cache_key_payload = {
			"account_id": str(self.account.id),
			"provider_id": str(self.account.provider.id),
			"base_url": (
				str(self.account.custom_base_url)
				if self.account.custom_base_url is not None
				else None
			),
			"engine_cls": self.__class__.__name__,
			"models_json_url": self.MODELS_JSON_URL,
		}
		cache_key = hashlib.sha256(
			json.dumps(cache_key_payload, sort_keys=True).encode("utf-8")
		).hexdigest()
		cache_dir = get_models_cache_dir()
		return cache_dir / f"{cache_key}.json"

	def _set_models_ram_cache(
		self, models: list[ProviderAIModel], cached_at: float
	) -> list[ProviderAIModel]:
		"""Store models in RAM cache and return the stored list."""
		self._models_cache = models
		self._models_cached_at = cached_at
		return self._models_cache

	def _write_models_disk_cache(
		self, models: list[ProviderAIModel], cached_at: float
	) -> None:
		"""Persist model cache payload to disk."""
		cache_file = self._models_cache_file_path
		payload = {
			"version": _MODELS_CACHE_PAYLOAD_VERSION,
			"cached_at": cached_at,
			"models": [asdict(model) for model in models],
		}
		write_json_atomic(cache_file, payload)
		register_model_cache_file(str(self.account.id), cache_file)

	def _delete_cache_file(self, cache_file: Path) -> None:
		"""Delete one cache file, logging only on failure."""
		try:
			cache_file.unlink(missing_ok=True)
		except OSError:
			log.debug("Could not delete models cache file %s", cache_file)
		remove_cache_file_from_registry(cache_file.name)

	def _read_models_disk_cache(
		self,
		now: float,
		ttl_seconds: int,
		allow_stale: bool = False,
		max_stale_seconds: int | None = None,
	) -> tuple[list[ProviderAIModel], float] | None:
		"""Read model cache payload from disk when valid for current TTL."""
		cache_file = self._models_cache_file_path
		if not cache_file.exists():
			return None
		try:
			payload = json.loads(cache_file.read_text(encoding="utf-8"))
			if not isinstance(payload, dict):
				raise TypeError("invalid cache payload")
			if payload.get("version") != _MODELS_CACHE_PAYLOAD_VERSION:
				raise ValueError("unsupported cache payload version")
			cached_at = float(payload["cached_at"])
			cache_age_seconds = now - cached_at
			if not allow_stale and cache_age_seconds >= ttl_seconds:
				log.debug(
					"Models disk cache expired for %s (age=%.1fs, ttl=%ss)",
					self.__class__.__name__,
					cache_age_seconds,
					ttl_seconds,
				)
				return None
			if (
				allow_stale
				and max_stale_seconds is not None
				and cache_age_seconds >= max_stale_seconds
			):
				log.debug(
					"Models stale disk cache exceeded retention for %s (age=%.1fs, max_stale=%ss)",
					self.__class__.__name__,
					cache_age_seconds,
					max_stale_seconds,
				)
				self._delete_cache_file(cache_file)
				return None
			model_rows = payload.get("models")
			if not isinstance(model_rows, list):
				raise TypeError("invalid models cache payload")
			models = [ProviderAIModel(**x) for x in model_rows]
			return models, cached_at
		except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
			log.warning("Failed reading models disk cache: %s", exc)
			self._delete_cache_file(cache_file)
			return None

	def _prune_models_cache_dir(self, now: float, ttl_seconds: int) -> None:
		"""Periodically remove obsolete cache files to limit file growth."""
		last_prune_at = BaseEngine._last_cache_prune_at
		if (
			last_prune_at > 0
			and now - last_prune_at < _CACHE_PRUNE_INTERVAL_SECONDS
		):
			return
		with BaseEngine._cache_prune_lock:
			last_prune_at = BaseEngine._last_cache_prune_at
			if (
				last_prune_at > 0
				and now - last_prune_at < _CACHE_PRUNE_INTERVAL_SECONDS
			):
				return
			BaseEngine._last_cache_prune_at = now
		prune_model_cache_registry()
		cache_dir = get_models_cache_dir()
		if not cache_dir.exists():
			return
		max_stale_seconds = self._get_models_cache_max_stale_seconds(
			ttl_seconds
		)
		for cache_file in cache_dir.glob("*.json"):
			if cache_file.name == get_registry_filename():
				continue
			try:
				payload = json.loads(cache_file.read_text(encoding="utf-8"))
				cached_at = float(payload["cached_at"])
				version = payload.get("version")
				if version != _MODELS_CACHE_PAYLOAD_VERSION:
					self._delete_cache_file(cache_file)
					continue
				if now - cached_at >= max_stale_seconds:
					self._delete_cache_file(cache_file)
			except (
				OSError,
				json.JSONDecodeError,
				KeyError,
				TypeError,
				ValueError,
			):
				self._delete_cache_file(cache_file)

	@property
	def models(self) -> list[ProviderAIModel]:
		"""Get models available for the provider.

		Returns:
			List of supported provider models with their configurations.
		"""
		now = time.time()
		ttl_seconds = self._get_models_cache_ttl_seconds()
		max_stale_seconds = self._get_models_cache_max_stale_seconds(
			ttl_seconds
		)
		self._prune_models_cache_dir(now, ttl_seconds)
		with self._models_cache_lock:
			if (
				self._models_cache is not None
				and self._models_cached_at is not None
				and now - self._models_cached_at < ttl_seconds
			):
				log.debug(
					"Using models from RAM cache for %s",
					self.__class__.__name__,
				)
				return self._models_cache
		disk_cache = self._read_models_disk_cache(now, ttl_seconds)
		if disk_cache is not None:
			models, cached_at = disk_cache
			with self._models_cache_lock:
				self._set_models_ram_cache(models, cached_at)
				self._models_last_error = None
				log.debug(
					"Using models from disk cache for %s",
					self.__class__.__name__,
				)
				return self._models_cache
		try:
			log.debug(
				"Loading models from provider source for %s",
				self.__class__.__name__,
			)
			models = self._load_models()
			try:
				self._write_models_disk_cache(models, now)
			except OSError as write_exc:
				log.warning("Failed writing models disk cache: %s", write_exc)
		except Exception as exc:
			log.warning(
				"Failed to refresh models for %s: %s",
				self.__class__.__name__,
				exc,
			)
			with self._models_cache_lock:
				self._models_last_error = str(exc)
				if self._models_cache is not None:
					return self._models_cache
			stale_disk_cache = self._read_models_disk_cache(
				now,
				ttl_seconds,
				allow_stale=True,
				max_stale_seconds=max_stale_seconds,
			)
			if stale_disk_cache is not None:
				models, cached_at = stale_disk_cache
				with self._models_cache_lock:
					self._set_models_ram_cache(models, cached_at)
					log.debug(
						"Using stale models from disk cache fallback for %s",
						self.__class__.__name__,
					)
					return self._models_cache
			return []
		with self._models_cache_lock:
			self._set_models_ram_cache(models, now)
			self._models_last_error = None
			return self._models_cache

	def get_model(self, model_id: str) -> Optional[ProviderAIModel]:
		"""Retrieves a specific model by its ID.

		Args:
			model_id: Identifier of the model to retrieve.

		Returns:
			The requested model if found, None otherwise.

		Raises:
			ValueError: If multiple models are found with the same ID.
		"""
		model_list = [model for model in self.models if model.id == model_id]
		if not model_list:
			return None
		if len(model_list) > 1:
			raise ValueError(f"Multiple models with id {model_id}")
		return model_list[0]

	def get_model_loading_error(self) -> str | None:
		"""Return the latest model-loading error for this engine."""
		return self._models_last_error

	def invalidate_models_cache(self) -> None:
		"""Clear the cached model list so the next access reloads it."""
		with self._models_cache_lock:
			self._models_cache = None
			self._models_cached_at = None
			self._models_last_error = None
		self._delete_cache_file(self._models_cache_file_path)

	@abstractmethod
	def prepare_message_request(self, message: Message) -> Any:
		"""Prepare message request for provider API.

		Args:
			message: The message to prepare.

		Returns:
			The prepared message in provider-specific format.
		"""
		if not isinstance(message, Message) or message.attachments is None:
			return
		for attachment in message.attachments:
			if attachment.mime_type not in self.supported_attachment_formats:
				raise ValueError(
					f"Unsupported attachment format: {attachment.mime_type}"
				)

	@abstractmethod
	def prepare_message_response(self, response: Any) -> Message:
		"""Prepare message response.

		Args:
			response: The response to prepare.

		Returns:
			The prepared response in Message format.
		"""
		pass

	def get_messages(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None = None,
		stop_block_index: int | None = None,
	) -> list[Message]:
		"""Prepares message history for API requests.

		Args:
			new_block: Current message block being processed.
			conversation: Full conversation history.
			system_message: Optional system-level instruction message.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.

		Returns:
			List of prepared messages in provider-specific format.
		"""
		messages = []
		if system_message:
			messages.append(self.prepare_message_request(system_message))
		for i, block in enumerate(conversation.messages):
			if stop_block_index is not None and i >= stop_block_index:
				break
			if not block.response:
				continue
			messages.extend(
				[
					self.prepare_message_request(block.request),
					self.prepare_message_response(block.response),
				]
			)
		messages.append(self.prepare_message_request(new_block.request))
		return messages

	@abstractmethod
	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs: dict[str, Any],
	) -> Any:
		"""Generates a completion response.

		Processes a message block and conversation to generate AI-generated content.
		Configures the generative model with optional system instructions, generation parameters, and streaming preferences.

		Args:
			new_block: Configuration block containing model ,message request and other generation settings.
			conversation: The current conversation context (paste message request and response).
			system_message: Optional system-level instruction message.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for flexible configuration.

		Returns:
			The generated content response from the provider.
		"""
		pass

	@abstractmethod
	def completion_response_with_stream(self, stream: Any, **kwargs) -> Any:
		"""Handle completion response with stream.

		Args:
			stream: Stream response from the provider.
			**kwargs: Additional keyword arguments for flexible configuration.

		Returns:
			Stream response from the provider.
		"""
		pass

	@abstractmethod
	def completion_response_without_stream(
		self, response: Any, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Handle completion response without stream.

		TODO: unify reasoning/thinking handling across providers so reasoning
		traces are modeled as provider-agnostic metadata (not mixed into plain
		response content), with a UI toggle to show/hide reasoning output.
		"""
		pass

	@staticmethod
	def get_user_agent() -> str:
		"""Get a user agent sting for the application."""
		return f"{APP_NAME} ({APP_SOURCE_URL})"

	def get_transcription(self, *args, **kwargs) -> str:
		"""Get transcription from audio file."""
		raise NotImplementedError(
			"Transcription not implemented for this engine"
		)
