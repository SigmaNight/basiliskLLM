import logging
from functools import cached_property
from .baseengine import ProviderAIModel
from .openaiengine import OpenAIEngine

log = logging.getLogger(__name__)


class MistralAIEngine(OpenAIEngine):
	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		log.debug("Getting MistralAI models")
		models = [
			ProviderAIModel(
				id="open-mistral-7b",
				# Translators: This is a model description
				description=_("aka %s") % "mistral-tiny-2312",
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="open-mixtral-8x7b",
				# Translators: This is a model description
				description=_("aka %s") % "mistral-small-2312",
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-small-latest",
				# Translators: This is a model description
				description=_(
					"Simple tasks (Classification, Customer Support, or Text Generation)"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-medium-latest",
				# Translators: This is a model description
				description=_(
					"Intermediate tasks that require moderate reasoning (Data extraction, Summarizing a Document, Writing emails, Writing a Job Description, or Writing Product Descriptions)"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-large-latest",
				# Translators: This is a model description
				description=_(
					"Complex tasks that require large reasoning capabilities or are highly specialized (Synthetic Text Generation, Code Generation, RAG, or Agents)"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
		]
		return models
