from __future__ import annotations

import base64
import logging
import mimetypes
import os
import re
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Any

import fsspec
from PIL import Image
from pydantic import BaseModel

from .decorators import measure_time

if TYPE_CHECKING:
	from io import BufferedReader, BufferedWriter
log = logging.getLogger(__name__)

URL_PATTERN = re.compile(
	r'(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|data:image/\S+)',
	re.IGNORECASE,
)


def get_image_dimensions(reader: BufferedReader) -> tuple[int, int]:
	"""
	Get the dimensions of an image.
	"""
	img = Image.open(reader)
	return img.size


def resize_image(
	src: BufferedReader,
	target: BufferedWriter,
	max_width: int = 0,
	max_height: int = 0,
	quality: int = 85,
) -> bool:
	"""
	Compress an image and save it to a specified file by resizing according to
	given maximum dimensions and adjusting the quality.

	@param src: path to the source image.
	@param max_width: Maximum width for the compressed image. If 0, only `max_height` is used to calculate the ratio.
	@param max_height: Maximum height for the compressed image. If 0, only `max_width` is used to calculate the ratio.
	@param quality: the quality of the compressed image
	@param target: output path for the compressed image
	@return: True if the image was successfully compressed and saved, False otherwise
	"""
	if max_width <= 0 and max_height <= 0:
		return False
	image = Image.open(src)
	if image.mode in ("RGBA", "P"):
		image = image.convert("RGB")
	orig_width, orig_height = image.size
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
	resized_image.save(target, optimize=True, quality=quality)
	return True


def get_display_size(size: int) -> str:
	if size < 1024:
		return f"{size} B"
	if size < 1024 * 1024:
		return f"{size / 1024:.2f} KB"
	return f"{size / 1024 / 1024:.2f} MB"


class ImageFileTypes(Enum):
	UNKNOWN = "unknown"
	IMAGE_LOCAL = "local"
	IMAGE_MEMORY = "memory"
	IMAGE_URL = "http"

	@classmethod
	def _missing_(cls, value: object) -> ImageFileTypes:
		if isinstance(value, str) and value.lower() == "data":
			return cls.IMAGE_URL
		return cls.UNKNOWN


class ImageFile(BaseModel):
	location: str
	type: ImageFileTypes = ImageFileTypes.UNKNOWN
	name: str | None = None
	description: str | None = None
	size: int = -1
	dimensions: tuple[int, int] | None = None
	resize_location: str | None = None

	def __init__(self, /, **data: Any) -> None:
		super().__init__(**data)
		self.type = self._get_type()
		if not self.name:
			self.name = self._get_name()
		if self.size > 0:
			self.size = get_display_size(self.size)
		else:
			self.size = self._get_size()
		if not self.dimensions:
			self.dimensions = self._get_dimensions()

	def _get_type(self) -> ImageFileTypes:
		protocol, path = fsspec.core.split_protocol(self.location)
		img_type = ImageFileTypes(protocol)
		return img_type

	def _get_name(self) -> str:
		if (
			self.type == ImageFileTypes.IMAGE_LOCAL
			or self.type == ImageFileTypes.IMAGE_MEMORY
		):
			path = fsspec.core.strip_protocol(self.location)
			return os.path.basename(path)[1]
		if self.type == ImageFileTypes.IMAGE_URL:
			return self.location.split("/")[-1]
		return "N/A"

	def _get_size(self) -> str:
		if self.type == ImageFileTypes.IMAGE_LOCAL:
			size = os.path.getsize(self.location)
			return get_display_size(size)
		return "N/A"

	def _get_dimensions(self) -> tuple[int, int] | None:
		if self.type != ImageFileTypes.IMAGE_URL:
			return None
		with fsspec.open(self.location, "rb") as image_file:
			return get_image_dimensions(image_file)

	@measure_time
	def resize_image(
		self,
		optimize_folder: str,
		max_width: int,
		max_height: int,
		quality: int,
	):
		if ImageFileTypes.IMAGE_URL == self.type:
			return
		if self.resize_location:
			return
		log.debug("Resizing image")
		resize_location = os.path.join(optimize_folder, self.name)
		with fsspec.open(self.location, "rb") as src_file:
			with fsspec.open(resize_location, "wb") as dst_file:
				success = resize_image(
					src_file,
					max_width=max_width,
					max_height=max_height,
					quality=quality,
					target=dst_file,
				)
				self.resize_location = resize_location if success else None

	def encode_image(self) -> str:
		image_path = self.resize_location or self.location
		with fsspec.open(image_path, "rb") as image_file:
			return base64.b64encode(image_file.read()).decode("utf-8")

	@cached_property
	def url(self) -> str:
		if self.type not in ImageFileTypes:
			raise ValueError("Invalid image type")
		if self.type == ImageFileTypes.IMAGE_URL:
			return self.location
		location = self.resize_location or self.location
		mime_type, _ = mimetypes.guess_type(location)
		base64_image = self.encode_image()
		return f"data:{mime_type};base64,{base64_image}"

	@property
	def display_location(self):
		location = self.location
		if location.startswith("data:image/"):
			location = f"{location[:50]}...{location[-10:]}"
		return location

	@staticmethod
	def remove_location(location: str):
		log.debug(f"Removing image at {location}")
		try:
			fs, path = fsspec.url_to_fs(location)
			fs.rm(path)
		except Exception as e:
			log.error(f"Error deleting image at {location}: {e}")

	def __del__(self):
		if self.resize_location:
			self.remove_location(self.resize_location)
		if self.type == ImageFileTypes.IMAGE_MEMORY:
			self.remove_location(self.location)
