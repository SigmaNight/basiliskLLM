import logging
from functools import cached_property

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class XAIEngine(OpenAIEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
	}

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		log.debug("Getting xAI models")
		models = [
			ProviderAIModel(
				id="grok-2-latest",
				# Translators: This is a model description
				description=_(""),
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-2-vision-latest",
				# Translators: This is a model description
				description=_(""),
				context_window=32768,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
			ProviderAIModel(
				id="grok-beta",
				# Translators: This is a model description
				description=_(""),
				context_window=131072,
				max_temperature=2.0,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="grok-vision-beta",
				# Translators: This is a model description
				description=_(""),
				context_window=8192,
				max_temperature=2.0,
				default_temperature=1.0,
				vision=True,
			),
		]
		return models
