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
		decoded = base64.b64decode(encoded).decode("utf-8")
		assert decoded == "test content"

	def test_attachment_read_as_bytes(self, text_file):
		"""Test reading attachment file as bytes."""
		attachment = AttachmentFile(location=text_file)
		content = attachment.read_as_bytes()
		assert isinstance(content, bytes)
		assert content == b"test content"

	def test_attachment_read_file_internal_method(self, text_file):
		"""Test the internal _read_file method with different modes."""
		attachment = AttachmentFile(location=text_file)

		# Test text mode
		text_content = attachment._read_file("r")
		assert isinstance(text_content, str)
		assert text_content == "test content"

		# Test binary mode
		binary_content = attachment._read_file("rb")
		assert isinstance(binary_content, bytes)
		assert binary_content == b"test content"

	def test_attachment_read_binary_file(self, tmp_path):
		"""Test reading binary file content."""
		test_file_path = UPath(tmp_path) / "test.bin"
		binary_data = b"\x00\x01\x02\x03\xff\xfe\xfd"

		with test_file_path.open("wb") as f:
			f.write(binary_data)

		attachment = AttachmentFile(location=test_file_path)

		# Test reading as bytes
		content = attachment.read_as_bytes()
		assert content == binary_data

		# Test internal method
		internal_content = attachment._read_file("rb")
		assert internal_content == binary_data

	def test_attachment_read_empty_file(self, tmp_path):
		"""Test reading empty files."""
		test_file_path = UPath(tmp_path) / "empty.txt"
		test_file_path.touch()

		attachment = AttachmentFile(location=test_file_path)

		# Test reading as text
		text_content = attachment.read_as_plain_text()
		assert text_content == ""

		# Test reading as bytes
		binary_content = attachment.read_as_bytes()
		assert binary_content == b""

	def test_attachment_read_large_file(self, tmp_path):
		"""Test reading large files."""
		test_file_path = UPath(tmp_path) / "large.txt"
		large_content = "A" * 10000  # 10KB of content

		with test_file_path.open("w") as f:
			f.write(large_content)

		attachment = AttachmentFile(location=test_file_path)

		# Test reading as text
		text_content = attachment.read_as_plain_text()
		assert text_content == large_content
		assert len(text_content) == 10000

		# Test reading as bytes
		binary_content = attachment.read_as_bytes()
		assert binary_content == large_content.encode("utf-8")
		assert len(binary_content) == 10000

	def test_attachment_read_unicode_file(self, tmp_path):
		"""Test reading files with Unicode content."""
		test_file_path = UPath(tmp_path) / "unicode.txt"
		unicode_content = "Hello 世界 🌍 café naïve résumé"

		with test_file_path.open("w", encoding="utf-8") as f:
			f.write(unicode_content)

		attachment = AttachmentFile(location=test_file_path)

		# Test reading as text
		text_content = attachment.read_as_plain_text()
		assert text_content == unicode_content

		# Test reading as bytes
		binary_content = attachment.read_as_bytes()
		assert binary_content == unicode_content.encode("utf-8")

	@pytest.mark.parametrize("mode", ["r", "rb", "rt"])
	def test_attachment_read_file_different_modes(self, text_file, mode):
		"""Test _read_file method with different valid modes."""
		attachment = AttachmentFile(location=text_file)
		content = attachment._read_file(mode)

		if "b" in mode:
			assert isinstance(content, bytes)
			assert content == b"test content"
		else:
			assert isinstance(content, str)
			assert content == "test content"


