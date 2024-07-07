from __future__ import annotations
import logging
from functools import cached_property
from typing import Generator, Union, TYPE_CHECKING
from openai import OpenAI
from openai.types.chat import ChatCompletionChunk, ChatCompletion
from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

if TYPE_CHECKING:
	from account import Account
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class OpenAIEngine(BaseEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.STT,
		ProviderCapability.TTS,
	}

	def __init__(self, account: Account) -> None:
		super().__init__(account)

	@cached_property
	def client(self) -> OpenAI:
		"""
		Property to return the client object
		"""
		super().client
		organization_key = (
			self.account.active_organization_key.get_secret_value()
			if self.account.active_organization_key
			else None
		)
		return OpenAI(
			api_key=self.account.api_key.get_secret_value(),
			organization=organization_key,
			base_url=str(self.account.provider.base_url),
		)
		log.debug("New openai client initialized")

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		super().models
		log.debug("Getting openAI models")
		return [
			ProviderAIModel(
				id="gpt-4o",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Our most advanced, multimodal flagship model that’s cheaper and faster than GPT-4 Turbo"
				),
				context_window=128000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="gpt-4-turbo",
				# Translators: This is a ProviderAIModel description
				description=_(
					"The latest GPT-4 Turbo model with vision capabilities"
				),
				context_window=128000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="gpt-3.5-turbo",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Points to one of the most recent iterations of gpt-3.5 ProviderAIModel."
				),
				context_window=16385,
				max_output_tokens=4096,
			),
			ProviderAIModel(
				id="gpt-3.5-turbo-0125",
				# Translators: This is a ProviderAIModel description
				description=_(
					"The latest GPT-3.5 Turbo ProviderAIModel with higher accuracy at responding in requested formats and a fix for a bug which caused a text encoding issue for non-English language function calls."
				),
				context_window=16385,
				max_output_tokens=4096,
			),
			ProviderAIModel(
				id="gpt-4-turbo-preview",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Points to one of the most recent iterations of gpt-4 ProviderAIModel."
				),
				context_window=128000,
				max_output_tokens=4096,
			),
			ProviderAIModel(
				id="gpt-4-0125-preview",
				# Translators: This is a ProviderAIModel description
				description=_(
					"The latest GPT-4 ProviderAIModel intended to reduce cases of “laziness” where the ProviderAIModel doesn’t complete a task."
				),
				context_window=128000,
				max_output_tokens=4096,
			),
			ProviderAIModel(
				id="gpt-4-1106-preview",
				# Translators: This is a ProviderAIModel description
				description=_(
					"GPT-4 Turbo ProviderAIModel featuring improved instruction following, JSON mode, reproducible outputs, parallel function calling, and more."
				),
				context_window=128000,
				max_output_tokens=4096,
			),
			ProviderAIModel(
				id="gpt-4-vision-preview",
				# Translators: This is a ProviderAIModel description
				description=_(
					"GPT-4 Turbo with vision. Ability to understand images, in addition to all other GPT-4 Turbo capabilities."
				),
				context_window=128000,
				max_output_tokens=4096,
				vision=True,
			),
			ProviderAIModel(
				id="gpt-4-0613",
				# Translators: This is a ProviderAIModel description
				description=_(
					"More capable than any GPT-3.5 ProviderAIModel, able to do more complex tasks, and optimized for chat"
				),
				max_output_tokens=8192,
			),
			ProviderAIModel(
				id="gpt-4-32k-0613",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Same capabilities as the standard gpt-4 mode but with 4x the context length."
				),
				context_window=32768,
				max_output_tokens=8192,
			),
		]

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.id,
			"messages": self.get_messages(
				new_block, conversation, system_message
			),
			"temperature": new_block.temperature,
			"top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		response = self.client.chat.completions.create(**params)
		return response

	def completion_response_with_stream(
		self, stream: Generator[ChatCompletionChunk, None, None]
	):
		for chunk in stream:
			delta = chunk.choices[0].delta
			if delta and delta.content:
				yield self.normalize_linesep(delta.content)

	def completion_response_without_stream(
		self, response: ChatCompletion, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=self.normalize_linesep(response.choices[0].message.content),
		)
		return new_block

	def get_transcription(
		self, audio_file_path: str, response_format: str = "json"
	) -> str:
		"""
		Get transcription from audio file
		"""
		file = open(audio_file_path, "rb")
		transcription = self.client.audio.transcriptions.create(
			model="whisper-1", file=file, response_format=response_format
		)
		file.close()
		return transcription
