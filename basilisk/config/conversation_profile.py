"""fodule for managing conversational profile configurations."""

from __future__ import annotations

import logging
from functools import cache, cached_property
from typing import Any, Iterable, Optional
from uuid import UUID, uuid4

from pydantic import (
	UUID4,
	BaseModel,
	ConfigDict,
	Field,
	OnErrorOmit,
	field_validator,
	model_validator,
)

from basilisk.provider import Provider
from basilisk.provider_ai_model import AIModelInfo

from .account_config import Account, AccountInfo, get_account_config
from .config_helper import (
	BasiliskBaseSettings,
	get_settings_config_dict,
	save_config_file,
)

log = logging.getLogger(__name__)


class ConversationProfile(BaseModel):
	"""A configuration model for a conversation profile."""

	model_config = ConfigDict(revalidate_instances="always")
	id: UUID4 = Field(default_factory=uuid4)
	name: str
	system_prompt: str = Field(default="")
	account_info: Optional[AccountInfo] = Field(default=None)
	ai_model_info: Optional[AIModelInfo] = Field(default=None)
	max_tokens: Optional[int] = Field(default=None)
	temperature: Optional[float] = Field(default=None)
	top_p: Optional[float] = Field(default=None)
	stream_mode: bool = Field(default=True)

	def __init__(self, **data: Any):
		"""Initialize a conversation profile with the provided data.

		Attempts to create a conversation profile by calling the parent class's initializer with the given data.

		Args:
			data: Keyword arguments containing configuration details for the conversation profile.

		Raises:
			Exception: If initialization fails, logs an error and re-raises the original exception,
			preventing the profile from being accessible.
		"""
		try:
			super().__init__(**data)
		except Exception as e:
			log.error(
				"Error in conversation profile '%s' the profile will not be accessible",
				data.get("name", "unknown"),
				exc_info=e,
			)
			raise e

	@field_validator("ai_model_info", mode="before")
	@classmethod
	def convert_ai_model(cls, value: str | None) -> dict[str, str] | None:
		"""Convert a string representation of an AI model to a dictionary.

		Args:
			value: A string in the format "provider_id/model_id" or None.

		Returns:
			A dictionary with 'provider_id' and 'model_id' keys, or the original value if not a string.

		Example:
			>>> convert_ai_model("openai/gpt-4")
			{"provider_id": "openai", "model_id": "gpt-4"}
			>>> convert_ai_model(None)
			None
		"""
		if isinstance(value, str):
			provider_id, model_id = value.split("/", 1)
			return {"provider_id": provider_id, "model_id": model_id}
		return value

	@classmethod
	def get_default(cls) -> ConversationProfile:
		"""Create a default conversation profile with minimal configuration.

		Returns:
			A conversation profile initialized with default name and an empty system prompt.
		"""
		return cls(name="default", system_prompt="")

	@cached_property
	def account(self) -> Account | None:
		"""Retrieves the account associated with the conversation profile.

		Returns:
			The account associated with the conversation profile, or None if no account is set.
		"""
		if self.account_info is None:
			return None
		return get_account_config().get_account_from_info(self.account_info)

	def set_account(self, account: Account | None):
		"""Set the account associated with the conversation profile.

		Update the account cached property and the account info field based on the provided account.

		Args:
			account: The account to associate with the conversation profile. Set to None to remove the account association.
		"""
		if account is None:
			self.account_info = None
			if "account" in self.__dict__:
				del self.__dict__["account"]
		else:
			self.account_info = account.get_account_info()
			self.__dict__["account"] = account

	@property
	def ai_model_id(self) -> str | None:
		"""Retrieves the model ID from the AI model information.

		Returns:
		The model ID if AI model information is set, otherwise None.
		"""
		if self.ai_model_info is None:
			return None
		return self.ai_model_info.model_id

	@property
	def ai_provider(self) -> Provider | None:
		"""Retrieves the AI provider associated with the conversation profile.

		Notes:
			- Prioritizes the account's provider if an account is set
			- Falls back to the AI model's provider if no account is set
			- Returns None if neither account nor AI model info is available
		Returns:
			The provider of the AI model, determined by either the account's provider or the AI model's provider. Returns None if no provider can be determined.
		"""
		if self.account is None and self.ai_model_info is None:
			return None
		if self.account:
			return self.account.provider
		if self.ai_model_info:
			return self.ai_model_info.provider

	def set_model_info(self, provider_id: str, model_id: str):
		"""Set the AI model information for the conversation profile.

		Args:
			provider_id: The unique identifier of the AI model provider.
			model_id: The specific identifier of the AI model within the provider's ecosystem.

		Raises:
			ValueError: If either provider_id or model_id is an empty string.

		Example:
			profile = ConversationProfile()
			profile.set_model_info('openai', 'gpt-4')
		"""
		self.ai_model_info = AIModelInfo(
			provider_id=provider_id, model_id=model_id
		)

	def __eq__(self, value: ConversationProfile | None) -> bool:
		"""Compare two conversation profiles for equality based on their unique identifier.

		Args:
			value: Another conversation profile to compare with this instance.

		Returns:
			True if the profiles have the same ID, False otherwise. Returns False if the compared value is None.
		"""
		if value is None:
			return False
		return self.id == value.id

	@model_validator(mode="after")
	def check_same_provider(self) -> ConversationProfile:
		"""Validates that the AI model provider matches the account provider.

		This method ensures that when both an account and AI model information are present,
		the provider ID of the AI model matches the provider ID of the account.

		Raises:
			ValueError: If the AI model provider differs from the account provider.

		Returns:
			ConversationProfile: The current conversation profile instance if validation passes.
		"""
		if self.account is not None and self.ai_model_info is not None:
			if self.ai_model_info.provider_id != self.account.provider.id:
				raise ValueError(
					"Model provider must be the same as account provider"
				)
		return self

	@model_validator(mode="after")
	def check_model_params(self) -> ConversationProfile:
		"""Validates that model parameters are set correctly.

		This method ensures that model parameters are only set when an AI model is present.

		Raises:
			ValueError: If model parameters are set without an AI model.
		"""
		if self.ai_model_info is None:
			if self.max_tokens is not None:
				raise ValueError("Max tokens must be None without model")
			if self.temperature is not None:
				raise ValueError("Temperature must be None without model")
			if self.top_p is not None:
				raise ValueError("Top P must be None without model")
		return self


