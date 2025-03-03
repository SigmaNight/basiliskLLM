"""Module for managing attached files in conversations."""

from __future__ import annotations

import base64
import enum
import logging
import mimetypes
import re
from io import BufferedReader, BufferedWriter, BytesIO
from typing import Any

import httpx
from PIL import Image
from pydantic import (
	BaseModel,
	Field,
	SerializationInfo,
	SerializerFunctionWrapHandler,
	ValidationInfo,
	field_serializer,
	field_validator,
	model_validator,
)
from upath import UPath

from basilisk.decorators import measure_time
from basilisk.types import PydanticUPath

log = logging.getLogger(__name__)

URL_PATTERN = re.compile(
	r'(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|data:image/\S+)',
	re.IGNORECASE,
)


def get_image_dimensions(reader: BufferedReader) -> tuple[int, int]:
	"""Get the dimensions of an image.

	Args:
		reader: A file-like object containing the image data.

	Returns:
		A tuple containing the width and height of the image.
	"""
	img = Image.open(reader)
	return img.size


def resize_image(
	src: BufferedReader,
	target: BufferedWriter,
	format: str,
	max_width: int = 0,
	max_height: int = 0,
	quality: int = 85,
) -> bool:
	"""Compress an image and save it to a specified file.

	Args:
		src: path to the source image.
		format: The format of the compressed image (e.g., "JPEG", "PNG").
		max_width: Maximum width for the compressed image. If 0, only `max_height` is used to calculate the ratio.
		max_height: Maximum height for the compressed image. If 0, only `max_width` is used to calculate the ratio.
		quality: the quality of the compressed image (1-100).
		target: Output path for the compressed image file.

	Returns:
		True if the image was successfully compressed and saved, False otherwise
	"""
	if max_width <= 0 and max_height <= 0:
		log.debug("No resizing needed")
		return False
	image = Image.open(src)
	if image.mode in ("RGBA", "P"):
		image = image.convert("RGB")
	orig_width, orig_height = image.size
	if orig_width <= max_width and orig_height <= max_height:
		log.debug("Image is already smaller than max dimensions")
		return False
	if max_width > 0 and max_height > 0:
		ratio = min(max_width / orig_width, max_height / orig_height)
	elif max_width > 0:
		ratio = max_width / orig_width
	else:
		ratio = max_height / orig_height
	new_width = int(orig_width * ratio)
	new_height = int(orig_height * ratio)
	resized_image = image.resize(
		(new_width, new_height), Image.Resampling.LANCZOS
	)
	resized_image.save(target, optimize=True, quality=quality, format=format)
	return True


def parse_supported_attachment_formats(
	supported_attachment_formats: set[str],
) -> str:
	"""Parse the supported attachment formats into a wildcard string for use in file dialogs.

	Args:
		supported_attachment_formats: A set of supported attachment formats (MIME types).

	Returns:
		A wildcard string containing all supported attachment formats.
	"""
	wildcard_parts = []
	for mime_type in sorted(supported_attachment_formats):
		exts = mimetypes.guess_all_extensions(mime_type)
		if exts:
			log.debug(f"Adding wildcard for MIME type {mime_type}: {exts}")
			wildcard_parts.append("*" + ";*".join(exts))
		else:
			log.warning(f"No extensions found for MIME type {mime_type}")

	wildcard = ";".join(wildcard_parts)
	return wildcard


def get_mime_type(path: str) -> str | None:
	"""Get the MIME type of a file.

	Args:
		path: The path to the file.

	Returns:
		The MIME type of the file, or None if the type cannot be determined.
	"""
	return mimetypes.guess_type(path)[0]


