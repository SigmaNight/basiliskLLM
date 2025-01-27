import logging
from functools import cached_property

from openai.types.chat import ChatCompletionUserMessageParam

from basilisk.conversation import Message

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class DeepSeekAIEngine(OpenAIEngine):
	capabilities: set[ProviderCapability] = {ProviderCapability.TEXT}

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		log.debug("Getting DeepSeek models")
		# See <https://api-docs.deepseek.com/quick_start/pricing>
		models = [
			ProviderAIModel(
				id="deepseek-chat",
				name="DeepSeek-V3",
				# Translators: This is a model description
				description="",
				context_window=64000,
				max_temperature=2.0,
				default_temperature=1.0,
				max_output_tokens=8000,
			),
			ProviderAIModel(
				id="deepseek-reasoner",
				name="DeepSeek-R1",
				# Translators: This is a model description
				description="",
				context_window=64000,
				max_temperature=2.0,
				default_temperature=1.0,
				max_output_tokens=8000,
			),
		]
		return models

	def prepare_message_request(
		self, message: Message
	) -> ChatCompletionUserMessageParam:
		return ChatCompletionUserMessageParam(
			role=message.role.value, content=message.content
		)

	prepare_message_response = prepare_message_request
