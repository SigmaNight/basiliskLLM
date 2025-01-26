from __future__ import annotations

import logging
import shutil
import zipfile
from typing import TYPE_CHECKING

from fsspec.implementations.zip import ZipFileSystem
from upath import UPath

from basilisk.config import conf
from basilisk.decorators import measure_time

from .image_model import ImageFile, ImageFileTypes

if TYPE_CHECKING:
	from .conversation_model import Conversation


log = logging.getLogger(__name__)

PROMPT_TITLE = "Generate a concise, relevant title in the conversation's main language based on the topics and context. Max 70 characters. Do not surround the text with quotation marks."


def save_attachments(
	attachments: list[ImageFile], attachment_path: str, fs: ZipFileSystem
):
	"""
	Save image attachments to a specified path within a zip file system.

	This function copies image attachments from their original locations to a new location
	in a zip file system, skipping URL-based images. It creates a mapping of original
	attachment locations to their new locations within the zip file.

	Parameters:
	    attachments (list[ImageFile]): A list of image file attachments to be saved.
	    attachment_path (str): The base path within the zip file system where attachments
	                           will be stored.
	    fs (ZipFileSystem): The zip file system where attachments will be copied.

	Returns:
	    dict: A mapping of original attachment locations to their new locations in the
	          zip file system.

	Notes:
	    - Attachments with type IMAGE_URL are skipped and not copied.
	    - Uses shutil.copyfileobj for efficient file copying.
	"""
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
	"""
	Create the main conversation file within a zip archive.

	This function processes a conversation by saving its attachments and writing the conversation data to a JSON file. It handles multiple messages with attachments, creating a mapping of original to new attachment locations.

	Parameters:
	    conversation (Conversation): The conversation object to be saved
	    fs (ZipFileSystem): The zip file system where the conversation will be stored

	Notes:
	    - Creates an "attachments" directory in the zip file if it doesn't exist
	    - Saves attachments for each message that contains them
	    - Writes the conversation data to "conversation.json" with an attachment mapping context
	    - Skips messages without attachments
	"""
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
	"""
	Restore image attachments to a specified storage path and optionally resize them.

	Parameters:
	    attachments (list[ImageFile]): A list of image file attachments to restore.
	    storage_path (UPath): The destination path where attachments will be saved.

	Details:
	    - Skips attachments of type IMAGE_URL
	    - Copies each attachment file to the new storage location
	    - Updates the attachment's location to the new path
	    - Optionally resizes images based on configuration settings
	    - Uses configuration for maximum width, height, and image quality

	Side Effects:
	    - Modifies the location of each processed attachment
	    - Creates new files in the specified storage path
	    - May resize images in-place if resize configuration is enabled
	"""
	for attachment in attachments:
		if attachment.type == ImageFileTypes.IMAGE_URL:
			continue
		new_path = storage_path / attachment.location.name
		with attachment.location.open(mode="rb") as attachment_file:
			with new_path.open(mode="wb") as new_file:
				shutil.copyfileobj(attachment_file, new_file)
		attachment.location = new_path
		if conf().images.resize:
			attachment.resize(
				storage_path,
				conf().images.max_width,
				conf().images.max_height,
				conf().images.quality,
			)


def read_conv_main_file(
	model_cls: Conversation, conv_main_path: UPath, attachments_path: UPath
) -> Conversation:
	"""
	Read a conversation main file and restore its attachments.

	Reads a conversation JSON file from the specified path and validates it against the provided model class.
	Restores any image attachments found in the conversation messages to the specified attachments path.

	Parameters:
	    model_cls (Conversation): The conversation model class used for JSON validation
	    conv_main_path (UPath): Path to the conversation main JSON file
	    attachments_path (UPath): Base path where attachments will be restored

	Returns:
	    Conversation: The validated conversation with restored attachments

	Raises:
	    ValidationError: If the JSON data does not match the model class structure
	"""
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


@measure_time
def create_bskc_file(conversation: Conversation, file_path: str):
	"""
	Save a conversation to a Basilisk Conversation (.bskc) file.

	This function creates a Basilisk Conversation file by saving the conversation data and its attachments in a zip archive. The file is created with no compression to preserve the original file sizes.

	Parameters:
	    conversation (Conversation): The conversation object to be saved
	    file_path (str): The file path where the Basilisk Conversation file will be created

	Notes:
	    - The file is opened in binary write mode
	    - Attachments are saved alongside the conversation JSON data
	    - The zip file uses ZIP_STORED compression method for no compression
	"""
	with open(file_path, mode="w+b") as bskc_file:
		fs = ZipFileSystem(
			fo=bskc_file, mode="w", compression=zipfile.ZIP_STORED
		)
		create_conv_main_file(conversation, fs)
		fs.close()


@measure_time
def open_bskc_file(
	model_cls: Conversation, file_path: str, base_storage_path: UPath
) -> Conversation:
	"""
	Open a Basilisk Conversation file and restore its contents.

	This function validates and reads a Basilisk Conversation file (.bskc) from the specified file path, ensuring it is a valid zip archive containing a conversation.json file.

	Parameters:
	    model_cls (Conversation): The conversation model class used for instantiation
	    file_path (str): Path to the Basilisk Conversation file
	    base_storage_path (UPath): Base path where attachments will be restored

	Returns:
	    Conversation: A restored conversation object with its associated attachments

	Raises:
	    zipfile.BadZipFile: If the file is not a valid zip archive
	    FileNotFoundError: If the conversation.json file is missing from the archive
	"""
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
