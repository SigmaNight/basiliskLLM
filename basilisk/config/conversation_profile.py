from __future__ import annotations

import logging
from functools import cache, cached_property
from typing import Any, Iterable, Optional, Union
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
		"""
		Initialize a conversation profile with the provided data.
		
		Attempts to create a conversation profile by calling the parent class's initializer with the given data. 
		
		Parameters:
		    **data (Any): Keyword arguments containing configuration details for the conversation profile.
		
		Raises:
		    Exception: If initialization fails, logs an error and re-raises the original exception, 
		               preventing the profile from being accessible.
		"""
		try:
			super().__init__(**data)
		except Exception as e:
			log.error(
				f"Error in conversation profile {e}; the profile will not be accessible",
				exc_info=e,
			)
			raise e

	@field_validator("ai_model_info", mode="before")
	@classmethod
	def convert_ai_model(cls, value: Optional[str]) -> Optional[dict[str, str]]:
		"""
		Convert a string representation of an AI model to a dictionary.
		
		Parameters:
		    value (Optional[str]): A string in the format "provider_id/model_id" or None.
		
		Returns:
		    Optional[dict[str, str]]: A dictionary with 'provider_id' and 'model_id' keys, 
		    or the original value if not a string.
		
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
		"""
		Create a default conversation profile with minimal configuration.
		
		Returns:
		    ConversationProfile: A conversation profile initialized with default name and an empty system prompt.
		"""
		return cls(name="default", system_prompt="")

	@cached_property
	def account(self) -> Optional[Account]:
		if self.account_info is None:
			return None
		return get_account_config().get_account_from_info(self.account_info)

	def set_account(self, account: Optional[Account]):
		if account is None:
			self.account_info = None
			if "account" in self.__dict__:
				del self.__dict__["account"]
		else:
			self.account_info = account.get_account_info()
			self.__dict__["account"] = account

	@property
	def ai_model_id(self) -> Optional[str]:
		"""
		Retrieves the model ID from the AI model information.
		
		Returns:
		    Optional[str]: The model ID if AI model information is set, otherwise None.
		"""
		if self.ai_model_info is None:
			return None
		return self.ai_model_info.model_id

	@property
	def ai_provider(self) -> Optional[Provider]:
		"""
		Retrieves the AI provider associated with the conversation profile.
		
		Returns:
		    Optional[Provider]: The provider of the AI model, determined by either the account's provider 
		    or the AI model's provider. Returns None if no provider can be determined.
		
		Notes:
		    - Prioritizes the account's provider if an account is set
		    - Falls back to the AI model's provider if no account is set
		    - Returns None if neither account nor AI model info is available
		"""
		if self.account is None and self.ai_model_info is None:
			return None
		if self.account:
			return self.account.provider
		if self.ai_model_info:
			return self.ai_model_info.provider

	def set_model_info(self, provider_id: str, model_id: str):
		"""
		Set the AI model information for the conversation profile.
		
		Parameters:
		    provider_id (str): The unique identifier of the AI model provider.
		    model_id (str): The specific identifier of the AI model within the provider's ecosystem.
		
		Raises:
		    ValueError: If either provider_id or model_id is an empty string.
		
		Example:
		    profile = ConversationProfile()
		    profile.set_model_info('openai', 'gpt-4')
		"""
		self.ai_model_info = AIModelInfo(
			provider_id=provider_id, model_id=model_id
		)

	def __eq__(self, value: Optional[ConversationProfile]) -> bool:
		"""
		Compare two conversation profiles for equality based on their unique identifier.
		
		Parameters:
		    value (Optional[ConversationProfile]): Another conversation profile to compare with this instance.
		
		Returns:
		    bool: True if the profiles have the same ID, False otherwise. Returns False if the compared value is None.
		"""
		if value is None:
			return False
		return self.id == value.id

	@model_validator(mode="after")
	def check_same_provider(self) -> ConversationProfile:
		"""
		Validates that the AI model provider matches the account provider.
		
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
	model_config = get_settings_config_dict(config_file_name)

	profiles: list[OnErrorOmit[ConversationProfile]] = Field(
		default_factory=list
	)

	default_profile_id: Optional[UUID4] = Field(default=None)

	def get_profile(self, **kwargs: dict) -> Optional[ConversationProfile]:
		return next(
			filter(
				lambda p: all(getattr(p, k) == v for k, v in kwargs.items()),
				self.profiles,
			),
			None,
		)

	@cached_property
	def default_profile(self) -> Optional[ConversationProfile]:
		if self.default_profile_id is None:
			return None
		return self.get_profile(id=self.default_profile_id)

	def set_default_profile(self, value: Optional[ConversationProfile]):
		if value is None:
			self.default_profile_id = None
		else:
			self.default_profile_id = value.id
		if "default_profile" in self.__dict__:
			del self.__dict__["default_profile"]

	@model_validator(mode="after")
	def check_default_profile(self) -> ConversationProfileManager:
		if self.default_profile_id is None:
			return self
		if self.default_profile is None:
			raise ValueError("Default profile not found")
		return self

	def __iter__(self) -> Iterable[ConversationProfile]:
		return iter(self.profiles)

	def add(self, profile: ConversationProfile):
		self.profiles.append(profile)

	def remove(self, profile: ConversationProfile):
		if profile == self.default_profile:
			self.default_profile_id = None
			if "default_profile" in self.__dict__:
				del self.__dict__["default_profile"]
		self.profiles.remove(profile)

	def __len__(self) -> int:
		return len(self.profiles)

	def __getitem__(self, index: Union[int, UUID]) -> ConversationProfile:
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
		profile = self.profiles[index]
		self.remove(profile)

	def __setitem__(self, index: Union[int, UUID], value: ConversationProfile):
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
		save_config_file(
			self.model_dump(
				mode="json", exclude_defaults=True, exclude_none=True
			),
			config_file_name,
		)


@cache
def get_conversation_profile_config() -> ConversationProfileManager:
	log.debug("Loading conversation profile config")
	return ConversationProfileManager()
