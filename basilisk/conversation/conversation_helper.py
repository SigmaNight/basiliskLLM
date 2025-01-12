from __future__ import annotations

import logging
import zipfile
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator
from upath import UPath

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


def create_conv_main_file(conversation: Conversation, zip_base_path: UPath):
	conv_main_path = zip_base_path / "conversation.json"
	with conv_main_path.open(mode="w") as conv_file:
		conv_json = conversation.model_dump_json()
		conv_file.write(conv_json)


def read_conv_main_file(
	model_cls: Conversation, conv_file: UPath
) -> Conversation:
	with conv_file.open(mode="r") as conv_file:
		return model_cls.model_validate_json(conv_file.read())


def create_bskc_file(conversation: Conversation, file_path: str):
	"""Save a conversation to a Basilisk Conversation file."""
	with open(file_path, mode="w+b") as bskc_file:
		zip_base_path = UPath(
			"zip://.", mode="w", fo=bskc_file, compression=zipfile.ZIP_STORED
		)
		create_conv_main_file(conversation, zip_base_path)
		zip_base_path.fs.close()


def open_bskc_file(model_cls: Conversation, file_path: str) -> Conversation:
	"""Open a Basilisk Conversation file."""
	with open(file_path, mode="r+b") as bskc_file:
		if not zipfile.is_zipfile(bskc_file):
			raise zipfile.BadZipFile("The baskc file must be a zip archive.")
		zip_base_path = UPath("zip://.", mode="r", fo=bskc_file)
		conv_main_path = zip_base_path / "conversation.json"
		if not conv_main_path.exists():
			raise FileNotFoundError(
				"The baskc file must contain a conversation.json file."
			)
		return read_conv_main_file(model_cls, conv_main_path)
