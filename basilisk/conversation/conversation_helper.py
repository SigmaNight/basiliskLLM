from __future__ import annotations

import logging
import shutil
import zipfile
from typing import TYPE_CHECKING

from fsspec.implementations.zip import ZipFileSystem
from pydantic import BaseModel, Field, field_validator

from .image_model import ImageFile, ImageFileTypes

if TYPE_CHECKING:
	from basilisk.provider import Provider

	from .conversation_model import Conversation


log = logging.getLogger(__name__)

PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."


class AIModelInfo(BaseModel):
	provider_id: str = Field(pattern=r"^[a-zA-Z]+$")
	model_id: str = Field(pattern=r"^.+$")

	@staticmethod
	def get_provider_by_id(provider_id: str) -> Provider:
		from basilisk.provider import get_provider

		return get_provider(id=provider_id)

	@field_validator("provider_id", mode="after")
	@classmethod
	def provider_must_exist(cls, value: str) -> str:
		cls.get_provider_by_id(value)
		return value

	@property
	def provider(self) -> Provider:
		return self.get_provider_by_id(self.provider_id)


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


def read_conv_main_file(
	model_cls: Conversation, fs: ZipFileSystem
) -> Conversation:
	with fs.open("conversation.json", mode="r") as conv_file:
		return model_cls.model_validate_json(conv_file.read())


def create_bskc_file(conversation: Conversation, file_path: str):
	"""Save a conversation to a Basilisk Conversation file."""
	with open(file_path, mode="w+b") as bskc_file:
		fs = ZipFileSystem(
			fo=bskc_file, mode="w", compression=zipfile.ZIP_STORED
		)
		create_conv_main_file(conversation, fs)
		fs.close()


def open_bskc_file(model_cls: Conversation, file_path: str) -> Conversation:
	"""Open a Basilisk Conversation file."""
	with open(file_path, mode="r+b") as bskc_file:
		if not zipfile.is_zipfile(bskc_file):
			raise zipfile.BadZipFile("The baskc file must be a zip archive.")
		fs = ZipFileSystem(fo=bskc_file, mode="r")
		if not fs.exists("conversation.json"):
			raise FileNotFoundError(
				"The baskc file must contain a conversation.json file."
			)
		return read_conv_main_file(model_cls, fs)
