import logging
import yaml
import basilisk.globalvars as globalvars
from pathlib import Path
from enum import Enum
from platformdirs import user_config_path
from pydantic import BaseModel, ConfigDict, Extra, Field
from pydantic_settings import (
	BaseSettings,
	PydanticBaseSettingsSource,
	SettingsConfigDict,
	YamlConfigSettingsSource,
)
from .account import AccountManager

log = logging.getLogger(__name__)


class LogLevelEnum(Enum):
	NOTSET = "off"
	DEBUG = "debug"
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


config_file_path = Path("config.yml")
search_config_paths = []
if globalvars.user_data_path:
	search_config_paths.append(globalvars.user_data_path / config_file_path)
search_config_paths.append(
	user_config_path(
		"basilisk", "basilisk_llm", roaming=True, ensure_exists=True
	)
	/ config_file_path
)


def search_existing_path(paths: list[Path]) -> Path:
	for p in paths:
		if p.exists() or p.parent.exists():
			return p
	return paths[-1]


class GeneralSettings(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	language: str = Field(default="auto")
	advanced_mode: bool = Field(default=False)
	log_level: LogLevelEnum = Field(default=LogLevelEnum.DEBUG)


class ImagesSettings(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	max_height: int = Field(default=720)
	max_width: int = Field(default=0)
	quality: int = Field(default=85, ge=1, le=100)
	resize: bool = Field(default=False)


class ServerSettings(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	port: int = Field(default=4242)
	enable: bool = Field(default=True)


class BasiliskConfig(BaseSettings):
	model_config = SettingsConfigDict(
		env_prefix="BASILISK_",
		extra=Extra.allow,
		yaml_file=search_existing_path(search_config_paths),
		yaml_file_encoding="UTF-8",
	)
	general: GeneralSettings = Field(default_factory=GeneralSettings)
	accounts: AccountManager = Field(default=AccountManager(list()))
	images: ImagesSettings = Field(default_factory=ImagesSettings)
	server: ServerSettings = Field(default_factory=ServerSettings)

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

	def save(self) -> None:
		basilisk_dict = self.model_dump(mode="json", by_alias=True)
		log.debug("Saving config: %s", basilisk_dict)
		conf_save_path = search_existing_path(search_config_paths)
		with conf_save_path.open(mode='w', encoding="UTF-8") as config_file:
			yaml.dump(basilisk_dict, config_file, indent=2, sort_keys=False)
		log.debug("Config saved to %s", conf_save_path)


conf = None


def initialize_config() -> BasiliskConfig:
	global conf
	conf = BasiliskConfig()
	return conf
