from __future__ import annotations

import logging
import zipfile
from typing import TYPE_CHECKING

from fsspec.implementations.zip import ZipFileSystem
from pydantic import BaseModel, Field, field_validator

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


def create_conv_main_file(conversation: Conversation, fs: ZipFileSystem):
	with fs.open("conversation.json", mode="w") as conv_file:
		conv_json = conversation.model_dump_json()
		conv_file.write(conv_json)


def create_bskc_file(conversation: Conversation, file_path: str):
	"""Save a conversation to a Basilisk Conversation file."""
	with open(file_path, mode="w+b") as bskc_file:
		fs = ZipFileSystem(
			fo=bskc_file, mode="w", compression=zipfile.ZIP_STORED
		)
		create_conv_main_file(conversation, fs)
		fs.close()
