"""This module contains the ProviderCapability enum class."""

import enum


class ProviderCapability(enum.StrEnum):
	"""Defines the different capabilities that a provider can support."""

	# The provider supports document processing (excluding images)
	DOCUMENT = enum.auto()
	# The provider supports citation processing
	CITATION = enum.auto()
	# The provider supports image processing
	IMAGE = enum.auto()
	# The provider supports text processing
	TEXT = enum.auto()
	# The provider supports speech-to-text conversion
	STT = enum.auto()
	# The provider supports text-to-speech conversion
	TTS = enum.auto()
