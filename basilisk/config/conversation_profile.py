from __future__ import annotations

import logging
from functools import cache, cached_property
from typing import Iterable, Optional

from more_itertools import locate
from pydantic import (
	BaseModel,
	Field,
	FieldSerializationInfo,
	JsonValue,
	PrivateAttr,
	SerializerFunctionWrapHandler,
	field_serializer,
	model_validator,
)

from .account_config import Account, AccountInfo, get_account_config
from .config_helper import (
	BasiliskBaseSettings,
	get_settings_config_dict,
	save_config_file,
)

log = logging.getLogger(__name__)


class ConversationProfile(BaseModel):
	name: str
	system_prompt: str = Field(default="")
	account_info: Optional[AccountInfo] = Field(default=None)

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
			del self.__dict__["account"]
		else:
			self.account_info = account.get_account_info()
			self.__dict__["account"] = account

	def __eq__(self, value: ConversationProfile) -> bool:
		return self.name == value.name


config_file_name = "profiles.yml"


class ConversationProfileManager(BasiliskBaseSettings):
	model_config = get_settings_config_dict(config_file_name)

	profiles: list[ConversationProfile] = Field(
		default=[ConversationProfile.get_default()]
	)

	@field_serializer("profiles", mode="wrap", when_used="json")
	@classmethod
	def serialize_profiles(
		cls,
		value: list[ConversationProfile],
		handler: SerializerFunctionWrapHandler,
		info: FieldSerializationInfo,
	) -> list[dict[str, JsonValue]]:
		default_profile = ConversationProfile.get_default()
		profiles = filter(lambda p: p != default_profile, value)
		return handler(list(profiles), info)

	default_profile_name: str = Field(default="default")

	_profiles_name: set[str] = PrivateAttr(default_factory=set)

	@property
	def profiles_name(self) -> set[str]:
		return self._profiles_name

	@property
	def default_profile(self) -> ConversationProfile:
		return self[self.default_profile_name]

	@property
	def default_profile_index(self) -> int:
		return next(
			locate(self.profiles, lambda p: p.name == self.default_profile_name)
		)

	@model_validator(mode="after")
	def check_unique_names(self) -> ConversationProfileManager:
		for profile in self.profiles:
			if profile.name in self._profiles_name:
				raise ValueError(f"Duplicate profile name: {profile.name}")
			self._profiles_name.add(profile.name)
		return self

	@model_validator(mode="after")
	def _check_default_profile(self) -> ConversationProfileManager:
		if (
			self.default_profile_name not in self._profiles_name
			and self.default_profile_name == "default"
		):
			self.add(ConversationProfile.get_default())
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
