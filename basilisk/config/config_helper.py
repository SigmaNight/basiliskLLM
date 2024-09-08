import logging
from pathlib import Path

import yaml
from platformdirs import user_config_path as get_user_config_path
from pydantic import Extra
from pydantic_settings import (
	BaseSettings,
	PydanticBaseSettingsSource,
	SettingsConfigDict,
	YamlConfigSettingsSource,
)

import basilisk.global_vars as global_vars

log = logging.getLogger(__name__)


class BasiliskBaseSettings(BaseSettings):
	@classmethod
	def settings_customise_sources(
		cls,
		settings_cls: BaseSettings,
		init_settings: PydanticBaseSettingsSource,
		env_settings: PydanticBaseSettingsSource,
		dotenv_settings: PydanticBaseSettingsSource,
		file_secret_settings: PydanticBaseSettingsSource,
	) -> tuple[PydanticBaseSettingsSource, ...]:
		return (
			YamlConfigSettingsSource(settings_cls),
			env_settings,
			init_settings,
		)


user_config_path = get_user_config_path(
	"basilisk", "basilisk_llm", roaming=True, ensure_exists=True
)


def get_config_file_paths(file_path: str) -> list[Path]:
	search_config_paths = []
	if global_vars.user_data_path:
		search_config_paths.append(global_vars.user_data_path / file_path)
	search_config_paths.append(user_config_path / file_path)
	return search_config_paths


def search_existing_path(paths: list[Path]) -> Path:
	for p in paths:
		if p.exists() or p.parent.exists():
			return p
	return paths[-1]


def get_settings_config_dict(file_path: str) -> SettingsConfigDict:
	return SettingsConfigDict(
		env_prefix="BASILISK_",
		extra=Extra.allow,
		yaml_file=search_existing_path(get_config_file_paths(file_path)),
		yaml_file_encoding="UTF-8",
	)


def save_config_file(conf_dict: dict, file_path: str) -> None:
	log.debug("Saving config file: %s", file_path)
	conf_save_path = search_existing_path(get_config_file_paths(file_path))
	with conf_save_path.open(mode='w', encoding="UTF-8") as config_file:
		yaml.dump(conf_dict, config_file, indent=2, sort_keys=False)
	log.debug("Config saved to %s", conf_save_path)
