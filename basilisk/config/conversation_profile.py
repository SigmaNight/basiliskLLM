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
		if isinstance(value, str):
			provider_id, model_id = value.split("/", 1)
			return {"provider_id": provider_id, "model_id": model_id}
		return value

	@classmethod
	def get_default(cls) -> ConversationProfile:
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
		if self.ai_model_info is None:
			return None
		return self.ai_model_info.model_id

	@property
	def ai_provider(self) -> Optional[Provider]:
		if self.account is None and self.ai_model_info is None:
			return None
		if self.account:
			return self.account.provider
		if self.ai_model_info:
			return self.ai_model_info.provider

	def set_model_info(self, provider_id: str, model_id: str):
		self.ai_model_info = AIModelInfo(
			provider_id=provider_id, model_id=model_id
		)

	def __eq__(self, value: Optional[ConversationProfile]) -> bool:
		if value is None:
			return False
		return self.id == value.id

	@model_validator(mode="after")
	def check_same_provider(self) -> ConversationProfile:
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
