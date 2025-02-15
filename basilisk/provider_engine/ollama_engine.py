"""Ollama provider engine implementation."""

import json
import logging
from functools import cached_property
from typing import Iterator

from ollama import ChatResponse, Client

from basilisk.conversation import (
	Conversation,
	ImageFileTypes,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.decorators import measure_time

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class OllamaEngine(BaseEngine):
	"""Engine implementation for Ollama API integration."""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	@cached_property
	@measure_time
	def models(self) -> list[ProviderAIModel]:
		"""Get Ollama models.

		Returns:
			A list of provider AI models.
		"""
		models = []
		models_list = self.client.list().models
		for model in models_list:
			info = self.client.show(model.model)
			context_length = 0
			description = json.dumps(info.modelinfo, indent=2)
			description += f"\n\n{info.license}"
			for k, v in info.modelinfo.items():
				if k.endswith("context_length"):
					context_length = v
			models.append(
				ProviderAIModel(
					id=model.model,
					name=model.model,
					description=description,
					context_window=context_length,
					max_output_tokens=0,
					max_temperature=2,
					default_temperature=1,
					vision=True,
				)
			)

		return models

	@cached_property
	def client(self) -> Client:
		"""Get Ollama client.

		Returns:
			The Ollama client instance.
		"""
		base_url = self.account.custom_base_url or str(
			self.account.provider.base_url
		)
		log.info(f"Base URL: {base_url}")
		return Client(host=base_url)

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> ChatResponse | Iterator[ChatResponse]:
		"""Get completion from Ollama.

		Args:
			new_block: The new message block.
			conversation: The conversation instance.
			system_message: The system message, if any.
			**kwargs: Additional keyword arguments.

		Returns:
			The chat response or an iterator of chat responses.
		"""
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.model_id,
			"messages": self.get_messages(
				new_block, conversation, system_message
			),
			"stream": new_block.stream,
		}
		params.update(kwargs)
		return self.client.chat(**params)

	def prepare_message_request(self, message: Message):
		"""Prepare message request for Ollama.

		Args:
			message: The message to prepare.

		Returns:
			The prepared message request.
		"""
		super().prepare_message_request(message)
		images = []
		if message.attachments:
			for attachment in message.attachments:
				if attachment.type == ImageFileTypes.IMAGE_URL:
					log.warning(
						f"Received unsupported image type: {attachment.type}, {attachment.location}"
					)
					raise NotImplementedError(
						"images URL are not supported for Ollama"
					)
				images.append(attachment.encode_image())
		return {
			"role": message.role.value,
			"content": message.content,
			"images": images,
		}

	prepare_message_response = prepare_message_request

	def completion_response_with_stream(self, stream):
		"""Process a streaming completion response.

		Args:
			stream: The stream of chat completion responses.

		Returns:
			An iterator of the completion response content.
		"""
		for chunk in stream:
			content = chunk.get("message", {}).get("content")
			if content:
				yield content

	def completion_response_without_stream(
		self, response, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		"""Process a non-streaming completion response.

		Args:
			response: The chat completion response.
			new_block: The message block to update with the response.
			**kwargs: Additional keyword arguments.

		Returns:
			The updated message block with the response.
		"""
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=response["message"]["content"],
		)
		return new_block
