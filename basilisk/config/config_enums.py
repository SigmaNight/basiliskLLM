from enum import Enum


class KeyStorageMethodEnum(Enum):
	plain = "plain"
	system = "system"


class AccountSource(Enum):
	ENV_VAR = "env_var"
	CONFIG = "config"


class LogLevelEnum(Enum):
	NOTSET = "off"
	DEBUG = "debug"
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"


class ReleaseChannelEnum(Enum):
	STABLE = "stable"
	BETA = "beta"
	DEV = "dev"


class AutomaticUpdateModeEnum(Enum):
	OFF = "off"
	NOTIFY = "notify"
	DOWNLOAD = "download"
	INSTALL = "install"


def get_account_source_labels() -> dict[AccountSource, str]:
	return {
		# Translators: Account source label
		AccountSource.ENV_VAR: _("Environment variable"),
		# Translators: Account source label
		AccountSource.CONFIG: _("Configuration file"),
	}
