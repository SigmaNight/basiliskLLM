from __future__ import annotations

import logging
from functools import cache, cached_property
from typing import Iterable, Optional

from more_itertools import locate
from pydantic import (
	BaseModel,
	ConfigDict,
	Field,
	PrivateAttr,
	field_validator,
	model_validator,
)

from basilisk.provider import Provider, get_provider

from .account_config import Account, AccountInfo, get_account_config
from .config_helper import (
	BasiliskBaseSettings,
	get_settings_config_dict,
	save_config_file,
)

log = logging.getLogger(__name__)


class ConversationProfile(BaseModel):
	model_config = ConfigDict(revalidate_instances="always")

	name: str
	system_prompt: str = Field(default="")
	account_info: Optional[AccountInfo] = Field(default=None)
	ai_model_info: Optional[str] = Field(default=None, pattern=r"^[a-zA-Z]/.+$")
	max_tokens: Optional[int] = Field(default=None)
	temperature: Optional[float] = Field(default=None)
	top_p: Optional[float] = Field(default=None)
	stream_mode: bool = Field(default=True)

	@field_validator("ai_model_info")
	@classmethod
	def provider_must_exist(cls, value: str):
		if value is None:
			return None
		provider_id, model_id = value.split("/", 1)
		get_provider(id=provider_id)
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
		return self.ai_model_info.split("/", 1)[1]

	@property
	def ai_provider(self) -> Optional[Provider]:
		if self.account is None and self.ai_model_info is None:
			return None
		if self.account:
			return self.account.provider
		if self.ai_model_info:
			provider_id, model_id = self.ai_model_info.split("/", 1)
			return get_provider(id=provider_id)

	def set_model_info(self, provider_id: str, model_id: str):
		self.ai_model_info = f"{provider_id}/{model_id}"

	def __eq__(self, value: Optional[ConversationProfile]) -> bool:
		if value is None:
			return False
		return self.name == value.name

	@model_validator(mode="after")
	def check_same_provider(self) -> ConversationProfile:
		if self.account is not None and self.ai_model_info is not None:
			provider_id, model_id = self.ai_model_info.split("/", 1)
			if provider_id != self.account.provider.id:
				raise ValueError(
					"Model provider must be the same as account provider"
				)
		return self


config_file_name = "profiles.yml"


class ConversationProfileManager(BasiliskBaseSettings):
	model_config = get_settings_config_dict(config_file_name)

	profiles: list[ConversationProfile] = Field(default_factory=list)

	default_profile_name: Optional[str] = Field(default=None)
	_profiles_name: set[str] = PrivateAttr(default_factory=set)

	@property
	def profiles_name(self) -> set[str]:
		return self._profiles_name

	@model_validator(mode="after")
	def check_unique_names(self) -> ConversationProfileManager:
		for profile in self.profiles:
			if profile.name in self._profiles_name:
				raise ValueError(f"Duplicate profile name: {profile.name}")
			self._profiles_name.add(profile.name)
		return self

	@property
	def default_profile(self) -> Optional[ConversationProfile]:
		if self.default_profile_name is None:
			return None
		return self[self.default_profile_name]

	@model_validator(mode="after")
	def check_default_profile(self) -> ConversationProfileManager:
		if self.default_profile_name is None:
			return self
		if self.default_profile_name not in self._profiles_name:
			raise ValueError(
				f"Default profile not found: {self.default_profile_name}"
			)
		return self

	def __iter__(self) -> Iterable[ConversationProfile]:
		return iter(self.profiles)

	def add(self, profile: ConversationProfile):
		if profile.name in self._profiles_name:
			raise ValueError(f"Duplicate profile name: {profile.name}")
		self.profiles.append(profile)
		self._profiles_name.add(profile.name)

	def remove(self, profile: ConversationProfile):
		if profile.name == self.default_profile_name:
			self.default_profile_name = None
		self.profiles.remove(profile)
		self._profiles_name.remove(profile.name)

	def __len__(self) -> int:
		return len(self.profiles)

	def __getitem__(self, index: int) -> ConversationProfile:
		if isinstance(index, int):
			return self.profiles[index]
		elif isinstance(index, str):
			if index not in self._profiles_name:
				raise KeyError(f"Profile not found: {index}")
			return next(filter(lambda p: p.name == index, self.profiles))
		else:
			raise TypeError(f"Invalid index type: {type(index)}")

	def __delitem__(self, index: int):
		profile = self.profiles[index]
		self.remove(profile)

	def __setitem__(self, index: int, value: ConversationProfile):
		if isinstance(index, str):
			value.name = index
			if index not in self._profiles_name:
				self.add(value)
				return
			index = next(locate(self.profiles, lambda p: p.name == index))
		if index >= len(self):
			raise IndexError(f"Index out of range: {index}")
		old_profile_name = self.profiles[index].name
		self.profiles[index] = value
		self._profiles_name.remove(old_profile_name)
		self._profiles_name.add(value.name)

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
