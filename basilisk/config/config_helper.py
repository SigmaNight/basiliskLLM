"""Helper functions for config file handling."""

import logging
from pathlib import Path

import yaml
from platformdirs import user_config_path as get_user_config_path
from pydantic_settings import (
	BaseSettings,
	PydanticBaseSettingsSource,
	SettingsConfigDict,
	YamlConfigSettingsSource,
)

import basilisk.global_vars as global_vars
from basilisk.consts import APP_AUTHOR, APP_NAME

log = logging.getLogger(__name__)


class BasiliskBaseSettings(BaseSettings):
	"""Base settings class for Basilisk."""

	@classmethod
	def settings_customise_sources(
		cls,
		settings_cls: BaseSettings,
		init_settings: PydanticBaseSettingsSource,
		env_settings: PydanticBaseSettingsSource,
		dotenv_settings: PydanticBaseSettingsSource,
		file_secret_settings: PydanticBaseSettingsSource,
	) -> tuple[PydanticBaseSettingsSource, ...]:
		"""Customise the source and order of settings loading.

		Settings are loaded in the following order:
		1. YAML file
		2. Environment variables
		3. Initial settings

		Args:
			settings_cls: The settings class model to load.
			init_settings: A helper class to get settings from init objects.
			env_settings: A helper class to get settings from environment variables.
			dotenv_settings: A helper class to get settings from .env files.
			file_secret_settings: A helper class to get settings from secret files.

		Returns:
			A tuple of settings sources in the order they should be loaded and merged.
		"""
		return (
			YamlConfigSettingsSource(settings_cls),
			env_settings,
			init_settings,
		)


user_config_path = get_user_config_path(
	APP_NAME, APP_AUTHOR, roaming=True, ensure_exists=True
)


def get_config_file_paths(file_path: str) -> list[Path]:
	"""Get the paths to search for a config file.

	Paths are searched in the following order:
	1. user_data_path if defined
	2. user_config_path

	Args:
		file_path: The path to the config file.

	Returns:
		A ordered list of paths to search for the config file.
	"""
	search_config_paths = []
	if global_vars.user_data_path:
		search_config_paths.append(global_vars.user_data_path / file_path)
	search_config_paths.append(user_config_path / file_path)
	return search_config_paths


def search_existing_path(paths: list[Path]) -> Path:
	"""Search for an existing path in a list of paths.

	Args:
		paths: A list of paths to search.

	Returns:
		The first existing path found in the list of paths.
	"""
	for p in paths:
		if p.exists() or p.parent.exists():
			return p
	return paths[-1]


def get_settings_config_dict(file_path: str) -> SettingsConfigDict:
	"""Get the settings config dict for a config file.

	Args:
		file_path: The path to the config file.

	Returns:
		The settings config dict for the config file.
	"""
	return SettingsConfigDict(
		env_prefix="BASILISK_",
		extra="allow",
		yaml_file=search_existing_path(get_config_file_paths(file_path)),
		yaml_file_encoding="UTF-8",
	)


def save_config_file(conf_dict: dict, file_path: str) -> None:
	"""Save a config file in YAML format.

	The config is saved with 2-space indentation and preserves key order.

	Args:
		conf_dict: The config dictionary to save.
		file_path: The path to the config file.
	"""
	log.debug("Saving config file: %s", file_path)
	conf_save_path = search_existing_path(get_config_file_paths(file_path))
	with conf_save_path.open(mode='w', encoding="UTF-8") as config_file:
		yaml.dump(conf_dict, config_file, indent=2, sort_keys=False)
	log.debug("Config saved to %s", conf_save_path)
