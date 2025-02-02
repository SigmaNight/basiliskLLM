from __future__ import annotations

from enum import IntEnum, StrEnum, auto


class AccountSource(StrEnum):
	ENV_VAR = auto()
	CONFIG = auto()

	@classmethod
	def get_labels(cls) -> dict[AccountSource, str]:
		return {
			# Translators: Account source label
			cls.ENV_VAR: _("Environment variable"),
			# Translators: Account source label
			cls.CONFIG: _("Configuration file"),
		}


class AutomaticUpdateMode(StrEnum):
	OFF = auto()
	NOTIFY = auto()
	DOWNLOAD = auto()
	INSTALL = auto()

	@classmethod
	def get_labels(cls) -> dict[AutomaticUpdateMode, str]:
		return {
			# Translators: A label for the automatic update mode in the settings dialog
			cls.OFF: _("Off"),
			# Translators: A label for the automatic update mode in the settings dialog
			cls.NOTIFY: _("Notify new version"),
			# Translators: A label for the automatic update mode in the settings dialog
			cls.DOWNLOAD: _("Download new version"),
			# Translators: A label for the automatic update mode in the settings dialog
			cls.INSTALL: _("Install new version"),
		}


class CaptureMode(StrEnum):
	FULL = auto()
	PARTIAL = auto()
	WINDOW = auto()


class HotkeyAction(IntEnum):
	TOGGLE_VISIBILITY = 1
	CAPTURE_FULL = 20
	CAPTURE_WINDOW = 21


class ImageFileTypes(StrEnum):
	UNKNOWN = auto()
	IMAGE_LOCAL = auto()
	IMAGE_MEMORY = auto()
	IMAGE_URL = auto()

	@classmethod
	def _missing_(cls, value: object) -> ImageFileTypes:
		if not isinstance(value, str):
			return cls.UNKNOWN
		value_lower = value.lower()
		if value_lower in {"http", "https", "data"}:
			return cls.IMAGE_URL
		if value.lower() == "zip":
			return cls.IMAGE_LOCAL
		return cls.UNKNOWN


class KeyStorageMethod(StrEnum):
	PLAIN = auto()
	SYSTEM = auto()


class LogLevel(StrEnum):
	NOTSET = "off"
	DEBUG = auto()
	INFO = auto()
	WARNING = auto()
	ERROR = auto()
	CRITICAL = auto()

	@classmethod
	def get_labels(cls) -> dict[LogLevel, str]:
		return {
			# Translators: A label for the log level in the settings dialog
			cls.NOTSET: _("Off"),
			# Translators: A label for the log level in the settings dialog
			cls.DEBUG: _("Debug"),
			# Translators: A label for the log level in the settings dialog
			cls.INFO: _("Info"),
			# Translators: A label for the log level in the settings dialog
			cls.WARNING: _("Warning"),
			# Translators: A label for the log level in the settings dialog
			cls.ERROR: _("Error"),
			# Translators: A label for the log level in the settings dialog
			cls.CRITICAL: _("Critical"),
		}


class MessageRole(StrEnum):
	ASSISTANT = auto()
	USER = auto()
	SYSTEM = auto()

	@classmethod
	def get_labels(cls) -> dict[MessageRole, str]:
		return {
			# Translators: Label indicating that the message is from the user in a conversation
			cls.USER: _("User:") + ' ',
			# Translators: Label indicating that the message is from the assistant in a conversation
			cls.ASSISTANT: _("Assistant:") + ' ',
		}


class MessageSegmentType(StrEnum):
	PREFIX = auto()
	CONTENT = auto()
	SUFFIX = auto()


class ProviderAPIType(StrEnum):
	OPENAI = auto()
	ANTHROPIC = auto()
	OLLAMA = auto()
	GEMINI = auto()


class ProviderCapability(StrEnum):
	IMAGE = auto()
	TEXT = auto()
	STT = auto()
	TTS = auto()


class ReleaseChannel(StrEnum):
	STABLE = auto()
	BETA = auto()
	DEV = auto()

	@classmethod
	def get_labels(cls) -> dict[ReleaseChannel, str]:
		return {
			# Translators: A label for the release channel in the settings dialog
			cls.STABLE: _("Stable"),
			# Translators: A label for the release channel in the settings dialog
			cls.BETA: _("Beta"),
			# Translators: A label for the release channel in the settings dialog
			cls.DEV: _("Development"),
		}


class SearchDirection(IntEnum):
	BACKWARD = auto(0)
	FORWARD = auto()


class SearchMode(IntEnum):
	PLAIN_TEXT = auto(0)
	EXTENDED = auto()
	REGEX = auto()
