"""Module for MistralAI OCR functionality.

This module provides OCR (Optical Character Recognition) capabilities for the MistralAI API,
implementing document and image text extraction functionality.
"""

from __future__ import annotations

import logging
import os
import traceback
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from mistralai import Mistral
from mistralai.models import OCRResponse
from platformdirs import user_documents_dir

from basilisk.conversation.attached_file import (
	AttachmentFile,
	AttachmentFileTypes,
)
from basilisk.logger import setup_logging

if TYPE_CHECKING:
	from multiprocessing import Queue

log = logging.getLogger(__name__)


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


def _update_ocr_progress(message: str, progress: int = None, result_queue=None):
	"""Updates OCR processing progress.

	Args:
		message: Progress message to log
		progress: Optional numeric progress value
		result_queue: Queue to send progress messages
	"""
	if result_queue:
		try:
			if message:
				log.debug(message)
				result_queue.put(("message", message))
			if progress is not None:
				result_queue.put(("progress", progress))
		except Exception as e:
			log.error(f"Error updating OCR progress: {str(e)}")
	else:
		log.info(message)


def _process_url_attachment(client, attachment, result_queue=None) -> str:
	"""Process a URL-based attachment for OCR.

	Args:
		client: Mistral client instance
		attachment: The attachment to process
		result_queue: Queue for progress updates

	Returns:
		Path to the output file if successful, empty string otherwise
	"""
	path = Path(user_documents_dir()) / "basilisk_ocr"
	path.mkdir(exist_ok=True, parents=True)
	output_file = path / f"{datetime.now().isoformat().replace(':', '-')}.md"

	_update_ocr_progress(
		f"Processing OCR for URL: {attachment.location}",
		result_queue=result_queue,
	)

	result = _ocr_result(
		_ocr_process(
			client=client,
			document={"type": "document_url", "document_url": attachment.url},
			include_image_base64=True,
		),
		file_path=str(output_file),
	)

	return str(output_file) if result else ""


def _process_file_attachment(client, attachment, result_queue=None) -> str:
	"""Process a file-based attachment for OCR.

	Args:
		client: Mistral client instance
		attachment: The attachment to process
		result_queue: Queue for progress updates

	Returns:
		Path to the output file if successful, empty string otherwise
	"""
	output_file = Path(attachment.location).with_suffix(".md")
	_update_ocr_progress(
		f"Processing OCR for file: {attachment.name}", result_queue=result_queue
	)

	# Check if the file exists and is readable
	if not os.path.exists(attachment.location):
		_update_ocr_progress(
			f"Warning: File not found: {attachment.location}",
			result_queue=result_queue,
		)
		return ""

	# Upload the file for OCR processing
	with open(attachment.location, "rb") as f:
		signed_url = _ocr_upload(
			client=client, file={"file_name": attachment.name, "content": f}
		)
		log.debug(f"Signed URL: {signed_url}\n")

	# Process the uploaded file
	result = _ocr_result(
		_ocr_process(
			client=client,
			document={"type": "document_url", "document_url": signed_url},
			include_image_base64=True,
		),
		file_path=str(output_file),
	)

	return str(output_file) if result else ""


def _process_single_attachment(
	client, attachment, index, total, result_queue=None
) -> str:
	"""Process a single attachment for OCR.

	Args:
		client: Mistral client instance
		attachment: The attachment to process
		index: Current attachment index
		total: Total number of attachments
		result_queue: Queue for progress updates

	Returns:
		Path to the output file if successful, empty string otherwise
	"""
	_update_ocr_progress(
		f"Processing attachment {index + 1}/{total}: {attachment.name}",
		progress=int(100 * index / total),
		result_queue=result_queue,
	)

	try:
		if attachment.type == AttachmentFileTypes.URL:
			output_file = _process_url_attachment(
				client, attachment, result_queue
			)
		else:
			output_file = _process_file_attachment(
				client, attachment, result_queue
			)

		if output_file:
			_update_ocr_progress(
				f"OCR completed for {attachment.name}. Saved to {output_file}",
				result_queue=result_queue,
			)
			return output_file
		else:
			_update_ocr_progress(
				f"OCR failed for {attachment.name}. No text extracted.",
				result_queue=result_queue,
			)
			return ""

	except Exception as e:
		error_trace = traceback.format_exc()
		_update_ocr_progress(
			f"Error processing attachment {attachment.name}: {str(e)}",
			result_queue=result_queue,
		)
		log.error(
			f"Error processing attachment {attachment.name}: {str(e)}\n{error_trace}"
		)
		return ""


def handle_ocr(
	api_key: str,
	base_url: str,
	attachments: list[AttachmentFile],
	cancel_flag=None,
	result_queue: Queue = None,
	log_level=logging.INFO,
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
	try:
		setup_logging(log_level)
		# Create a new client in the subprocess
		_update_ocr_progress(
			"Initializing OCR processor...", result_queue=result_queue
		)
		client = Mistral(api_key=api_key, server_url=base_url)

		if not attachments:
			return "error", "No attachments for OCR processing"

		total_attachments = len(attachments)
		output_files = []

		for i, attachment in enumerate(attachments):
			# Check for cancellation
			if cancel_flag and cancel_flag.value:
				return "result", output_files

			output_file = _process_single_attachment(
				client, attachment, i, total_attachments, result_queue
			)
			if output_file:
				output_files.append(output_file)

		# Final update
		_update_ocr_progress(
			f"OCR completed for {len(output_files)} of {total_attachments} attachments",
			progress=100,
			result_queue=result_queue,
		)
		return output_files

	except Exception as e:
		error_trace = traceback.format_exc()
		log.error(f"OCR process error: {str(e)}\n{error_trace}")
		return "error", f"OCR process error: {str(e)}"