class TestAttachmentFileErrorHandling:
	"""Tests for attachment file error handling."""

	def test_attachment_read_nonexistent_file_after_creation(self, tmp_path):
		"""Test reading a file that gets deleted after attachment creation."""
		test_file_path = UPath(tmp_path) / "temp.txt"
		with test_file_path.open("w") as f:
			f.write("temporary content")

		attachment = AttachmentFile(location=test_file_path)

		# Delete the file after creating the attachment
		test_file_path.unlink()

		# Reading should raise an exception
		with pytest.raises(FileNotFoundError):
			attachment.read_as_plain_text()

		with pytest.raises(FileNotFoundError):
			attachment.read_as_bytes()

	def test_attachment_read_with_permission_error(self, tmp_path, monkeypatch):
		"""Test reading a file with permission errors."""
		test_file_path = UPath(tmp_path) / "restricted.txt"
		with test_file_path.open("w") as f:
			f.write("restricted content")

		attachment = AttachmentFile(location=test_file_path)

		# Mock the _read_file method to raise PermissionError
		def mock_read_file(mode):
			raise PermissionError("Access denied")

		monkeypatch.setattr(attachment, "_read_file", mock_read_file)

		with pytest.raises(PermissionError):
			attachment.read_as_plain_text()

		with pytest.raises(PermissionError):
			attachment.read_as_bytes()

	def test_attachment_read_directory_instead_of_file(self, tmp_path):
		"""Test attempting to read a directory as a file."""
		# Create a directory instead of a file
		test_dir_path = UPath(tmp_path) / "test_directory"
		test_dir_path.mkdir()

		# First test: directory existence validation should pass (directory exists)
		# but reading should fail when we try to read it as a file
		attachment = AttachmentFile(location=test_dir_path)

		# Attempting to read a directory should raise an error
		with pytest.raises((IsADirectoryError, PermissionError, OSError)):
			attachment.read_as_plain_text()

		with pytest.raises((IsADirectoryError, PermissionError, OSError)):
			attachment.read_as_bytes()


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

	def test_image_file_read_methods_inheritance(self, image_file):
		"""Test that ImageFile properly inherits read methods from AttachmentFile."""
		image = ImageFile(location=image_file)

		# Test reading as bytes (should work for images)
		binary_content = image.read_as_bytes()
		assert isinstance(binary_content, bytes)
		assert len(binary_content) > 0

		# Verify we can reconstruct the image from bytes
		reconstructed_image = Image.open(BytesIO(binary_content))
		assert reconstructed_image.size == (100, 50)

		# Test internal _read_file method
		internal_binary = image._read_file("rb")
		assert internal_binary == binary_content

	def test_image_file_read_as_text_error(self, image_file):
		"""Test that reading binary image file as text may raise encoding errors."""
		image = ImageFile(location=image_file)

		# Reading binary PNG data as text should potentially cause issues
		# but we should still test that the method is available
		try:
			text_content = image.read_as_plain_text()
			# If it succeeds, it should be a string (though likely garbled)
			assert isinstance(text_content, str)
		except UnicodeDecodeError:
			# This is expected behavior when reading binary data as text
			pass


class TestImageResizing:
	"""Tests for image resizing functionality."""

	@pytest.fixture
	def resizable_image_file(self, tmp_path):
		"""Create an image file for resize testing."""
		test_file_path = UPath(tmp_path) / "resize_test.png"
		with test_file_path.open("wb") as f:
			img = Image.new("RGB", (200, 100))
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
		image = Image.new("RGB", (100, 50))
		image_content = BytesIO()
		image.save(image_content, format="JPEG")
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

	def test_url_attachment_read_methods(self):
		"""Test that URL-based attachments handle read methods appropriately."""
		test_url = "https://example.com/document.txt"
		# Create a URL attachment (this will skip file existence validation)
		url_attachment = AttachmentFile(
			location=UPath(test_url), size=100, mime_type="text/plain"
		)

		assert url_attachment.type == AttachmentFileTypes.URL

		# URL attachments should be able to call read methods
		# (though they may fail at runtime depending on network access)
		# We're testing that the methods exist and are callable
		assert hasattr(url_attachment, "read_as_plain_text")
		assert hasattr(url_attachment, "read_as_bytes")
		assert hasattr(url_attachment, "_read_file")

	def test_data_url_attachment_properties(self):
		"""Test attachment created from data URL."""
		# Create a data URL attachment
		data_url = "data:text/plain;base64,dGVzdCBjb250ZW50"  # "test content" in base64
		data_attachment = AttachmentFile(
			location=UPath(data_url), size=12, mime_type="text/plain"
		)

		assert data_attachment.type == AttachmentFileTypes.URL
		assert data_attachment.display_location.startswith("data:")
		assert "..." in data_attachment.display_location  # Should be truncated

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


