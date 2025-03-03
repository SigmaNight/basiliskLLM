"""Test conversation attachment file."""

import base64
from io import BytesIO

import pytest
from PIL import Image
from upath import UPath

from basilisk.conversation import (
	AttachmentFile,
	AttachmentFileTypes,
	ImageFile,
	build_from_url,
	parse_supported_attachment_formats,
)


class TestAttachmentFileCreation:
	"""Tests for attachment file creation and validation."""

	@pytest.mark.parametrize(
		"file_path",
		[
			lambda tmp_path: UPath(tmp_path) / "non_existent_file.txt",
			lambda _: UPath("memory://test.txt"),
		],
		ids=["local_non_existent", "memory_non_existent"],
	)
	def test_attachment_file_not_exist(self, tmp_path, file_path):
		"""Test attachment file not exists."""
		test_file_path = file_path(tmp_path)
		with pytest.raises(FileNotFoundError):
			AttachmentFile(location=test_file_path)

	@pytest.mark.parametrize(
		"file_path,expected_type",
		[
			(
				lambda tmp_path: UPath(tmp_path) / "test.txt",
				AttachmentFileTypes.LOCAL,
			),
			(lambda _: UPath("memory://test.txt"), AttachmentFileTypes.MEMORY),
		],
		ids=["local_file", "memory_file"],
	)
	def test_attachment_file_exists(self, tmp_path, file_path, expected_type):
		"""Test attachment file exists."""
		test_file_path = file_path(tmp_path)
		with test_file_path.open("w") as f:
			f.write("test")
		attachment = AttachmentFile(location=test_file_path)
		assert attachment.location == test_file_path
		assert attachment.size == 4
		assert attachment.type == expected_type

	def test_attachment_custom_name(self, text_file):
		"""Test attachment file with custom name."""
		custom_name = "custom_file_name.txt"
		attachment = AttachmentFile(location=text_file, name=custom_name)
		assert attachment.name == custom_name


class TestAttachmentFileProperties:
	"""Tests for attachment file properties and methods."""

	def test_attachment_display_size(self, tmp_path):
		"""Test attachment file display size formatting."""
		test_file_path = UPath(tmp_path) / "test.txt"
		with test_file_path.open("w") as f:
			f.write("a" * 1500)  # Write 1.5KB of data
		attachment = AttachmentFile(location=test_file_path)
		assert attachment.display_size == "1.46 KB"

	def test_attachment_mime_type(self, text_file):
		"""Test attachment file mime type detection."""
		attachment = AttachmentFile(location=text_file)
		assert attachment.mime_type == "text/plain"

	def test_attachment_read_as_str(self, text_file):
		"""Test reading attachment file as string."""
		attachment = AttachmentFile(location=text_file)
		assert attachment.read_as_plain_text() == "test content"

	def test_attachment_get_display_info(self, text_file):
		"""Test getting display info tuple."""
		attachment = AttachmentFile(location=text_file)
		name, size, location = attachment.get_display_info()

		assert name == "test.txt"
		assert size == "12 B"
		assert str(text_file) in location

	@pytest.mark.parametrize(
		"content_size,expected_display",
		[
			(500, "500 B"),
			(1024, "1.00 KB"),
			(1024 * 1024, "1.00 MB"),
			(2 * 1024 * 1024, "2.00 MB"),
		],
		ids=["bytes", "kilobytes", "megabytes", "multiple_megabytes"],
	)
	def test_attachment_various_sizes(
		self, tmp_path, content_size, expected_display
	):
		"""Test attachment file with various sizes."""
		test_file_path = UPath(tmp_path) / "test.txt"
		with test_file_path.open("w") as f:
			f.write("a" * content_size)

		attachment = AttachmentFile(location=test_file_path)
		assert attachment.display_size == expected_display

	@pytest.mark.parametrize(
		"file_name,expected_mime",
		[
			("test.txt", "text/plain"),
			("test.jpg", "image/jpeg"),
			("test.png", "image/png"),
			("test.pdf", "application/pdf"),
		],
		ids=["text", "jpeg", "png", "pdf"],
	)
	def test_attachment_mime_types(self, tmp_path, file_name, expected_mime):
		"""Test MIME type detection for various file types."""
		test_file_path = UPath(tmp_path) / file_name
		with test_file_path.open("w") as f:
			f.write("test content")

		attachment = AttachmentFile(location=test_file_path)
		assert attachment.mime_type == expected_mime

	def test_attachment_base64_encoding(self, text_file):
		"""Test base64 encoding of attachment file."""
		attachment = AttachmentFile(location=text_file)
		encoded = attachment.encode_base64()
		decoded = base64.b64decode(encoded).decode('utf-8')
		assert decoded == "test content"