@measure_time
def build_from_url(url: str) -> AttachmentFile:
	"""Fetch a file from a given URL and create an AttachmentFile instance.

	This class method retrieves a file from the specified URL and constructs an AttachmentFile with metadata about the file.

	Args:
		url: The URL of the file to retrieve.

	Returns:
		An instance of AttachmentFile with details about the retrieved file.

	Raises:
		httpx.HTTPError: If there is an error during the HTTP request.

	Example:
		file = build_from_url("https://example.com/file.pdf")
		image = build_from_url("https://example.com/image.jpg")
	"""
	r = httpx.get(url, follow_redirects=True)
	r.raise_for_status()
	size = r.headers.get("Content-Length")
	if size and size.isdigit():
		size = int(size)
	mime_type = r.headers.get("content-type", None)
	if not mime_type:
		raise NotImageError("No MIME type found")
	if mime_type.startswith("image/"):
		dimensions = get_image_dimensions(BytesIO(r.content))
		return ImageFile(
			location=url,
			type=AttachmentFileTypes.URL,
			size=size,
			mime_type=mime_type,
			dimensions=dimensions,
		)
	return AttachmentFile(
		location=url,
		type=AttachmentFileTypes.URL,
		size=size,
		mime_type=mime_type,
	)


class AttachmentFileTypes(enum.StrEnum):
	"""Enumeration of file types based on their source location."""

	# The file type is unknown.
	UNKNOWN = enum.auto()
	# The file is stored on the local filesystem.
	LOCAL = enum.auto()
	# The file is stored in memory (RAM).
	MEMORY = enum.auto()
	# The file is stored at a URL.
	URL = enum.auto()

	@classmethod
	def _missing_(cls, value: object) -> AttachmentFileTypes:
		"""Determine the enum value for a given input value.

		This method is a custom implementation for handling enum value mapping when a non-standard value is provided. It maps specific string inputs to predefined ImageFileTypes.
			The mapping is as follows:
			- "http", "https", "data" -> AttachmentFileTypes.URL
			- "zip" -> AttachmentFileTypes.LOCAL
			- Any other value -> AttachmentFileTypes.UNKNOWN

		Args:
				value: The input value to be mapped to an ImageFileTypes enum.

		Returns:
			The corresponding AttachmentFileTypes enum value for the input value.
		"""
		if not isinstance(value, str):
			return cls.UNKNOWN
		value = value.lower()
		if value in {"data", "http", "https"}:
			return cls.URL
		if value == "zip":
			return cls.LOCAL
		return cls.UNKNOWN


class NotImageError(ValueError):
	"""Exception raised when a URL does not point to an image file."""

	pass


