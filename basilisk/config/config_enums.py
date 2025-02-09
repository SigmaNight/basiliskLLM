from __future__ import annotations

import enum


class AccountSource(enum.StrEnum):
	"""Enum values for account sources."""

	# account was loaded from an environment variable
	ENV_VAR = enum.auto()
	# account was loaded from the configuration file
	CONFIG = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[AccountSource, str]:
		"""Return a dict of account source labels.

		Returns:
			A dict of account source enum values as keys and their translated labels as values.
		"""
		return {
			# Translators: Account source label
			cls.ENV_VAR: _("Environment variable"),
			# Translators: Account source label
			cls.CONFIG: _("Configuration file"),
		}


class KeyStorageMethodEnum(enum.StrEnum):
	"""Enum values for key storage methods."""

	# store the key in the config file as plain text
	PLAIN = enum.auto()
	# store the key in the system keyring
	SYSTEM = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[str, str]:
		"""Return a dict of key storage method labels.

		Returns:
			A dict of key storage method enum values as keys and their translated labels as values.
		"""
		return {
			# Translators: A label for the API key storage method in the account dialog
			cls.PLAIN: _("Plain text"),
			# Translators: A label for the API key storage method in the account dialog
			cls.SYSTEM: _("System keyring"),
		}


class LogLevelEnum(enum.StrEnum):
	"""Enum values for log levels."""

	# no log messages are displayed
	NOTSET = "off"
	# log messages are displayed for debugging purposes
	DEBUG = enum.auto()
	# log messages are displayed for informational purposes
	INFO = enum.auto()
	# log messages are displayed for warning purposes
	WARNING = enum.auto()
	# log messages are displayed for error purposes
	ERROR = enum.auto()
	# log messages are displayed for critical purposes
	CRITICAL = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[LogLevelEnum, str]:
		"""Return a dict of log level labels.

		Returns:
			A dict of log level enum values as keys and their translated labels as values.
		"""
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


class ReleaseChannelEnum(enum.StrEnum):
	"""Enum values for release channels."""

	# stable releases
	STABLE = enum.auto()
	# beta releases (pre-release)
	BETA = enum.auto()
	# development releases (nightly)
	DEV = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[ReleaseChannelEnum, str]:
		"""Return a dict of release channel labels.

		Returns:
			A dict of release channel enum values as keys and their translated labels as values.
		"""
		return {
			# Translators: A label for the release channel in the settings dialog
			cls.STABLE: _("Stable"),
			# Translators: A label for the release channel in the settings dialog
			cls.BETA: _("Beta"),
			# Translators: A label for the release channel in the settings dialog
			cls.DEV: _("Development"),
		}


class AutomaticUpdateModeEnum(enum.StrEnum):
	"""Enum values for automatic update modes."""

	# automatic updates are disabled
	OFF = enum.auto()
	# Notify for update availability but do not download or install
	NOTIFY = enum.auto()
	# automatically download updates and notify but do not install
	DOWNLOAD = enum.auto()
	# automatically download and install updates
	INSTALL = enum.auto()

	@classmethod
	def get_labels(cls) -> dict[AutomaticUpdateModeEnum, str]:
		"""Return a dict of automatic update mode labels.

		Returns:
			A dict of automatic update mode enum values as keys and their translated labels as values.
		"""
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
