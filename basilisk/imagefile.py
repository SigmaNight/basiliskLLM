from enum import Enum
from functools import lru_cache
import logging
import mimetypes
import os
import re
import tempfile
import time
from .imagehelper import get_image_dimensions, encode_image, resize_image

log = logging.getLogger(__name__)

URL_PATTERN = re.compile(
	r'(https?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|data:image/\S+)',
	re.IGNORECASE,
)


def get_display_size(size):
	if size < 1024:
		return f"{size} B"
	if size < 1024 * 1024:
		return f"{size / 1024:.2f} KB"
	return f"{size / 1024 / 1024:.2f} MB"


class ImageFileTypes(Enum):
	UNKNOWN = 0
	IMAGE_LOCAL = 1
	IMAGE_URL = 2


class ImageFile:
	def __init__(
		self,
		location: str,
		name: str = None,
		description: str = None,
		size: int = -1,
		dimensions: tuple = None,
	):
		if not isinstance(location, str):
			raise TypeError("path must be a string")
		self.location = location
		self.type = self._get_type()
		self.name = name or self._get_name()
		self.description = description
		if size and size > 0:
			self.size = get_display_size(size)
		else:
			self.size = self._get_size()
		self.dimensions = dimensions or self._get_dimensions()

	def _get_type(self):
		if os.path.exists(self.location):
			return ImageFileTypes.IMAGE_LOCAL
		if re.match(URL_PATTERN, self.location):
			return ImageFileTypes.IMAGE_URL
		return ImageFileTypes.UNKNOWN

	def _get_name(self):
		if self.type == ImageFileTypes.IMAGE_LOCAL:
			return os.path.basename(self.location)
		if self.type == ImageFileTypes.IMAGE_URL:
			return self.location.split("/")[-1]
		return "N/A"

	def _get_size(self):
		if self.type == ImageFileTypes.IMAGE_LOCAL:
			size = os.path.getsize(self.location)
			return get_display_size(size)
		return "N/A"

	def _get_dimensions(self):
		if self.type == ImageFileTypes.IMAGE_LOCAL:
			return get_image_dimensions(self.location)
		return None

	@lru_cache(maxsize=None)
	def get_url(
		self, resize=False, max_width=None, max_height=None, quality=None
	) -> str:
		location = self.location
		log.debug(f'Processing image "{location}"')
		if self.type == ImageFileTypes.IMAGE_LOCAL:
			if resize:
				start_time = time.time()
				fd, path_resized_image = tempfile.mkstemp(
					prefix="basilisk_resized_", suffix=".jpg"
				)
				os.close(fd)
				resize_image(
					location,
					max_width=max_width,
					max_height=max_height,
					quality=quality,
					target=path_resized_image,
				)
				log.debug(
					f"Image resized in {time.time() - start_time:.2f} second"
				)
				location = path_resized_image
			start_time = time.time()
			base64_image = encode_image(location)
			if resize:
				os.remove(path_resized_image)
			log.debug(f"Image encoded in {time.time() - start_time:.2f} second")
			mime_type, _ = mimetypes.guess_type(location)
			return f"data:{mime_type};base64,{base64_image}"
		elif self.type == ImageFileTypes.IMAGE_URL:
			return location
		raise ValueError("Invalid image type")

	@property
	def display_location(self):
		location = self.location
		if location.startswith("data:image/"):
			location = f"{location[:50]}...{location[-10:]}"
		return location

	def __str__(self):
		location = self.display_location
		return f"{self.name} ({self.size}, {self.dimensions}, {self.description}, {location})"

	def __repr__(self):
		location = self.display_location
		return f"ImageFile(name={self.name}, size={self.size}, dimensions={self.dimensions}, description={self.description}, location={location})"