class TestImageFileProperties:
	"""Tests for image file properties and methods."""

	def test_image_file_dimensions(self, image_file):
		"""Test image file dimensions detection."""
		image = ImageFile(location=image_file)
		assert image.dimensions == (100, 50)
		assert image.display_dimensions == "100 x 50"

	def test_image_display_location_truncation(self):
		"""Test display location truncation for data URLs."""
		# Mock a data URL
		test_location = UPath("data:image/png;base64," + "A" * 100)

		image = ImageFile(location=test_location)
		assert image.type == AttachmentFileTypes.URL
		display_loc = image.display_location
		assert len(display_loc) < 100
		assert "..." in display_loc

	def test_encode_image_url(self, image_file):
		"""Test base64 encoding of image file."""
		image = ImageFile(location=image_file)
		encoded = image.url
		assert encoded.startswith("data:image/png;base64,")
		decoded = base64.b64decode(encoded.split(",")[1])
		assert Image.open(BytesIO(decoded)).size == (100, 50)


class TestImageResizing:
	"""Tests for image resizing functionality."""

	@pytest.fixture
	def resizable_image_file(self, tmp_path):
		"""Create an image file for resize testing."""
		test_file_path = UPath(tmp_path) / "resize_test.png"
		with test_file_path.open("wb") as f:
			img = Image.new('RGB', (200, 100))
			img.save(f)
		return test_file_path

	@pytest.fixture
	def conv_folder(self, tmp_path):
		"""Create a conversation folder for image resize output."""
		folder = UPath(tmp_path) / "conv"
		folder.mkdir()
		return folder

	@pytest.mark.parametrize(
		"img_width,img_height,quality,final_size",
		[
			(200, 100, 85, None),  # Same size, no resize
			(50, 25, 85, (50, 25)),  # Smaller size, resize
			(300, 200, 50, None),  # Larger size, no resize
			(200, 100, 100, None),  # Max quality, no resize
			(200, 100, 0, None),  # Invalid quality, no resize
			(200, 100, 101, None),  # Out of range quality, no resize
			(200, 100, -1, None),  # Negative quality, no resize
			(-100, 50, 50, (100, 50)),  # Absolute value width, resize
			(50, -100, 50, (50, 25)),  # Absolute value height, resize
			(-50, -50, 50, None),  # Both negative and too small, no resize
		],
		ids=[
			"no_resize_same_size",
			"resize_smaller",
			"no_resize_larger",
			"no_resize_max_quality",
			"no_resize_zero_quality",
			"no_resize_exceed_quality",
			"no_resize_negative_quality",
			"resize_negative_width",
			"resize_negative_height",
			"no_resize_both_negative",
		],
	)
	def test_image_resize(
		self,
		resizable_image_file,
		conv_folder,
		img_width,
		img_height,
		quality,
		final_size,
	):
		"""Test image resizing functionality."""
		image = ImageFile(location=resizable_image_file)

		image.resize(
			conv_folder,
			max_width=img_width,
			max_height=img_height,
			quality=quality,
		)

		if final_size:
			assert image.resize_location is not None
			# Verify resized image dimensions
			with Image.open(image.resize_location) as resized_img:
				assert resized_img.size == final_size
		else:
			assert image.resize_location is None


class TestURLAndFormatting:
	"""Tests for URL handling and format parsing."""

	def test_image_from_url(self, httpx_mock):
		"""Test creating ImageFile from URL."""
		test_url = "https://example.com/image.jpg"
		image = Image.new('RGB', (100, 50))
		image_content = BytesIO()
		image.save(image_content, format='JPEG')
		image_content.seek(0)

		# Mock the HTTP response
		httpx_mock.add_response(
			url=test_url,
			content=image_content,
			headers={
				"content-type": "image/jpeg",
				"content-length": str(len(image_content.getvalue())),
			},
		)

		image = build_from_url(test_url)
		assert image.type == AttachmentFileTypes.URL
		assert str(image.location) == test_url

	@pytest.mark.parametrize(
		"mime_type,expected_wildcard",
		[
			({"image/jpeg"}, "*.jpg;*.jpe;*.jpeg;*.jfif"),
			({"image/jpeg", "image/png"}, "*.jpg;*.jpe;*.jpeg;*.jfif;*.png"),
			({"application/x-unknown"}, ""),
			(set(), ""),
		],
		ids=["single_mime", "multiple_mime", "unknown_mime", "empty_mime"],
	)
	def test_parse_supported_attachment_formats(
		self, mime_type, expected_wildcard
	):
		"""Test parsing supported attachment formats."""
		assert (
			parse_supported_attachment_formats(mime_type) == expected_wildcard
		)
