from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import google.generativeai as genai

from basilisk.conversation import (
	Conversation,
	ImageFile,
	ImageFileTypes,
	Message,
	MessageBlock,
	MessageRoleEnum,
)

from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

if TYPE_CHECKING:
	from basilisk.config import Account

logger = logging.getLogger(__name__)


class GeminiEngine(BaseEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	def __init__(self, account: Account) -> None:
		super().__init__(account)
		genai.configure(api_key=self.account.api_key.get_secret_value())

	@property
	def client(self) -> None:
		"""
		Property to return the client object
		"""
		raise NotImplementedError("Getting client not supported for Gemini")

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		# See <https://ai.google.dev/gemini-api/docs/models/gemini?hl=en>
		return [
			ProviderAIModel(
				id="gemini-2.0-flash-exp",
				# Translators: This is a model description
				description=_(
					"Next generation features, speed, and multimodal generation for a diverse variety of tasks"
				),
				context_window=1048576,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-flash-latest",
				# Translators: This is a model description
				description=_(
					'Fast and versatile multimodal model for scaling across diverse tasks'
				),
				context_window=1048576,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-pro-latest",
				# Translators: This is a model description
				description=_(
					"Mid-size multimodal model that supports up to 1 million tokens"
				),
				context_window=2097152,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-flash",
				# Translators: This is a model description
				description=_(
					"Fast and versatile multimodal model for scaling across diverse tasks"
				),
				context_window=1048576,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-pro",
				# Translators: This is a model description
				description=_(
					"Mid-size multimodal model that supports up to 1 million tokens"
				),
				context_window=2097152,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
		]

	def convert_role(self, role: MessageRoleEnum) -> str:
		if role == MessageRoleEnum.ASSISTANT:
			return "model"
		elif role == MessageRoleEnum.USER:
			return "user"
		elif role == MessageRoleEnum.SYSTEM:
			raise NotImplementedError(
				"System role must be set on the model instance"
			)

	def convert_image(self, image: ImageFile) -> genai.protos.Part:
		if image.type == ImageFileTypes.IMAGE_URL:
			raise NotImplementedError("Image URL not supported")
		with image.send_location.open("rb") as f:
			blob = genai.protos.Blob(mime_type=image.mime_type, data=f.read())
		return genai.protos.Part(inline_data=blob)

	def convert_message_content(self, message: Message) -> genai.protos.Content:
		role = self.convert_role(message.role)
		parts = [genai.protos.Part(text=message.content)]
		if message.attachments:
			for attachment in message.attachments:
				parts.append(self.convert_image(attachment))
		return genai.protos.Content(role=role, parts=parts)

	prepare_message_request = convert_message_content
	prepare_message_response = convert_message_content

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> genai.types.GenerateContentResponse:
		super().completion(new_block, conversation, system_message, **kwargs)
		model = genai.GenerativeModel(
			model_name=new_block.model.model_id,
			system_instruction=system_message.content
			if system_message
			else None,
		)

		generation_config = genai.GenerationConfig(
			max_output_tokens=new_block.max_tokens
			if new_block.max_tokens
			else None,
			temperature=new_block.temperature,
			top_p=new_block.top_p,
		)
		return model.generate_content(
			contents=self.get_messages(new_block, conversation, None),
			generation_config=generation_config,
			stream=new_block.stream,
		)

	def completion_response_without_stream(
		self,
		response: genai.types.GenerateContentResponse,
		new_block: MessageBlock,
		**kwargs,
	) -> MessageBlock:
		new_block.response = Message(
			role=MessageRoleEnum.ASSISTANT, content=response.text
		)
		return new_block

	def completion_response_with_stream(
		self, stream: genai.types.GenerateContentResponse, **kwargs
	):
		for chunk in stream:
			chunk_text = chunk.text
			if chunk_text:
				yield chunk_text
