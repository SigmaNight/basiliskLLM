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
	parse_supported_attachment_formats,
)


@pytest.mark.parametrize(
	"file_path",
	[
		lambda tmp_path: UPath(tmp_path) / "non_existent_file.txt",
		lambda _: UPath("memory://test.txt"),
	],
)
def test_attachment_file_not_exist(tmp_path: str, file_path: callable):
	"""Test attachment file not exissts."""
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
)
def test_attachment_file_exists(
	tmp_path: str, file_path: callable, expected_type: AttachmentFileTypes
):
	"""Test attachment file exists."""
	test_file_path = file_path(tmp_path)
	with test_file_path.open("w") as f:
		f.write("test")
	attachment = AttachmentFile(location=test_file_path)
	assert attachment.location == test_file_path
	assert attachment.size == 4
	assert attachment.type == expected_type


def test_attachment_display_size(tmp_path: str):
	"""Test attachment file display size formatting."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("a" * 1500)  # Write 1.5KB of data
	attachment = AttachmentFile(location=test_file_path)
	assert attachment.display_size == "1.46 KB"


def test_attachment_mime_type(tmp_path: str):
	"""Test attachment file mime type detection."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("test content")

	attachment = AttachmentFile(location=test_file_path)
	assert attachment.mime_type == "text/plain"


def test_attachment_custom_name(tmp_path: str):
	"""Test attachment file with custom name."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("test")

	custom_name = "custom_file_name.txt"
	attachment = AttachmentFile(location=test_file_path, name=custom_name)
	assert attachment.name == custom_name


def test_attachment_read_as_str(tmp_path: str):
	"""Test reading attachment file as string."""
	test_file_path = UPath(tmp_path) / "test.txt"
	content = "test content"
	with test_file_path.open("w") as f:
		f.write(content)

	attachment = AttachmentFile(location=test_file_path)
	assert attachment.read_as_str() == content


def test_attachment_get_display_info(tmp_path: str):
	"""Test getting display info tuple."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("test")

	attachment = AttachmentFile(location=test_file_path)
	name, size, location = attachment.get_dispay_info()

	assert name == "test.txt"
	assert size == "4 B"
	assert str(test_file_path) in location


@pytest.mark.parametrize(
	"content_size,expected_display",
	[
		(500, "500 B"),
		(1024, "1.00 KB"),
		(1024 * 1024, "1.00 MB"),
		(2 * 1024 * 1024, "2.00 MB"),
	],
)
def test_attachment_various_sizes(
	tmp_path: str, content_size: int, expected_display: str
):
	"""Test attachment file with various sizes."""
	test_file_path = UPath(tmp_path) / "test.txt"
	with test_file_path.open("w") as f:
		f.write("a" * content_size)

	attachment = AttachmentFile(location=test_file_path)
	assert attachment.display_size == expected_display


def test_image_file_dimensions(tmp_path: str):
	"""Test image file dimensions detection."""
	# Create a test image
	test_file_path = UPath(tmp_path) / "test.png"
	with test_file_path.open("wb") as f:
		img = Image.new('RGB', (100, 50))
		img.save(f)

	image = ImageFile(location=test_file_path)
	assert image.dimensions == (100, 50)
	assert image.display_dimensions == "100 x 50"


@pytest.mark.parametrize(
	"img_width,img_height,quality,final_size",
	[
		(200, 100, 85, None),
		(50, 25, 85, (50, 25)),
		(300, 200, 50, None),
		(200, 100, 100, None),
		(200, 100, 0, None),
		(200, 100, 101, None),
		(200, 100, -1, None),
		(-100, 50, 50, (100, 50)),
		(50, -100, 50, (50, 25)),
		(-50, -50, 50, None),
	],
)
def test_image_resize(
	tmp_path: str,
	img_width: int,
	img_height: int,
	quality: int,
	final_size: tuple[int, int] | None,
):
	"""Test image resizing functionality."""
	# Create a test image
	test_file_path = UPath(tmp_path) / "test.png"
	with test_file_path.open("wb") as f:
		img = Image.new('RGB', (200, 100))
		img.save(f)

	image = ImageFile(location=test_file_path)
	conv_folder = UPath(tmp_path) / "conv"
	conv_folder.mkdir()

	image.resize(
		conv_folder, max_width=img_width, max_height=img_height, quality=quality
	)
	if final_size:
		assert image.resize_location is not None
		# Verify resized image dimensions
		with Image.open(image.resize_location) as resized_img:
			assert resized_img.size == final_size
	else:
		assert image.resize_location is None


def test_image_from_url(httpx_mock):
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

	image = ImageFile.build_from_url(test_url)
	assert image.type == AttachmentFileTypes.URL
	assert str(image.location) == test_url


def test_attachment_base64_encoding(tmp_path: str):
	"""Test base64 encoding of attachment file."""
	test_file_path = UPath(tmp_path) / "test.txt"
	content = "Hello, World!"
	with test_file_path.open("w") as f:
		f.write(content)

	attachment = AttachmentFile(location=test_file_path)
	encoded = attachment.encode_base64()
	decoded = base64.b64decode(encoded).decode('utf-8')
	assert decoded == content


@pytest.mark.parametrize(
	"file_name,expected_mime",
	[
		("test.txt", "text/plain"),
		("test.jpg", "image/jpeg"),
		("test.png", "image/png"),
		("test.pdf", "application/pdf"),
	],
)
def test_attachment_mime_types(
	tmp_path: str, file_name: str, expected_mime: str
):
	"""Test MIME type detection for various file types."""
	test_file_path = UPath(tmp_path) / file_name
	with test_file_path.open("w") as f:
		f.write("test content")

	attachment = AttachmentFile(location=test_file_path)
	assert attachment.mime_type == expected_mime


def test_image_display_location_truncation(tmp_path: str):
	"""Test display location truncation for data URLs."""
	# Mock a data URL
	test_location = UPath("data:image/png;base64," + "A" * 100)

	image = ImageFile(location=test_location)
	assert image.type == AttachmentFileTypes.URL
	display_loc = image.display_location
	assert len(display_loc) < 100
	assert "..." in display_loc


@pytest.mark.parametrize(
	"mime_type,expected_wildcard",
	[
		({"image/jpeg"}, "*.jpg;*.jpe;*.jpeg;*.jfif"),
		({"image/jpeg", "image/png"}, "*.jpg;*.jpe;*.jpeg;*.jfif;*.png"),
		({"application/x-unknown"}, ""),
		(set(), ""),
	],
)
def test_parse_supported_attachment_formats(
	mime_type: set[str], expected_wildcard: str
):
	"""Test parsing supported attachment formats."""
	assert parse_supported_attachment_formats(mime_type) == expected_wildcard


def test_encode_image_url(tmp_path: str):
	"""Test base64 encoding of image file."""
	test_file_path = UPath(tmp_path) / "test.png"
	with test_file_path.open("wb") as f:
		img = Image.new('RGB', (100, 50))
		img.save(f)

	image = ImageFile(location=test_file_path)
	encoded = image.url
	assert encoded.startswith("data:image/png;base64,")
	decoded = base64.b64decode(encoded.split(",")[1])
	assert Image.open(BytesIO(decoded)).size == (100, 50)
