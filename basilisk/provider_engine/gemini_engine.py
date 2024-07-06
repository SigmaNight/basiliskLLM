from __future__ import annotations
import logging
import google.generativeai as genai
from functools import cached_property
from typing import TYPE_CHECKING, Any


from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	TextMessageContent,
	ImageUrlMessageContent,
)
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

if TYPE_CHECKING:
	from basilisk.account import Account

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
		return [
			ProviderAIModel(
				id="gemini-1.0-pro",
				# Translators: This is a ProviderAIModel description
				description=_(
					"The best model for scaling across a wide range of tasks"
				),
				context_window=30720,
				max_output_tokens=2048,
				default_temperature=0.9,
			),
			ProviderAIModel(
				id="gemini-1.0-pro-latest",
				# Translators: This is a ProviderAIModel description
				description=_(
					"The best model for scaling across a wide range of tasks. This is the latest model."
				),
				context_window=30720,
				max_output_tokens=2048,
				default_temperature=0.9,
			),
			ProviderAIModel(
				id="gemini-1.0-pro-vision-latest",
				# Translators: This is a ProviderAIModel description
				description=_(
					'The best image understanding model to handle a broad range of applications'
				),
				context_window=12288,
				max_output_tokens=4096,
				vision=True,
				default_temperature=0.4,
			),
			ProviderAIModel(
				id="gemini-1.5-flash",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Fast and versatile multimodal model for scaling across diverse tasks"
				),
				context_window=1048576,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-flash-latest",
				# Translators: This is a ProviderAIModel description
				description=_(
					'Fast and versatile multimodal model for scaling across diverse tasks'
				),
				context_window=1048576,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-pro",
				# Translators: This is a ProviderAIModel description
				description=_(
					"Mid-size multimodal model that supports up to 1 million tokens"
				),
				context_window=2097152,
				max_output_tokens=8192,
				vision=True,
				default_temperature=1.0,
			),
			ProviderAIModel(
				id="gemini-1.5-pro-latest",
				# Translators: This is a ProviderAIModel description
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

	def convert_message_content(
		self, message: Message
	) -> list[genai.protos.Part]:
		parts = []
		for content in message.content:
			if isinstance(content, TextMessageContent):
				parts.append(genai.protos.Part(text=content.text))
			elif isinstance(content, ImageUrlMessageContent):
				parts.append(genai.protos.Part(inline_data=content.url))
			elif isinstance(content, str):
				parts.append(genai.protos.Part(text=content))
			else:
				raise NotImplementedError(
					f"Content type {type(content)} not supported"
				)
		return parts

	def get_messages(
		self, new_block: MessageBlock, conversation: Conversation, **kwargs
	) -> list[genai.types.ContentsType]:
		"""
		Get messages
		"""
		messages = []
		for message_block in conversation.messages:
			if not message_block.response:
				continue
			messages.extend(
				[
					genai.protos.Content(
						role=self.convert_role(message_block.request.role),
						parts=self.convert_message_content(
							message_block.request
						),
					),
					genai.protos.Content(
						role=self.convert_role(message_block.response.role),
						parts=self.convert_message_content(
							message_block.response
						),
					),
				]
			)
		messages.append(
			genai.protos.Content(
				role=self.convert_role(new_block.request.role),
				parts=self.convert_message_content(new_block.request),
			)
		)
		return messages

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> genai.types.GenerateContentResponse:
		super().completion(new_block, conversation, system_message, **kwargs)
		model = genai.GenerativeModel(
			model_name=new_block.model.id,
			system_instruction=system_message.content
			if system_message
			else None,
		)
		generation_config = None
		"""
		generation_config = genai.GenerationConfig(
			max_output_tokens=new_block.max_tokens,
			temperature=new_block.temperature,
			top_p=new_block.top_p,
		)
		"""
		return model.generate_content(
			contents=self.get_messages(new_block, conversation),
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
			role=MessageRoleEnum.ASSISTANT,
			content=self.normalize_linesep(response.text),
		)
		return new_block

	def completion_response_with_stream(
		self, stream: Any, new_block: MessageBlock, **kwargs
	) -> MessageBlock:
		raise NotImplementedError("Stream completion not supported for Gemini")