config_file_name = "profiles.yml"


class ConversationProfileManager(BasiliskBaseSettings):
	"""A configuration model for managing conversation profiles."""

	model_config = get_settings_config_dict(config_file_name)

	profiles: list[OnErrorOmit[ConversationProfile]] = Field(
		default_factory=list
	)

	default_profile_id: Optional[UUID4] = Field(default=None)

	def get_profile(self, **kwargs: dict) -> ConversationProfile | None:
		"""Retrieve a conversation profile based on the provided key-value pairs.

		Args:
			kwargs: Keyword arguments containing the profile attributes to match.

		Returns:
			The first conversation profile that matches all the provided attributes, or None if no profile is found.
		"""
		return next(
			filter(
				lambda p: all(getattr(p, k) == v for k, v in kwargs.items()),
				self.profiles,
			),
			None,
		)

	@cached_property
	def default_profile(self) -> ConversationProfile | None:
		"""Retrieves the default conversation profile.

		Returns:
			The default conversation profile if set, otherwise None.
		"""
		if self.default_profile_id is None:
			return None
		return self.get_profile(id=self.default_profile_id)

	def set_default_profile(self, value: ConversationProfile | None):
		"""Set the default conversation profile.

		Args:
			value: The conversation profile to set as the default. Set to None to remove the default profile.
		"""
		if value is None:
			self.default_profile_id = None
		else:
			self.default_profile_id = value.id
		if "default_profile" in self.__dict__:
			del self.__dict__["default_profile"]

	@model_validator(mode="after")
	def check_default_profile(self) -> ConversationProfileManager:
		"""Validates that the default profile is set and exists.

		Auto-corrects invalid default_profile_id by setting it to None if the
		referenced profile no longer exists, instead of raising an error.

		Returns:
		The current conversation profile manager instance after validation/correction.
		"""
		if self.default_profile_id is None:
			return self
		if self.default_profile is None:
			# Auto-correct invalid default_profile_id instead of failing
			log.warning(
				"Unable to load default profile with id: '%s'",
				self.default_profile_id,
			)
			self.default_profile_id = None
			if "default_profile" in self.__dict__:
				del self.__dict__["default_profile"]
		return self

	def __iter__(self) -> Iterable[ConversationProfile]:
		"""Iterate over the conversation profiles.

		Returns:
			An iterator over the conversation profiles.
		"""
		return iter(self.profiles)

	def add(self, profile: ConversationProfile):
		"""Add a conversation profile to the config.

		Args:
			profile: The conversation profile to add.
		"""
		self.profiles.append(profile)

	def remove(self, profile: ConversationProfile):
		"""Remove a conversation profile from the config.

		Args:
			profile: The conversation profile to remove.
		"""
		if profile == self.default_profile:
			self.default_profile_id = None
			if "default_profile" in self.__dict__:
				del self.__dict__["default_profile"]
		self.profiles.remove(profile)

	def __len__(self) -> int:
		"""Get the number of conversation profiles.

		Returns:
			The number of conversation profiles in the config.
		"""
		return len(self.profiles)

	def __getitem__(self, index: int | UUID) -> ConversationProfile:
		"""Get a conversation profile by index or ID.

		Args:
			index: The index or ID of the conversation profile to retrieve.

		Returns:
			The conversation profile at the specified index or with the specified ID.

		Raises:
			KeyError: If no profile is found with the provided index or ID.
			TypeError: If the index type is not an integer or UUID.
		"""
		if isinstance(index, int):
			return self.profiles[index]
		elif isinstance(index, UUID):
			profile = self.get_profile(id=index)
			if profile is None:
				raise KeyError(f"No profile found with id {index}")
			return profile
		else:
			raise TypeError(f"Invalid index type: {type(index)}")

	def __delitem__(self, index: int):
		"""Remove a conversation profile by index.

		Args:
			index: The index of the conversation profile to remove.

		Raises:
			IndexError: If the index is out of range.
		"""
		profile = self.profiles[index]
		self.remove(profile)

	def __setitem__(self, index: int | UUID, value: ConversationProfile):
		"""Set a conversation profile by index or ID.

		Args:
			index: The index or ID of the conversation profile to set.
			value: The conversation profile to set.

		Raises:
			TypeError: If the index type is not an integer or UUID.
		"""
		if isinstance(index, int):
			self.profiles[index] = value
		elif isinstance(index, UUID):
			profile = self.get_profile(id=index)
			if not profile:
				self.add(value)
			else:
				idx = self.profiles.index(profile)
				self.profiles[idx] = value
		else:
			raise TypeError(f"Invalid index type: {type(index)}")

	def save(self):
		"""Save the conversation profile config to a file."""
		save_config_file(
			self.model_dump(
				mode="json", exclude_defaults=True, exclude_none=True
			),
			config_file_name,
		)


@cache
def get_conversation_profile_config() -> ConversationProfileManager:
	"""Get the conversation profile configuration. Cache the result for future calls.

	Returns:
		The conversation profile configuration manager.
	"""
	log.debug("Loading conversation profile config")
	return ConversationProfileManager()
