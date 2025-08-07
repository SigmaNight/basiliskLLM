"""Module for OpenAI API integration.

This module provides the OpenAIEngine class for interacting with the OpenAI API,
implementing capabilities for text, image, and audio generation/processing.
"""

from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING, Generator, Union

from openai import OpenAI
from openai.types.chat import (
	ChatCompletion,
	ChatCompletionAssistantMessageParam,
	ChatCompletionChunk,
	ChatCompletionContentPartTextParam,
	ChatCompletionUserMessageParam,
)
from openai.types.chat.chat_completion_content_part_image_param import (
	ChatCompletionContentPartImageParam,
	ImageURL,
)

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

if TYPE_CHECKING:
	from basilisk.config import Account
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class OpenAIEngine(BaseEngine):
	"""Engine implementation for OpenAI API integration.

	Provides functionality for interacting with OpenAI's models, supporting text,
	image, speech-to-text, and text-to-speech capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.TEXT,
		ProviderCapability.STT,
		ProviderCapability.TTS,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the OpenAI engine.

		Args:
			account: Account configuration for the OpenAI provider.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> OpenAI:
		"""Creates and configures the OpenAI client.

		Returns:
			Configured OpenAI client instance.
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
			base_url=self.account.custom_base_url
			or str(self.account.provider.base_url),
		)

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available OpenAI models.

		Returns:
			List of supported OpenAI models with their configurations.
		"""
		super().models
		log.debug("Getting openAI models")
		# See <https://platform.openai.com/docs/models>
		return [
			ProviderAIModel(
				id="gpt-5",
				name="GPT-5",
				# Translators: This is a model description
				description=_("Fastest, most cost-efficient version of GPT-5"),
				context_window=400000,
				max_output_tokens=128000,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-5-mini",
				name="GPT-5 mini",
				# Translators: This is a model description
				description=_(
					"A faster, more cost-efficient version of GPT-5 for well-defined tasks"
				),
				context_window=400000,
				max_output_tokens=128000,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-5-nano",
				name="GPT-5 nano",
				# Translators: This is a model description
				description=_("Fastest, most cost-efficient version of GPT-5"),
				context_window=400000,
				max_output_tokens=128000,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-5-chat-latest",
				name="GPT-5 Chat",
				# Translators: This is a model description
				description=_("GPT-5 model used in ChatGPT"),
				context_window=400000,
				max_output_tokens=128000,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-oss-120b",
				name="gpt-oss-120b",
				# Translators: This is a model description
				description=_(
					"Our most powerful open weight model, which fits into a single H100 GPU"
				),
				context_window=131072,
				max_output_tokens=131072,
				vision=False,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-oss-20b",
				name="gpt-oss-20b",
				# Translators: This is a model description
				description=_(
					"Our medium-sized open weight model for low latency"
				),
				context_window=131072,
				max_output_tokens=131072,
				vision=False,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4.1",
				name="GPT-4.1",
				# Translators: This is a model description
				description=_("Flagship GPT model for complex tasks"),
				context_window=1047576,
				max_output_tokens=32768,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4.1-mini",
				name="GPT-4.1 mini",
				# Translators: This is a model description
				description=_("Balanced for intelligence, speed, and cost"),
				context_window=1047576,
				max_output_tokens=32768,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4.1-nano",
				name="GPT-4.1 nano",
				# Translators: This is a model description
				description=_("Fastest, most cost-effective GPT-4.1 model"),
				context_window=1047576,
				max_output_tokens=32768,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="o4-mini",
				name="o4-mini",
				# Translators: This is a model description
				description=_("Faster, more affordable reasoning model"),
				context_window=200000,
				max_output_tokens=100000,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="o3",
				name="o3",
				# Translators: This is a model description
				description=_("Our most powerful reasoning model"),
				context_window=200000,
				max_output_tokens=100000,
				vision=True,
				reasoning=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o",
				name="GPT 4o",
				# Translators: This is a model description
				description=_(
					"Points to one of the most recent iterations of gpt-4o-mini model"
				),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-search-preview",
				name="GPT-4o Search Preview",
				# Translators: This is a model description
				description=_("GPT model for web search in Chat Completions"),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-mini-search-preview",
				name="GPT-4o mini Search Preview",
				# Translators: This is a model description
				description=_("Fast, affordable small model for web search"),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="chatgpt-4o-latest",
				name="ChatGPT 4o",
				# Translators: This is a model description
				description=_(
					"Dynamic model continuously updated to the current version of GPT-4o in ChatGPT"
				),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-mini",
				name="GPT 4o Mini",
				# Translators: This is a model description
				description=_(
					"Points to one of the most recent iterations of gpt-4o-mini model"
				),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="o3-mini",
				name="o3 Mini",
				# Translators: This is a model description
				description=_(
					"Our most recent small reasoning model, providing high intelligence at the same cost and latency targets of o1-mini. o3-mini also supports key developer features, like Structured Outputs, function calling, Batch API, and more. Like other models in the o-series, it is designed to excel at science, math, and coding tasks."
				),
				context_window=200000,
				max_output_tokens=100000,
				vision=True,
				reasoning=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="o1",
				name="o1",
				# Translators: This is a model description
				description=_(
					"Points to the most recent snapshot of the o1 model"
				),
				context_window=200000,
				max_output_tokens=100000,
				vision=True,
				reasoning=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4-turbo",
				name="GPT 4 Turbo",
				# Translators: This is a model description
				description=_(
					"The latest GPT-4 Turbo model with vision capabilities"
				),
				context_window=128000,
				max_output_tokens=4096,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-3.5-turbo",
				name="GPT 3.5 Turbo",
				# Translators: This is a model description
				description=_(
					"Points to one of the most recent iterations of gpt-3.5 model"
				),
				context_window=16385,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-2024-08-06",
				name="GPT 4o (2024-08-06)",
				# Translators: This is a model description
				description=_(
					"Latest snapshot that supports Structured Outputs"
				),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-2024-05-13",
				name="GPT 4o (2024-05-13)",
				# Translators: This is a model description
				description=_(
					"Our high-intelligence flagship model for complex, multi-step tasks"
				),
				context_window=128000,
				max_output_tokens=4096,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4o-mini-2024-07-18",
				name="GPT 4o Mini (2024-07-18)",
				# Translators: This is a model description
				description=_(
					"Our affordable and intelligent small model for fast, lightweight tasks. GPT-4o mini is cheaper and more capable than GPT-3.5 Turbo"
				),
				context_window=128000,
				max_output_tokens=16384,
				vision=True,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-3.5-turbo-0125",
				name="GPT 3.5 Turbo (0125)",
				# Translators: This is a model description
				description=_(
					"The latest GPT-3.5 Turbo model with higher accuracy at responding in requested formats and a fix for a bug which caused a text encoding issue for non-English language function calls"
				),
				context_window=16385,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4-turbo-preview",
				name="GPT 4 Turbo Preview",
				# Translators: This is a model description
				description=_(
					"Points to one of the most recent iterations of gpt-4 model"
				),
				context_window=128000,
				max_output_tokens=4096,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4-0125-preview",
				name="GPT 4 (0125) Preview",
				# Translators: This is a model description
				description=_(
					"The latest GPT-4 model intended to reduce cases of “laziness” where the model doesn’t complete a task"
				),
				context_window=128000,
				max_output_tokens=4096,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4-1106-preview",
				name="GPT 4 (1106) Preview",
				# Translators: This is a model description
				description=_(
					"GPT-4 Turbo model featuring improved instruction following, JSON mode, reproducible outputs, parallel function calling, and more"
				),
				context_window=128000,
				max_output_tokens=4096,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="gpt-4-0613",
				name="GPT 4 (0613)",
				# Translators: This is a model description
				description=_(
					"More capable than any GPT-3.5 model, able to do more complex tasks, and optimized for chat"
				),
				max_output_tokens=8192,
				max_temperature=2.0,
			),
		]

	def prepare_message_request(
		self, message: Message
	) -> ChatCompletionUserMessageParam:
		"""Prepares a message for OpenAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			OpenAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [
			ChatCompletionContentPartTextParam(
				text=message.content, type="text"
			)
		]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				image = ImageURL(url=attachment.url, detail="auto")
				content.append(
					ChatCompletionContentPartImageParam(
						image_url=image, type="image_url"
					)
				)
		return ChatCompletionUserMessageParam(
			role=message.role.value, content=content
		)

	def prepare_message_response(
		self, response: Message
	) -> ChatCompletionAssistantMessageParam:
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			OpenAI API compatible assistant message parameter.
		"""
		super().prepare_message_response(response)
		return ChatCompletionAssistantMessageParam(
			role=response.role.value,
			content=[
				ChatCompletionContentPartTextParam(
					text=response.content, type="text"
				)
			],
		)

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		stop_block_index: int | None = None,
		**kwargs,
	) -> Union[ChatCompletion, Generator[ChatCompletionChunk, None, None]]:
		"""Generates a chat completion using the OpenAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			stop_block_index: Optional index to stop processing messages at. If None, all messages are processed.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			Either a complete chat completion response or a generator for streaming
			chat completion chunks.
		"""
		super().completion(
			new_block, conversation, system_message, stop_block_index, **kwargs
		)
		model_id = new_block.model.model_id
		params = {
			"model": model_id,
			"messages": self.get_messages(
				new_block,
				conversation,
				system_message,
				stop_block_index=stop_block_index,
			),
			"stream": new_block.stream,
		}
		if model_id not in [
			"gpt-4o-search-preview",
			"gpt-4o-mini-search-preview",
		]:
			params.update(
				{"temperature": new_block.temperature, "top_p": new_block.top_p}
			)
		if new_block.max_tokens:
			params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		response = self.client.chat.completions.create(**params)
		return response

	def completion_response_with_stream(
		self, stream: Generator[ChatCompletionChunk, None, None]
	):
		"""Processes a streaming completion response.

		Args:
			stream: Generator of chat completion chunks.

		Yields:
			Content from each chunk in the stream.
		"""
		for chunk in stream:
			delta = chunk.choices[0].delta
			if delta and delta.content:
				yield delta.content

	def completion_response_without_stream(
		self, response: ChatCompletion, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Processes a non-streaming completion response.

		Args:
			response: The chat completion response.
			new_block: The message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			Updated message block containing the response.
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=response.choices[0].message.content,
		)
		return new_block

	def get_transcription(
		self, audio_file_path: str, response_format: str = "json"
	) -> str:
		"""Transcribes audio to text using OpenAI's Whisper model.

		Args:
			audio_file_path: Path to the audio file.
			response_format: Format of the response (defaults to "json").

		Returns:
			Transcription of the audio content.
		"""
		file = open(audio_file_path, "rb")
		transcription = self.client.audio.transcriptions.create(
			model="whisper-1", file=file, response_format=response_format
		)
		file.close()
		return transcription
