from __future__ import annotations

import base64
import logging
import mimetypes
import re
from enum import Enum
from functools import cached_property
from typing import TYPE_CHECKING, Annotated, Any

from PIL import Image
from pydantic import BaseModel, PlainValidator
from upath import UPath

from .decorators import measure_time

if TYPE_CHECKING:
	from io import BufferedReader, BufferedWriter
log = logging.getLogger(__name__)

PydanticUPath = Annotated[UPath, PlainValidator(lambda v: UPath(v))]

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
	format: str,
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
	resized_image.save(target, optimize=True, quality=quality, format=format)
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
	location: PydanticUPath
	type: ImageFileTypes = ImageFileTypes.UNKNOWN
	name: str | None = None
	description: str | None = None
	size: int = -1
	dimensions: tuple[int, int] | None = None
	resize_location: PydanticUPath | None = None

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
		img_type = ImageFileTypes(self.location.protocol)
		return img_type

	def _get_name(self) -> str:
		return self.location.name

	def _get_size(self) -> str:
		if self.type == ImageFileTypes.IMAGE_URL:
			return "N/A"
		return get_display_size(self.location.stat().st_size)

	def _get_dimensions(self) -> tuple[int, int] | None:
		if self.type != ImageFileTypes.IMAGE_URL:
			return None
		with self.location.open(mode="rb") as image_file:
			return get_image_dimensions(image_file)

	@measure_time
	def resize(
		self,
		optimize_folder: UPath,
		max_width: int,
		max_height: int,
		quality: int,
	):
		if ImageFileTypes.IMAGE_URL == self.type:
			return
		if self.resize_location:
			return
		log.debug("Resizing image")
		resize_location = optimize_folder / self.location.name
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

	@property
	def send_location(self) -> UPath:
		return self.resize_location or self._location

	@measure_time
	def encode_image(self) -> str:
		with self.send_location.open(mode="rb") as image_file:
			return base64.b64encode(image_file.read()).decode("utf-8")

	@property
	def mime_type(self) -> str | None:
		if self.type == ImageFileTypes.IMAGE_URL:
			return None
		mime_type, _ = mimetypes.guess_type(self.send_location)
		return mime_type

	@cached_property
	def url(self) -> str:
		if self.type not in ImageFileTypes:
			raise ValueError("Invalid image type")
		if self.type == ImageFileTypes.IMAGE_URL:
			return self.location
		base64_image = self.encode_image()
		return f"data:{self.mime_type};base64,{base64_image}"

	@property
	def display_location(self):
		location = str(self.location)
		if location.startswith("data:image/"):
			location = f"{location[:50]}...{location[-10:]}"
		return location

	@staticmethod
	def remove_location(location: UPath):
		log.debug(f"Removing image at {location}")
		try:
			fs = location.fs
			fs.rm(location.path)
		except Exception as e:
			log.error(f"Error deleting image at {location}: {e}")

	def __del__(self):
		if self.type == ImageFileTypes.IMAGE_URL:
			return
		if self.resize_location:
			self.remove_location(self.resize_location)
		if self.type == ImageFileTypes.IMAGE_MEMORY:
			self.remove_location(self.location)