class TestAttachmentFileReadMethods:
	"""Comprehensive tests for the refactored read methods."""

	def test_read_methods_consistency(self, tmp_path):
		"""Test that both read methods return consistent data."""
		test_file_path = UPath(tmp_path) / "consistency_test.txt"
		test_content = "Hello, World! 123 @#$%"

		with test_file_path.open("w", encoding="utf-8") as f:
			f.write(test_content)

		attachment = AttachmentFile(location=test_file_path)

		# Read as text and as bytes
		text_content = attachment.read_as_plain_text()
		binary_content = attachment.read_as_bytes()

		# They should represent the same data
		assert text_content == test_content
		assert binary_content == test_content.encode("utf-8")
		assert text_content == binary_content.decode("utf-8")

	def test_read_file_method_caching_behavior(self, text_file):
		"""Test that multiple calls to read methods return consistent results."""
		attachment = AttachmentFile(location=text_file)

		# Multiple calls should return the same content
		first_text = attachment.read_as_plain_text()
		second_text = attachment.read_as_plain_text()
		first_bytes = attachment.read_as_bytes()
		second_bytes = attachment.read_as_bytes()

		assert first_text == second_text == "test content"
		assert first_bytes == second_bytes == b"test content"

	def test_read_file_with_different_encodings(self, tmp_path):
		"""Test reading files with different text encodings."""
		# Test with UTF-8 (default)
		utf8_file = UPath(tmp_path) / "utf8.txt"
		utf8_content = "UTF-8: Hello 世界 🌍"
		with utf8_file.open("w", encoding="utf-8") as f:
			f.write(utf8_content)

		utf8_attachment = AttachmentFile(location=utf8_file)
		text_content = utf8_attachment.read_as_plain_text()
		assert text_content == utf8_content

		# Binary read should return UTF-8 encoded bytes
		binary_content = utf8_attachment.read_as_bytes()
		assert binary_content == utf8_content.encode("utf-8")

	def test_internal_read_file_method_directly(self, tmp_path):
		"""Test the internal _read_file method with various scenarios."""
		test_file_path = UPath(tmp_path) / "internal_test.txt"
		test_content = "Internal method test content"

		with test_file_path.open("w") as f:
			f.write(test_content)

		attachment = AttachmentFile(location=test_file_path)

		# Test text mode
		text_result = attachment._read_file("r")
		assert text_result == test_content
		assert isinstance(text_result, str)

		# Test binary mode
		binary_result = attachment._read_file("rb")
		assert binary_result == test_content.encode("utf-8")
		assert isinstance(binary_result, bytes)

		# Test text mode with explicit flag
		text_explicit = attachment._read_file("rt")
		assert text_explicit == test_content
		assert isinstance(text_explicit, str)

	def test_send_location_property_with_read_methods(self, tmp_path):
		"""Test that read methods use send_location property correctly."""
		test_file_path = UPath(tmp_path) / "send_location_test.txt"
		test_content = "Send location test"

		with test_file_path.open("w") as f:
			f.write(test_content)

		attachment = AttachmentFile(location=test_file_path)

		# Verify send_location is used (it should be the same as location for regular files)
		assert attachment.send_location == attachment.location

		# Read methods should work through send_location
		text_content = attachment.read_as_plain_text()
		binary_content = attachment.read_as_bytes()

		assert text_content == test_content
		assert binary_content == test_content.encode("utf-8")

	@pytest.mark.parametrize(
		"file_content,expected_size",
		[
			("", 0),  # Empty file
			("a", 1),  # Single character
			("Hello, World!", 13),  # Regular text
			("🌍" * 100, 400),  # Unicode characters (4 bytes each in UTF-8)
		],
		ids=["empty", "single_char", "regular_text", "unicode_text"],
	)
	def test_read_methods_with_various_content_sizes(
		self, tmp_path, file_content, expected_size
	):
		"""Test read methods with various content sizes."""
		test_file_path = UPath(tmp_path) / "size_test.txt"

		with test_file_path.open("w", encoding="utf-8") as f:
			f.write(file_content)

		attachment = AttachmentFile(location=test_file_path)

		# Test text reading
		text_content = attachment.read_as_plain_text()
		assert text_content == file_content
		assert len(text_content) == len(file_content)

		# Test binary reading
		binary_content = attachment.read_as_bytes()
		assert binary_content == file_content.encode("utf-8")
		assert len(binary_content) == expected_size
