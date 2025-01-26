from __future__ import annotations

import base64
import logging
import mimetypes
import re
from enum import Enum
from io import BufferedReader, BufferedWriter, BytesIO
from typing import Annotated, Any

import httpx
from PIL import Image
from pydantic import (
	BaseModel,
	Field,
	PlainValidator,
	SerializationInfo,
	SerializerFunctionWrapHandler,
	ValidationInfo,
	field_serializer,
	field_validator,
)
from upath import UPath

from basilisk.decorators import measure_time

log = logging.getLogger(__name__)

PydanticUPath = Annotated[UPath, PlainValidator(lambda v: UPath(v))]

URL_PATTERN = re.compile(
	r'(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|data:image/\S+)',
	re.IGNORECASE,
)


def get_image_dimensions(reader: BufferedReader) -> tuple[int, int]:
	"""Get the dimensions of an image."""
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
	"""Compress an image and save it to a specified file by resizing according to
	given maximum dimensions and adjusting the quality.

	@param src: path to the source image.
	@param max_width: Maximum width for the compressed image. If 0, only `max_height` is used to calculate the ratio.
	@param max_height: Maximum height for the compressed image. If 0, only `max_width` is used to calculate the ratio.
	@param quality: the quality of the compressed image
	@param target: output path for the compressed image
	@return: True if the image was successfully compressed and saved, False otherwise
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


class ImageFileTypes(Enum):
	UNKNOWN = "unknown"
	IMAGE_LOCAL = "local"
	IMAGE_MEMORY = "memory"
	IMAGE_URL = "http"

	@classmethod
	def _missing_(cls, value: object) -> ImageFileTypes:
		"""Determine the image file type based on a given string value.

		This method is a custom implementation for handling enum value mapping when a non-standard value is provided. It maps specific string inputs to predefined ImageFileTypes.

		Parameters:
		    value (object): The input value to be mapped to an ImageFileTypes enum.

		Returns:
		    ImageFileTypes: The corresponding image file type based on the input value.
		    - Returns IMAGE_URL for "data" or "https" strings (case-insensitive)
		    - Returns IMAGE_LOCAL for "zip" string (case-insensitive)
		    - Returns UNKNOWN for any other input that doesn't match the predefined mappings

		Notes:
		    - This method is typically used as a fallback for enum value resolution
		    - Provides flexible type mapping for different image source representations
		"""
		if isinstance(value, str) and value.lower() == "data":
			return cls.IMAGE_URL
		if isinstance(value, str) and value.lower() == "https":
			return cls.IMAGE_URL
		if isinstance(value, str) and value.lower() == "zip":
			return cls.IMAGE_LOCAL
		return cls.UNKNOWN


class NotImageError(ValueError):
	pass


class ImageFile(BaseModel):
	location: PydanticUPath
	name: str | None = None
	description: str | None = None
	size: int | None = None
	dimensions: tuple[int, int] | None = None
	resize_location: PydanticUPath | None = Field(default=None, exclude=True)

	@classmethod
	@measure_time
	def build_from_url(cls, url: str) -> ImageFile:
		"""Fetch an image from a given URL and create an ImageFile instance.

		This class method retrieves an image from the specified URL, validates that it is an image,
		and constructs an ImageFile with metadata about the image.

		Parameters:
		    url (str): The URL of the image to retrieve.

		Returns:
		    ImageFile: An instance of ImageFile with details about the retrieved image.

		Raises:
		    httpx.HTTPError: If there is an error during the HTTP request.
		    NotImageError: If the URL does not point to an image (content type is not image/*).

		Example:
		    image = ImageFile.build_from_url("https://example.com/image.jpg")
		"""
		r = httpx.get(url, follow_redirects=True)
		r.raise_for_status()
		content_type = r.headers.get("content-type", "")
		if not content_type.startswith("image/"):
			e = NotImageError("URL does not point to an image")
			e.content_type = content_type
			raise e
		size = r.headers.get("Content-Length")
		if size and size.isdigit():
			size = int(size)
		dimensions = get_image_dimensions(BytesIO(r.content))
		return cls(
			location=url,
			type=ImageFileTypes.IMAGE_URL,
			size=size,
			description=content_type,
			dimensions=dimensions,
		)

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

		Parameters:
		    value (PydanticUPath): The original location path to be serialized.
		    wrap_handler (SerializerFunctionWrapHandler): The default serialization handler.
		    info (SerializationInfo): Serialization context information.

		Returns:
		    PydanticUPath: The serialized location path, potentially remapped based on context.

		Example:
		    # With a mapping context
		    context = {"attachment_mapping": {original_path: new_path}}
		    serialized_location = ImageFile.change_location(original_path, default_handler, context)
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

		Parameters:
		    cls (type): The class this method is attached to.
		    value (Any): The location value to validate, which can be a string or UPath.
		    info (ValidationInfo): Validation context containing additional information.

		Returns:
		    str | PydanticUPath: A validated and potentially transformed location.

		Raises:
		    ValueError: If the location is not a string or UPath instance.

		Examples:
		    # With root path context
		    validate_location("image.jpg", context={"root_path": "/home/user"})
		    # Returns: /home/user/image.jpg

		    # With full URL or absolute path
		    validate_location("https://example.com/image.jpg")
		    # Returns: https://example.com/image.jpg
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

	def __init__(self, /, **data: Any) -> None:
		"""Initialize an ImageFile instance with optional data.

		If no name is provided, automatically generates a name using the internal _get_name() method.
		If no size is set, retrieves the file size using _get_size() method.
		If no dimensions are specified, determines image dimensions using _get_dimensions() method.

		Parameters:
		    **data (Any): Keyword arguments for initializing the ImageFile instance.
		                  Can include optional attributes like name, size, and dimensions.

		Note:
		    - Uses positional-only argument separator (/) to prevent naming conflicts
		    - Calls the parent class initializer with provided data
		    - Fills in missing attributes with derived values from internal methods
		"""
		super().__init__(**data)
		if not self.name:
			self.name = self._get_name()
			self.size = self._get_size()
		if not self.dimensions:
			self.dimensions = self._get_dimensions()

	__init__.__pydantic_base_init__ = True

	@property
	def type(self) -> ImageFileTypes:
		"""Determine the type of image file based on its location protocol.

		Returns:
		    ImageFileTypes: An enum value representing the image file's source type,
		    derived from the protocol of the image's location.

		Raises:
		    ValueError: If the protocol cannot be mapped to a known ImageFileTypes value.
		"""
		return ImageFileTypes(self.location.protocol)

	def _get_name(self) -> str:
		return self.location.name

	def _get_size(self) -> int | None:
		if self.type == ImageFileTypes.IMAGE_URL:
			return None
		return self.location.stat().st_size

	@property
	def display_size(self) -> str:
		size = self.size
		if size is None:
			return _("Unknown")
		if size < 1024:
			return f"{size} B"
		if size < 1024 * 1024:
			return f"{size / 1024:.2f} KB"
		return f"{size / 1024 / 1024:.2f} MB"

	def _get_dimensions(self) -> tuple[int, int] | None:
		if self.type == ImageFileTypes.IMAGE_URL:
			return None
		with self.location.open(mode="rb") as image_file:
			return get_image_dimensions(image_file)

	@property
	def display_dimensions(self) -> str:
		if self.dimensions is None:
			return _("Unknown")
		return f"{self.dimensions[0]} x {self.dimensions[1]}"

	@measure_time
	def resize(
		self, conv_folder: UPath, max_width: int, max_height: int, quality: int
	):
		"""Resize the image to specified dimensions and save to a new location.

		This method resizes the image if it is not a URL, creating an optimized version
		in the specified conversion folder. The original image remains unchanged.

		Parameters:
		    conv_folder (UPath): Folder where the resized image will be saved
		    max_width (int): Maximum width for the resized image
		    max_height (int): Maximum height for the resized image
		    quality (int): Compression quality for the resized image (1-100)

		Notes:
		    - Skips resizing for URL-based images
		    - Saves resized image in an "optimized_images" subdirectory
		    - Sets `resize_location` to the new file path if resizing is successful
		    - Uses the original file's extension for the resized image
		"""
		if ImageFileTypes.IMAGE_URL == self.type:
			return
		log.debug("Resizing image")
		resize_location = conv_folder.joinpath(
			"optimized_images", self.location.name
		)
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
		return self.resize_location or self.location

	@measure_time
	def encode_image(self) -> str:
		if self.size and self.size > 1024 * 1024 * 1024:
			log.warning(
				f"Large image ({self.display_size}) being encoded to base64"
			)
		with self.send_location.open(mode="rb") as image_file:
			return base64.b64encode(image_file.read()).decode("utf-8")

	@property
	def mime_type(self) -> str | None:
		if self.type == ImageFileTypes.IMAGE_URL:
			return None
		mime_type, _ = mimetypes.guess_type(self.send_location)
		return mime_type

	@property
	def url(self) -> str:
		if not isinstance(self.type, ImageFileTypes):
			raise ValueError("Invalid image type")
		if self.type == ImageFileTypes.IMAGE_URL:
			return str(self.location)
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
