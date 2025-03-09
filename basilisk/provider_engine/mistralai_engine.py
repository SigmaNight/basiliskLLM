"""Module for MistralAI API integration.

This module provides the MistralAIEngine class for interacting with the MistralAI API,
implementing capabilities for text and image generation/processing.
"""

from __future__ import annotations

import logging
from datetime import datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Any, Generator

from mistralai import Mistral
from mistralai.models import (
	ChatCompletionResponse,
	CompletionEvent,
	OCRResponse,
)
from mistralai.utils.eventstreaming import EventStream
from platformdirs import user_documents_dir

from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.conversation.attached_file import (
	AttachmentFile,
	AttachmentFileTypes,
)

if TYPE_CHECKING:
	from multiprocessing import Queue

	from basilisk.config import Account
from .base_engine import BaseEngine, ProviderAIModel, ProviderCapability

log = logging.getLogger(__name__)


class MistralAIEngine(BaseEngine):
	"""Engine implementation for MistralAI API integration.

	Provides functionality for interacting with MistralAI's models, supporting text,
	image and document capabilities.

	Attributes:
		capabilities: Set of supported capabilities including text, image, STT, and TTS.
	"""

	capabilities: set[ProviderCapability] = {
		ProviderCapability.IMAGE,
		ProviderCapability.DOCUMENT,
		ProviderCapability.OCR,
		ProviderCapability.TEXT,
	}
	supported_attachment_formats: set[str] = {
		"image/gif",
		"image/jpeg",
		"image/png",
		"image/webp",
		"application/pdf",
	}

	def __init__(self, account: Account) -> None:
		"""Initializes the MistralAI engine.

		Args:
			account: Account configuration for the MistralAI provider.
		"""
		super().__init__(account)

	@cached_property
	def client(self) -> Mistral:
		"""Creates and configures the Mistral client.

		Returns:
			Configured MistralAI client instance.
		"""
		super().client
		return Mistral(
			api_key=self.account.api_key.get_secret_value(),
			server_url=self.account.custom_base_url
			or self.account.provider.base_url,
		)

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""Retrieves available MistralAI models.

		Returns:
			List of supported MistralAI models with their configurations.
		"""
		super().models
		log.debug("Getting MistralAI models")
		# See <https://docs.mistral.ai/getting-started/models/models_overview/>
		return [
			ProviderAIModel(
				id="ministral-3b-latest",
				name="Ministral 3B",
				# Translators: This is a model description
				description=_("World’s best edge model"),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="ministral-8b-latest",
				name="Ministral 8B",
				# Translators: This is a model description
				description=_(
					"Powerful edge model with extremely high performance/price ratio"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="mistral-large-latest",
				name="Mistral Large",
				# Translators: This is a model description
				description=_(
					"Our top-tier reasoning model for high-complexity tasks with the latest version v2 released July 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-large-latest",
				name="Pixtral Large",
				# Translators: This is a model description
				description=_(
					"Our frontier-class multimodal model released November 2024"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="mistral-small-latest",
				name="Mistral Small",
				# Translators: This is a model description
				description=_(
					"Our latest enterprise-grade small model with the lastest version v2 released September 2024"
				),
				context_window=32000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="codestral-latest",
				name="Codestral",
				# Translators: This is a model description
				description=_(
					"Our cutting-edge language model for coding released May 2024"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="pixtral-12b-2409",
				name="Pixtral",
				# Translators: This is a model description
				description=_(
					"A 12B model with image understanding capabilities in addition to text"
				),
				context_window=131000,
				max_temperature=1.0,
				default_temperature=0.7,
				vision=True,
			),
			ProviderAIModel(
				id="open-mistral-nemo",
				name="Mistral Nemo",
				# Translators: This is a model description
				description=_(
					"A 12B model built with the partnership with Nvidia. It is easy to use and a drop-in replacement in any system using Mistral 7B that it supersedes"
				),
				context_window=128000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
			ProviderAIModel(
				id="open-codestral-mamba",
				name="Codestral Mamba",
				# Translators: This is a model description
				description=_(
					"A Mamba 2 language model specialized in code generation"
				),
				context_window=256000,
				max_temperature=1.0,
				default_temperature=0.7,
			),
		]

	def prepare_message_request(self, message: Message) -> dict[str, Any]:
		"""Prepares a message for MistralAI API request.

		Args:
			message: Message to be prepared.

		Returns:
			MistralAI API compatible message parameter.
		"""
		super().prepare_message_request(message)
		content = [{"type": "text", "text": message.content}]
		if getattr(message, "attachments", None):
			for attachment in message.attachments:
				mime_type = attachment.mime_type
				if mime_type.startswith("image/"):
					content.append(
						{"type": "image_url", "image_url": attachment.url}
					)
				else:
					content.append(
						{"type": "document_url", "document_url": attachment.url}
					)
		return {"role": message.role.value, "content": content}

	def prepare_message_response(self, response: Message) -> dict[str, Any]:
		"""Prepares an assistant message response.

		Args:
			response: Response message to be prepared.

		Returns:
			MistralAI API compatible assistant message parameter.
		"""
		super().prepare_message_response(response)
		return {
			"role": response.role.value,
			"content": [{"type": "text", "text": response.content}],
		}

	def completion(
		self,
		new_block: MessageBlock,
		conversation: Conversation,
		system_message: Message | None,
		**kwargs,
	) -> ChatCompletionResponse | EventStream[CompletionEvent]:
		"""Generates a chat completion using the MistralAI API.

		Args:
			new_block: The message block containing generation parameters.
			conversation: The conversation history context.
			system_message: Optional system message to guide the AI's behavior.
			**kwargs: Additional keyword arguments for the API request.

		Returns:
			The chat completion response.
		"""
		super().completion(new_block, conversation, system_message, **kwargs)
		params = {
			"model": new_block.model.model_id,
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
		if new_block.stream:
			return self.client.chat.stream(**params)
		return self.client.chat.complete(**params)

	def completion_response_with_stream(
		self, stream: Generator[CompletionEvent, None, None]
	):
		"""Processes a streaming completion response.

		Args:
			stream: Generator of chat completion chunks.

		Yields:
			Content from each chunk in the stream.
		"""
		for chunk in stream:
			delta = chunk.data.choices[0].delta
			if delta and delta.content:
				yield delta.content

	def completion_response_without_stream(
		self,
		response: ChatCompletionResponse,
		new_block: MessageBlock,
		**kwargs,
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

	@staticmethod
	def _ocr_upload(client: Mistral, file: dict[str, Any]) -> str:
		"""Uploads a file for OCR processing.

		Args:
			client: Mistral client instance.
			file: The file to upload.

		Returns:
			The signed URL for the uploaded file.
		"""
		uploaded_pdf = client.files.upload(file=file, purpose="ocr")
		return client.files.get_signed_url(file_id=uploaded_pdf.id).url

	@staticmethod
	def _ocr_process(
		client: Mistral,
		document: dict[str, Any],
		include_image_base64: bool = True,
		**kwargs,
	) -> OCRResponse:
		"""Processes a document for OCR.

		Args:
			client: Mistral client instance
			document: The document to process.
			include_image_base64: Whether to include image base64.
			**kwargs: Additional keyword arguments.

		Returns:
			The OCR response.
		"""
		return client.ocr.process(
			model="mistral-ocr-latest",
			document=document,
			include_image_base64=include_image_base64,
			**kwargs,
		)

	@staticmethod
	def _ocr_result(ocr_response: OCRResponse, file_path: str) -> bool:
		"""Extracts text from the OCR response.

		Args:
			ocr_response: The OCR response.
			file_path: The file path to save the extracted text.

		Returns:
			True if text was saved to a file, False otherwise.
		"""
		if not ocr_response:
			return False

		parent_dir = Path(file_path).parent
		parent_dir.mkdir(exist_ok=True, parents=True)

		with open(file_path, "w", encoding="UTF-8") as file:
			for page_number, page in enumerate(ocr_response.pages, start=1):
				file.write(page.markdown)
				file.write(f"\n\n_----------_{page_number + 1}\n\n")
		return True

	@staticmethod
	def handle_ocr(
		api_key: str,
		base_url: str,
		attachments: list[AttachmentFile],
		cancel_flag=None,
		result_queue: Queue = None,
	) -> tuple[str, Any]:
		"""Extracts text from images using OCR.

		Args:
			api_key: The API key for the MistralAI account
			base_url: The base URL for the MistralAI API
			attachments: List of attachments to extract text from
			cancel_flag: Flag to cancel the operation
			result_queue: Queue to send progress messages

		Returns:
			List of file paths containing the extracted text.
		"""
		# Import required modules inside the function for better multiprocessing compatibility
		import os
		import sys
		from pathlib import Path

		from mistralai import Mistral

		# Helper to safely update progress through queue
		def update_progress(message, progress=None):
			sys.stdout.write(f"Progress: {message}\n")
			if result_queue:
				try:
					if message:
						result_queue.put(("message", message))
					if progress is not None:
						result_queue.put(("progress", progress))
				except Exception as e:
					sys.stderr.write(
						f"Error sending progress update: {str(e)}\n"
					)

		# Check if process should be canceled
		def should_cancel():
			return cancel_flag and cancel_flag.value

		try:
			# Create a new client in the subprocess
			update_progress("Initializing OCR processor...")
			client = Mistral(api_key=api_key, server_url=base_url)

			output_files = []
			if not attachments:
				return "error", "No attachments for OCR processing"

			total_attachments = len(attachments)

			for i, attachment in enumerate(attachments):
				# Check for cancellation
				if should_cancel():
					return "result", output_files

				update_progress(
					f"Processing attachment {i + 1}/{total_attachments}: {attachment.name}"
				)
				update_progress(None, int(100 * i / total_attachments))

				try:
					output_file = ""
					if attachment.type == AttachmentFileTypes.URL:
						path = Path(user_documents_dir()) / "basilisk_ocr"
						path.mkdir(exist_ok=True, parents=True)
						output_file = (
							path
							/ f"{datetime.now().isoformat().replace(':', '-')}.md"
						)

						update_progress(
							f"Processing OCR for URL: {attachment.location}"
						)

						# Process URL-based attachment
						result = MistralAIEngine._ocr_result(
							MistralAIEngine._ocr_process(
								client=client,
								document={
									"type": "document_url",
									"document_url": attachment.url,
								},
								include_image_base64=True,
							),
							file_path=str(output_file),
						)
					else:
						# For file-based attachments
						output_file = Path(attachment.location).with_suffix(
							".md"
						)
						update_progress(
							f"Processing OCR for file: {attachment.name}"
						)

						# Check if the file exists and is readable
						if not os.path.exists(attachment.location):
							update_progress(
								f"Warning: File not found: {attachment.location}"
							)
							continue

						# Upload the file for OCR processing
						with open(attachment.location, "rb") as f:
							signed_url = MistralAIEngine._ocr_upload(
								client=client,
								file={
									"file_name": attachment.name,
									"content": f,
								},
							)
							sys.stdout.write(f"Signed URL: {signed_url}\n")

						# Process the uploaded file
						result = MistralAIEngine._ocr_result(
							MistralAIEngine._ocr_process(
								client=client,
								document={
									"type": "document_url",
									"document_url": signed_url,
								},
								include_image_base64=True,
							),
							file_path=str(output_file),
						)

					# Record successful result
					if result:
						output_files.append(str(output_file))
						update_progress(
							f"OCR completed for {attachment.name}. Saved to {output_file}"
						)
					else:
						update_progress(
							f"OCR failed for {attachment.name}. No text extracted."
						)

				except Exception as e:
					import traceback

					error_trace = traceback.format_exc()
					update_progress(
						f"Error processing attachment {attachment.name}: {str(e)}"
					)
					sys.stderr.write(f"OCR error: {str(e)}\n{error_trace}\n")

			# Final update
			update_progress(
				f"OCR completed for {len(output_files)} of {total_attachments} attachments",
				100,
			)
			return output_files

		except Exception as e:
			import traceback

			error_trace = traceback.format_exc()
			sys.stderr.write(f"OCR process error: {str(e)}\n{error_trace}\n")
			return "error", f"OCR process error: {str(e)}"
