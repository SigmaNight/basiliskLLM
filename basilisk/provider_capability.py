"""This module contains the ProviderCapability enum class."""

import enum


class ProviderCapability(enum.StrEnum):
	"""Defines the different capabilities that a provider can support."""

	# The provider support audio processing
	AUDIO = enum.auto()
	# The provider supports document processing (excluding images)
	DOCUMENT = enum.auto()
	# The provider supports citation processing
	CITATION = enum.auto()
	# The provider supports image processing
	IMAGE = enum.auto()
	# The provider supports OCR (Optical Character Recognition)
	OCR = enum.auto()
	# The provider supports text processing
	TEXT = enum.auto()
	# The provider supports speech-to-text conversion
	STT = enum.auto()
	# The provider supports text-to-speech conversion
	TTS = enum.auto()
	# The provider supports video processing
	VIDEO = enum.auto()
	# The provider supports web search capabilities
	WEB_SEARCH = enum.auto()
