import yaml
from pathlib import Path
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from pydantic_settings import (
	BaseSettings,
	PydanticBaseSettingsSource,
	SettingsConfigDict,
	YamlConfigSettingsSource,
)

from account import AccountManager


class LogLevelEnum(Enum):
	NOTSET = "off"
	DEBUG = "debug"
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


search_config_paths = [Path(__file__).parent / Path("basilisk_config.yml")]


class GeneralSettings(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	language: str = Field(default="auto")
	log_level: LogLevelEnum = Field(default=LogLevelEnum.DEBUG)


class BasiliskConfig(BaseSettings):
	model_config = SettingsConfigDict(
		env_prefix="BASILISK_",
		yaml_file=search_config_paths,
		yaml_file_encoding="UTF-8",
	)
	general: GeneralSettings = Field(default_factory=GeneralSettings)
	accounts: AccountManager = Field(default=AccountManager(list()))

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
		conf_save_path = search_existing_path(search_config_paths)
		with conf_save_path.open(mode='w', encoding="UTF-8") as config_file:
			yaml.dump(basilisk_dict, config_file, indent=2, sort_keys=False)


conf = None


def search_existing_path(paths: list[Path]) -> Path:
	for p in paths:
		if p.exists():
			return p
	return paths[0]


def initialize_config():
	global conf
	conf = BasiliskConfig()
