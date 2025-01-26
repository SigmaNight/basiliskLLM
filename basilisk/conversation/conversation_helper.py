from __future__ import annotations

import logging
import shutil
import zipfile
from typing import TYPE_CHECKING

from fsspec.implementations.zip import ZipFileSystem
from upath import UPath

from .image_model import ImageFile, ImageFileTypes

if TYPE_CHECKING:
	from .conversation_model import Conversation


log = logging.getLogger(__name__)

PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."


def save_attachments(
	attachments: list[ImageFile], attachment_path: str, fs: ZipFileSystem
):
	attachment_mapping = {}
	for attachment in attachments:
		if attachment.type == ImageFileTypes.IMAGE_URL:
			continue
		new_location = f"{attachment_path}/{attachment.location.name}"
		with attachment.location.open(mode="rb") as attachment_file:
			with fs.open(new_location, mode="wb") as new_file:
				shutil.copyfileobj(attachment_file, new_file)
		attachment_mapping[attachment.location] = new_location
	return attachment_mapping


def create_conv_main_file(conversation: Conversation, fs: ZipFileSystem):
	base_path = "attachments"
	attachment_mapping = {}
	for block in conversation.messages:
		attachments = block.request.attachments
		if not attachments:
			continue
		fs.makedirs(base_path, exist_ok=True)
		attachment_mapping |= save_attachments(attachments, base_path, fs)
	with fs.open("conversation.json", mode="w", encoding="utf-8") as conv_file:
		conv_file.write(
			conversation.model_dump_json(
				context={"attachment_mapping": attachment_mapping}
			)
		)


def restore_attachments(attachments: list[ImageFile], storage_path: UPath):
	for attachment in attachments:
		if attachment.type == ImageFileTypes.IMAGE_URL:
			continue
		new_path = storage_path / attachment.location.name
		with attachment.location.open(mode="rb") as attachment_file:
			with new_path.open(mode="wb") as new_file:
				shutil.copyfileobj(attachment_file, new_file)
		attachment.location = new_path


def read_conv_main_file(
	model_cls: Conversation, conv_main_path: UPath, attachments_path: UPath
) -> Conversation:
	conversation = None
	with conv_main_path.open(mode="r", encoding="utf-8") as conv_file:
		conversation = model_cls.model_validate_json(
			json_data=conv_file.read(),
			context={"root_path": conv_main_path.parent},
		)
	for block in conversation.messages:
		attachments = block.request.attachments
		if not attachments:
			continue
		restore_attachments(attachments, attachments_path)
	return conversation


def create_bskc_file(conversation: Conversation, file_path: str):
	"""Save a conversation to a Basilisk Conversation file."""
	with open(file_path, mode="w+b") as bskc_file:
		fs = ZipFileSystem(
			fo=bskc_file, mode="w", compression=zipfile.ZIP_STORED
		)
		create_conv_main_file(conversation, fs)
		fs.close()


def open_bskc_file(
	model_cls: Conversation, file_path: str, base_storage_path: UPath
) -> Conversation:
	"""Open a Basilisk Conversation file."""
	with open(file_path, mode="r+b") as bskc_file:
		if not zipfile.is_zipfile(bskc_file):
			raise zipfile.BadZipFile("The baskc file must be a zip archive.")
		zip_path = UPath("zip://", fo=bskc_file, mode="r")
		conv_main_math = zip_path / "conversation.json"
		if not conv_main_math.exists():
			raise FileNotFoundError(
				"The baskc file must contain a conversation.json file."
			)
		attachments_path = base_storage_path / "attachments"
		return read_conv_main_file(model_cls, conv_main_math, attachments_path)