class AttachmentFile(BaseModel):
	"""Represents an attached file in a conversation."""

	location: PydanticUPath
	name: str | None = None
	description: str | None = None
	size: int | None = None
	mime_type: str | None = None

	@field_serializer("location", mode="wrap")
	@classmethod
	def change_location(
		cls,
		value: PydanticUPath,
		wrap_handler: SerializerFunctionWrapHandler,
		info: SerializationInfo,
	) -> PydanticUPath:
		"""Serialize the location field with optional context-based mapping.

		This method is a field serializer for the `location` attribute that allows dynamic
		path translation based on a provided mapping context. If no mapping is available,
		it returns the original value using the default serialization handler.

		Args:
			value: The original location path to be serialized.
			wrap_handler: The default serialization handler.
			info: Serialization context information.

		Returns:
			PydanticUPath: The serialized location path, potentially remapped based on context.
		"""
		if not info.context:
			return wrap_handler(value)
		mapping = info.context.get("attachment_mapping")
		if not mapping:
			return wrap_handler(value)
		return mapping.get(value, wrap_handler(value))

	@field_validator("location", mode="before")
	@classmethod
	def validate_location(
		cls, value: Any, info: ValidationInfo
	) -> str | PydanticUPath:
		"""Validates and transforms the location of an image file.

		This method ensures that the location is either a valid string or a UPath instance.
		If a string is provided without a protocol and a root path is available in the context,
		it prepends the root path to create an absolute path.

		Args:
			value: The location value to validate, which can be a string or UPath.
			info: Validation context containing additional information.

		Returns:
			A validated and potentially transformed location.

		Raises:
			ValueError: If the location is not a string or UPath instance.
		"""
		if isinstance(value, str):
			if info.context:
				root_path = info.context.get("root_path")
				if root_path and "://" not in value:
					return root_path / value
			return value
		if not isinstance(value, UPath):
			raise ValueError("Invalid location")
		return value

	def __init__(self, /, **kwargs: Any) -> None:
		"""Initialize an AttachmentFile instance with optional data.

		If no name is provided, automatically generates a name using the internal _get_name() method.
		If no size is set, retrieves the file size using _get_size() method.

		Args:
			kwargs: Keyword arguments for initializing the AttachmentFile instance. Can include optional attributes like name, size, and description.
		"""
		super().__init__(**kwargs)
		self.name = self.name or self._get_name()
		self.mime_type = kwargs.get("mime_type") or self._get_mime_type()
		self.size = kwargs.get("size") or self._get_size()

	__init__.__pydantic_base_init__ = True

	@model_validator(mode="after")
	def validate_location_exist(self) -> AttachmentFile:
		"""Validate the location of the file.

		Raises:
			FileNotFoundError: If the file does not exist.
		"""
		if self.type == AttachmentFileTypes.URL:
			return self
		if not self.location.exists():
			raise FileNotFoundError(f"File {self.location} does not exist")
		return self

	@property
	def type(self) -> AttachmentFileTypes:
		"""Determine the type of file based on its location protocol.

		Returns:
			An enum value representing the file's source type, derived from the protocol of the file's location.
		"""
		if self.location.protocol in ("", "file"):
			return AttachmentFileTypes.LOCAL
		return AttachmentFileTypes(self.location.protocol)

	def _get_name(self) -> str:
		"""Get the name of the file.

		Returns:
			The name of the file, extracted from the file path.
		"""
		return self.location.name

	def _get_size(self) -> int | None:
		"""Get the size of the file.

		Returns:
			The size of the file in bytes, or None if the size cannot be determined
		"""
		if self.type == AttachmentFileTypes.URL:
			return None
		return self.location.stat().st_size

	@property
	def display_size(self) -> str:
		"""Get the human-readable size of the file.

		Returns:
			The size of the file in a human-readable format (e.g., "1.23 MB").
		"""
		size = self.size
		if size is None:
			# Translators: Placeholder for an unknown file size
			return _("Unknown")
		if size < 1024:
			return f"{size} B"
		if size < 1024 * 1024:
			return f"{size / 1024:.2f} KB"
		return f"{size / 1024 / 1024:.2f} MB"

	@property
	def send_location(self) -> UPath:
		"""Get the location of the file to send.

		Returns:
			The location of the file to send, which is the original location for URL files.
		"""
		return getattr(self, "resize_location", None) or self.location

	def _get_mime_type(self) -> str | None:
		"""Get the MIME type of the file.

		Returns:
			The MIME type of the file, or None if the type cannot be determined.
		"""
		if self.type == AttachmentFileTypes.URL:
			return None
		return get_mime_type(self.send_location)

	@property
	def display_location(self) -> str:
		"""Get the display location of the file.

		Returns:
			The display location of the file, truncated if necessary.
		"""
		location = str(self.location)
		if location.startswith("data:"):
			location = f"{location[:50]}...{location[-10:]}"
		return location

	@staticmethod
	def remove_location(location: UPath):
		"""Remove a file at the specified location.

		Args:
			location: The location of the file to remove.
		"""
		log.debug(f"Removing file at {location}")
		try:
			fs = location.fs
			fs.rm(location.path)
		except Exception as e:
			log.error(f"Error deleting file at {location}: {e}")

	def read_as_plain_text(self) -> str:
		"""Read the file as a plain text string.

		Returns:
			The contents of the file as a plain text string.
		"""
		with self.send_location.open(mode="r") as file:
			return file.read()

	def encode_base64(self) -> str:
		"""Encode the file as a base64 string.

		Returns:
			A base64-encoded string representing the file.
		"""
		with self.send_location.open(mode="rb") as file:
			return base64.b64encode(file.read()).decode("utf-8")

	def __del__(self):
		"""Delete the file."""
		if self.type == AttachmentFileTypes.URL:
			return
		if self.type == AttachmentFileTypes.MEMORY:
			self.remove_location(self.location)

	def get_display_info(self) -> tuple[str, str, str]:
		"""Get the name, size and location of the file.

		Returns:
			A tuple containing the name, size and location of the file.
		"""
		return self.name, self.display_size, self.display_location

	@property
	def url(self) -> str:
		"""Get the URL of the file.

		Returns:
			The URL of the file, or the base64-encoded data if the file is in memory.
		"""
		if self.type == AttachmentFileTypes.URL:
			return str(self.location)
		base64_data = self.encode_base64()
		return f"data:{self.mime_type};base64,{base64_data}"

	def exists(self):
		"""Check if the file exists.

		Returns:
			True if the file exists, False otherwise.
		"""
		if self.type == AttachmentFileTypes.URL:
			query = httpx.head(self.url, follow_redirects=True)
			return query.status_code == 200
		return self.location.exists()


