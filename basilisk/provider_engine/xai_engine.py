"""Module for xAI API integration.

This module provides the XAIEngine class for interacting with the xAI API,
implementing capabilities for both text and image generation.
"""

import logging

from basilisk.provider_capability import ProviderCapability

from .legacy_openai_engine import LegacyOpenAIEngine

log = logging.getLogger(__name__)


class XAIEngine(LegacyOpenAIEngine):
	"""Engine implementation for xAI API integration.

	Extends LegacyOpenAIEngine to provide xAI-specific model configurations and capabilities.
	Supports both text and image generation through the xAI API.

	Attributes:
		capabilities: Set of supported capabilities including text and image generation.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
	}

	MODELS_JSON_URL = "https://raw.githubusercontent.com/SigmaNight/model-metadata/master/data/x-ai.json"
