from __future__ import annotations

from enum import Enum


class AccountSource(Enum):
	ENV_VAR = "env_var"
	CONFIG = "config"

	@classmethod
	def get_labels(cls) -> dict[AccountSource, str]:
		return {
			# Translators: Account source label
			cls.ENV_VAR: _("Environment variable"),
			# Translators: Account source label
			cls.CONFIG: _("Configuration file"),
		}


class AutomaticUpdateMode(Enum):
	OFF = "off"
	NOTIFY = "notify"
	DOWNLOAD = "download"
	INSTALL = "install"

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


class CaptureMode(Enum):
	FULL = "full"
	PARTIAL = "partial"
	WINDOW = "window"


class HotkeyAction(Enum):
	TOGGLE_VISIBILITY = 1
	CAPTURE_FULL = 20
	CAPTURE_WINDOW = 21


class ImageFileTypes(Enum):
	UNKNOWN = "unknown"
	IMAGE_LOCAL = "local"
	IMAGE_MEMORY = "memory"
	IMAGE_URL = "http"

	@classmethod
	def _missing_(cls, value: object) -> ImageFileTypes:
		if isinstance(value, str) and value.lower() == "data":
			return cls.IMAGE_URL
		if isinstance(value, str) and value.lower() == "https":
			return cls.IMAGE_URL
		if isinstance(value, str) and value.lower() == "zip":
			return cls.IMAGE_LOCAL
		return cls.UNKNOWN


class KeyStorageMethod(Enum):
	plain = "plain"
	system = "system"


class LogLevel(Enum):
	NOTSET = "off"
	DEBUG = "debug"
	INFO = "info"
	WARNING = "warning"
	ERROR = "error"
	CRITICAL = "critical"

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


class MessageRole(Enum):
	ASSISTANT = "assistant"
	USER = "user"
	SYSTEM = "system"

	@classmethod
	def get_labels(cls) -> dict[MessageRole, str]:
		return {
			# Translators: Label indicating that the message is from the user in a conversation
			cls.USER: _("User:") + ' ',
			# Translators: Label indicating that the message is from the assistant in a conversation
			cls.ASSISTANT: _("Assistant:") + ' ',
		}


class MessageSegmentType(Enum):
	PREFIX = "prefix"
	CONTENT = "content"
	SUFFIX = "suffix"


class ProviderAPIType(Enum):
	OPENAI = "openai"
	ANTHROPIC = "anthropic"
	OLLAMA = "ollama"
	GEMINI = "gemini"


class ProviderCapability(Enum):
	IMAGE = "image"
	TEXT = "text"
	STT = "stt"
	TTS = "tts"


class ReleaseChannel(Enum):
	STABLE = "stable"
	BETA = "beta"
	DEV = "dev"

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


class SearchDirection(Enum):
	BACKWARD = 0
	FORWARD = 1


class SearchMode(Enum):
	PLAIN_TEXT = 0
	EXTENDED = 1
	REGEX = 2