class ImageFile(AttachmentFile):
	"""Represents an image file in a conversation."""

	dimensions: tuple[int, int] | None = None
	resize_location: PydanticUPath | None = Field(default=None, exclude=True)

	def __init__(self, /, **kwargs: Any) -> None:
		"""Initialize an ImageFile instance with optional data.

		If no name is provided, automatically generates a name using the internal _get_name() method.
		If no size is set, retrieves the file size using _get_size() method.
		If no dimensions are specified, determines image dimensions using _get_dimensions() method.

		Args:
			kwargs: Keyword arguments for initializing the ImageFile instance. Can include optional attributes like name, size, and dimensions.
		"""
		super().__init__(**kwargs)
		self.dimensions = self.dimensions or self._get_dimensions()

	__init__.__pydantic_base_init__ = True

	def _get_dimensions(self) -> tuple[int, int] | None:
		if self.type == AttachmentFileTypes.URL:
			return None
		with self.location.open(mode="rb") as image_file:
			return get_image_dimensions(image_file)

	@property
	def display_dimensions(self) -> str:
		"""Get the human-readable dimensions of the image.

		Returns:
			The dimensions of the image in a human-readable format (e.g., "1920 x 1080").
		"""
		if self.dimensions is None:
			# Translators: Placeholder for unknown image dimensions
			return _("Unknown")
		return f"{self.dimensions[0]} x {self.dimensions[1]}"

	@measure_time
	def resize(
		self, conv_folder: UPath, max_width: int, max_height: int, quality: int
	):
		"""Resize the image to specified dimensions and save to a new location.

		This method resizes the image if it is not a URL, creating an optimized version
		in the specified conversion folder. The original image remains unchanged.

		Args:
			conv_folder: Folder where the resized image will be saved
			max_width: Maximum width for the resized image
			max_height: Maximum height for the resized image
			quality: Compression quality for the resized image (1-100)
		"""
		if AttachmentFileTypes.URL == self.type:
			return
		log.debug("Resizing image")
		resize_folder = conv_folder.joinpath("optimized_images")
		resize_folder.mkdir(parents=True, exist_ok=True)
		resize_location = resize_folder / self.location.name
		with self.location.open(mode="rb") as src_file:
			with resize_location.open(mode="wb") as dst_file:
				success = resize_image(
					src_file,
					max_width=max_width,
					max_height=max_height,
					quality=quality,
					target=dst_file,
					format=self.location.suffix[1:],
				)
				self.resize_location = resize_location if success else None

	@measure_time
	def encode_base64(self) -> str:
		"""Encode the image file as a base64 string.

		Returns:
			A base64-encoded string representing the image file.
		"""
		if self.size and self.size > 1024 * 1024 * 1024:
			log.warning(
				f"Large image ({self.display_size}) being encoded to base64"
			)
		return super().encode_base64()

	@property
	def display_location(self):
		"""Get the display location of the image file.

		Returns:
			The display location of the image file, truncated if necessary.
		"""
		location = str(self.location)
		if location.startswith("data:image/"):
			location = f"{location[:50]}...{location[-10:]}"
		return location

	def __del__(self):
		"""Delete the image file and its resized version."""
		if self.type == AttachmentFileTypes.URL:
			return
		if self.resize_location:
			self.remove_location(self.resize_location)
		super().__del__()
