"""Base module for AI provider engines.

This module defines the abstract base class for all AI provider engines,
establishing the common interface and shared functionality.
"""

from __future__ import annotations

import logging
import threading
import time
from abc import ABC, abstractmethod
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Optional

import basilisk.config as config
from basilisk.consts import APP_NAME, APP_SOURCE_URL
from basilisk.conversation import Conversation, Message, MessageBlock
from basilisk.model_catalog_sampling import (
	strip_disallowed_completion_dict_params,
)
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.provider_engine.dynamic_model_loader import load_models_from_url
from basilisk.provider_engine.engine_model_list_cache import (
	STALE_TTL_MULTIPLIER,
	delete_model_list_disk_cache_file,
	model_list_disk_cache_path,
	prune_model_list_cache_dir,
	read_model_list_disk_cache,
	write_model_list_disk_cache,
)

if TYPE_CHECKING:
	from basilisk.config import Account

log = logging.getLogger(__name__)


class BaseEngine(ABC):
	"""Abstract base class for AI provider engines.

	Defines the interface that all provider-specific engines must implement,
	providing common functionality and type definitions.

	Attributes:
		capabilities: Set of supported provider capabilities.
		supported_attachment_formats: Set of MIME types for supported attachments.
		catalog_strip_candidate_keys: Top-level client kwargs subject to catalog
			stripping; ``None`` means do not strip (e.g. Ollama).
	"""

	capabilities: set[ProviderCapability] = set()
	supported_attachment_formats: set[str] = set()
	MODELS_JSON_URL: str | None = None
	catalog_strip_candidate_keys: ClassVar[frozenset[str] | None] = None

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
		self._models_refresh_cv = threading.Condition(self._models_cache_lock)
		self._models_refresh_in_progress = False

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
		return ttl_seconds * STALE_TTL_MULTIPLIER

	@cached_property
	def _models_cache_file_path(self) -> Path:
		"""Return persistent cache file path for this engine/account."""
		return model_list_disk_cache_path(
			account_id=str(self.account.id),
			provider_id=str(self.account.provider.id),
			custom_base_url=(
				str(self.account.custom_base_url)
				if self.account.custom_base_url is not None
				else None
			),
			engine_cls_name=self.__class__.__name__,
			models_json_url=self.MODELS_JSON_URL,
		)

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
		write_model_list_disk_cache(
			self._models_cache_file_path,
			str(self.account.id),
			models,
			cached_at,
		)

	def _read_models_disk_cache(
		self,
		now: float,
		ttl_seconds: int,
		allow_stale: bool = False,
		max_stale_seconds: int | None = None,
	) -> tuple[list[ProviderAIModel], float] | None:
		"""Read model cache payload from disk when valid for current TTL."""
		return read_model_list_disk_cache(
			self._models_cache_file_path,
			cache_kind_label=self.__class__.__name__,
			now=now,
			ttl_seconds=ttl_seconds,
			allow_stale=allow_stale,
			max_stale_seconds=max_stale_seconds,
		)

	def _prune_models_cache_dir(self, now: float, ttl_seconds: int) -> None:
		"""Periodically remove obsolete cache files to limit file growth."""
		prune_model_list_cache_dir(
			now=now,
			max_stale_seconds=self._get_models_cache_max_stale_seconds(
				ttl_seconds
			),
		)

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

		def _ram_ttl_ok() -> bool:
			return (
				self._models_cache is not None
				and self._models_cached_at is not None
				and now - self._models_cached_at < ttl_seconds
			)

		with self._models_refresh_cv:
			if _ram_ttl_ok():
				log.debug(
					"Using models from RAM cache for %s",
					self.__class__.__name__,
				)
				return self._models_cache
			while self._models_refresh_in_progress:
				self._models_refresh_cv.wait()
			if _ram_ttl_ok():
				log.debug(
					"Using models from RAM cache for %s",
					self.__class__.__name__,
				)
				return self._models_cache
			self._models_refresh_in_progress = True

		# Disk/network refresh runs without holding the condition lock so
		# invalidate_models_cache() can interleave; disk writes are atomic
		# and invalidate only removes the matching cache file for this engine.
		try:
			disk_cache = self._read_models_disk_cache(now, ttl_seconds)
			if disk_cache is not None:
				models, cached_at = disk_cache
				with self._models_refresh_cv:
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
				except (OSError, TypeError, ValueError) as write_exc:
					log.warning(
						"Failed writing models disk cache: %s", write_exc
					)
			except Exception as exc:
				log.warning(
					"Failed to refresh models for %s: %s",
					self.__class__.__name__,
					exc,
				)
				with self._models_refresh_cv:
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
					with self._models_refresh_cv:
						self._set_models_ram_cache(models, cached_at)
						log.debug(
							"Using stale models from disk cache fallback for %s",
							self.__class__.__name__,
						)
						return self._models_cache
				with self._models_refresh_cv:
					return []
			with self._models_refresh_cv:
				self._set_models_ram_cache(models, now)
				self._models_last_error = None
				return self._models_cache
		finally:
			with self._models_refresh_cv:
				self._models_refresh_in_progress = False
				self._models_refresh_cv.notify_all()

	def get_model(self, model_id: str) -> Optional[ProviderAIModel]:
		"""Retrieves a specific model by its ID.

		Args:
			model_id: Identifier of the model to retrieve.

		Returns:
			The requested model if found, None otherwise.

		Raises:
			ValueError: If multiple models are found with the same ID.
		"""
		found: ProviderAIModel | None = None
		for model in self.models:
			if model.id == model_id:
				if found is not None:
					raise ValueError(f"Multiple models with id {model_id}")
				found = model
		return found

	def _strip_catalog_sampling_params(
		self, model: ProviderAIModel | None, params: dict[str, Any]
	) -> None:
		"""Drop sampling kwargs rejected by catalog metadata for this model."""
		keys = type(self).catalog_strip_candidate_keys
		if keys is None:
			return
		strip_disallowed_completion_dict_params(
			model, params, regulated_keys=keys
		)

	def get_model_loading_error(self) -> str | None:
		"""Return the latest model-loading error for this engine."""
		return self._models_last_error

	def invalidate_models_cache(self) -> None:
		"""Clear the cached model list so the next access reloads it."""
		with self._models_refresh_cv:
			self._models_cache = None
			self._models_cached_at = None
			self._models_last_error = None
			delete_model_list_disk_cache_file(self._models_cache_file_path)

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
		"""Get a user agent string for the application."""
		return f"{APP_NAME} ({APP_SOURCE_URL})"

	def get_transcription(self, *args, **kwargs) -> str:
		"""Get transcription from audio file."""
		raise NotImplementedError(
			"Transcription not implemented for this engine"
		)
