"""Main configuration file for BasiliskLLM appication."""

import logging
from datetime import datetime
from functools import cache

from pydantic import BaseModel, Field, model_validator

from .config_enums import (
	AutomaticUpdateModeEnum,
	LogLevelEnum,
	ReleaseChannelEnum,
)
from .config_helper import (
	BasiliskBaseSettings,
	get_settings_config_dict,
	save_config_file,
)

log = logging.getLogger(__name__)

config_file_name = "config.yml"


class GeneralSettings(BaseModel):
	"""General settings for BasiliskLLM."""

	language: str = Field(default="auto")
	advanced_mode: bool = Field(default=False)
	log_level: LogLevelEnum = Field(default=LogLevelEnum.INFO)
	automatic_update_mode: AutomaticUpdateModeEnum = Field(
		default=AutomaticUpdateModeEnum.NOTIFY
	)
	release_channel: ReleaseChannelEnum = Field(default=ReleaseChannelEnum.BETA)
	last_update_check: datetime | None = Field(default=None)
	quit_on_close: bool = Field(default=False)


class ConversationSettings(BaseModel):
	"""Conversation settings for BasiliskLLM."""

	role_label_user: str | None = Field(default=None)
	role_label_assistant: str | None = Field(default=None)
	nav_msg_select: bool = Field(default=False)
	shift_enter_mode: bool = Field(default=False)
	use_accessible_output: bool = Field(default=True)
	focus_history_after_send: bool = Field(default=False)
	auto_save_to_db: bool = Field(default=True)
	auto_save_draft: bool = Field(default=True)
	reopen_last_conversation: bool = Field(default=False)
	last_active_conversation_id: int | None = Field(default=None)


class ImagesSettings(BaseModel):
	"""Image settings for BasiliskLLM."""

	max_height: int = Field(default=720)
	max_width: int = Field(default=0)
	quality: int = Field(default=85, ge=1, le=100)
	resize: bool = Field(default=False)


class RecordingsSettings(BaseModel):
	"""Recording settings for BasiliskLLM."""

	sample_rate: int = Field(default=16000, ge=8000, le=48000)
	channels: int = Field(default=1, ge=1, le=2)
	dtype: str = Field(default="int16")


class ServerSettings(BaseModel):
	"""Server settings for BasiliskLLM."""

	port: int = Field(default=4242)
	enable: bool = Field(default=True)


class NetworkSettings(BaseModel):
	"""Network settings for BasiliskLLM."""

	use_system_cert_store: bool = Field(default=True)


class BasiliskConfig(BasiliskBaseSettings):
	"""BasiliskLLM configuration settings."""

	model_config = get_settings_config_dict(config_file_name)

	general: GeneralSettings = Field(default_factory=GeneralSettings)
	conversation: ConversationSettings = Field(
		default_factory=ConversationSettings
	)
	images: ImagesSettings = Field(default_factory=ImagesSettings)
	recordings: RecordingsSettings = Field(default_factory=RecordingsSettings)
	network: NetworkSettings = Field(default_factory=NetworkSettings)
	server: ServerSettings = Field(default_factory=ServerSettings)

	@model_validator(mode="before")
	@classmethod
	def migrate_accounts(cls, value: dict) -> dict:
		"""Migrate accounts to its own config file.

		Args:
			value: The configuration settings.

		Returns:
			The configuration settings with the accounts removed.
		"""
		accounts = value.pop("accounts", None)
		if not accounts:
			return value
		log.info("Migrating accounts to its own config file")
		from .account_config import AccountManager

		account_dict = {"accounts": accounts}
		account_manager = AccountManager.model_validate(account_dict)
		account_manager.save()
		save_config_file(value, config_file_name)
		return value

	def save(self):
		"""Save the configuration settings."""
		save_config_file(
			self.model_dump(
				mode="json",
				by_alias=True,
				exclude_defaults=True,
				exclude_none=True,
			),
			config_file_name,
		)


@cache
def get_basilisk_config() -> BasiliskConfig:
	"""Get the Basilisk configuration settings. Cache the result for future calls.

	Returns:
		The Basilisk configuration settings.
	"""
	log.debug("Loading Basilisk config")
	return BasiliskConfig()
