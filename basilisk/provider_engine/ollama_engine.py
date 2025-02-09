import json
import logging
from functools import cached_property
from typing import Iterator

from ollama import ChatResponse, Client

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.decorators import measure_time

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class OllamaEngine(BaseEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	@cached_property
	@measure_time
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
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
		"""
		Get client
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
		"""
		Completion
		"""
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.model_id,
			"messages": self.get_messages(
				new_block, conversation, system_message
			),
			# "temperature": new_block.temperature,
			# "top_p": new_block.top_p,
			"stream": new_block.stream,
		}
		# if new_block.max_tokens:
		# params["max_tokens"] = new_block.max_tokens
		params.update(kwargs)
		return self.client.chat(**params)

	def prepare_message_request(self, message: Message):
		super().prepare_message_request(message)
		images = []
		if message.attachments:
			for attachment in message.attachments:
				images.append(attachment.location)
		return {
			"role": message.role.value,
			"content": message.content,
			"images": images,
		}

	prepare_message_response = prepare_message_request

	def completion_response_with_stream(self, stream):
		for chunk in stream:
			content = chunk.get("message", {}).get("content")
			if content:
				yield content

	def completion_response_without_stream(
		self, response, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT,
			content=response["message"]["content"],
		)
		return new_block
