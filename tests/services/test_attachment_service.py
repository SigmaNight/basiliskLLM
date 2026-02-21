"""Tests for AttachmentService."""

import threading
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image as PILImage

from basilisk.conversation import AttachmentFile, ImageFile
from basilisk.services.attachment_service import AttachmentService

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def make_attachment(
	mime_type: str, location: str = "file.bin"
) -> AttachmentFile:
	"""Return a mock attachment with the given MIME type."""
	att = MagicMock(spec=AttachmentFile)
	att.mime_type = mime_type
	att.location = location
	return att


def make_image_attachment(location: str = "img.png") -> MagicMock:
	"""Return a mock ImageFile attachment."""
	att = MagicMock(spec=ImageFile)
	att.mime_type = "image/png"
	att.location = location
	return att


@pytest.fixture
def success_cb():
	"""Return a mock success callback."""
	return MagicMock()


@pytest.fixture
def error_cb():
	"""Return a mock error callback."""
	return MagicMock()


@pytest.fixture
def service(success_cb, error_cb):
	"""Return an AttachmentService with mock callbacks."""
	return AttachmentService(
		on_download_success=success_cb, on_download_error=error_cb
	)


# ---------------------------------------------------------------------------
# Static: is_format_supported
# ---------------------------------------------------------------------------


class TestIsFormatSupported:
	"""Tests for AttachmentService.is_format_supported."""

	def test_known_mime_type(self):
		"""Known MIME type returns True."""
		assert AttachmentService.is_format_supported(
			"image/png", {"image/png", "image/jpeg"}
		)

	def test_unknown_mime_type(self):
		"""Unknown MIME type returns False."""
		assert not AttachmentService.is_format_supported(
			"application/pdf", {"image/png"}
		)

	def test_none_mime_type(self):
		"""None MIME type returns False."""
		assert not AttachmentService.is_format_supported(None, {"image/png"})

	def test_empty_supported_set(self):
		"""Empty supported set always returns False."""
		assert not AttachmentService.is_format_supported("image/png", set())


# ---------------------------------------------------------------------------
# Static: build_attachment_from_path
# ---------------------------------------------------------------------------


class TestBuildAttachmentFromPath:
	"""Tests for AttachmentService.build_attachment_from_path."""

	def test_image_returns_image_file(self, tmp_path):
		"""An image MIME type should produce an ImageFile."""
		p = tmp_path / "photo.png"
		img = PILImage.new("RGB", (10, 10), color="red")
		img.save(str(p))
		supported = {"image/png"}

		with patch(
			"basilisk.services.attachment_service.get_mime_type",
			return_value="image/png",
		):
			attachment, err = AttachmentService.build_attachment_from_path(
				str(p), supported
			)

		assert isinstance(attachment, ImageFile)
		assert err is None

	def test_text_returns_attachment_file(self, tmp_path):
		"""A text MIME type should produce an AttachmentFile."""
		p = tmp_path / "notes.txt"
		p.touch()
		supported = {"text/plain"}

		with patch(
			"basilisk.services.attachment_service.get_mime_type",
			return_value="text/plain",
		):
			attachment, err = AttachmentService.build_attachment_from_path(
				str(p), supported
			)

		assert isinstance(attachment, AttachmentFile)
		assert err is None

	def test_unsupported_format_returns_none_and_mime(self, tmp_path):
		"""An unsupported MIME type returns (None, mime_type)."""
		p = tmp_path / "archive.zip"
		p.touch()
		supported = {"image/png"}

		with patch(
			"basilisk.services.attachment_service.get_mime_type",
			return_value="application/zip",
		):
			attachment, err = AttachmentService.build_attachment_from_path(
				str(p), supported
			)

		assert attachment is None
		assert err == "application/zip"


# ---------------------------------------------------------------------------
# Static: validate_attachments
# ---------------------------------------------------------------------------


class TestValidateAttachments:
	"""Tests for AttachmentService.validate_attachments."""

	def test_all_valid(self):
		"""All supported attachments → empty list."""
		att = make_attachment("image/png")
		result = AttachmentService.validate_attachments([att], {"image/png"})
		assert result == []

	def test_partially_invalid(self):
		"""One invalid attachment → its location in the returned list."""
		valid = make_attachment("image/png", "ok.png")
		invalid = make_attachment("application/zip", "bad.zip")
		result = AttachmentService.validate_attachments(
			[valid, invalid], {"image/png"}
		)
		assert result == ["bad.zip"]

	def test_all_invalid(self):
		"""All invalid attachments → all locations returned."""
		att1 = make_attachment("application/zip", "a.zip")
		att2 = make_attachment("application/pdf", "b.pdf")
		result = AttachmentService.validate_attachments(
			[att1, att2], {"image/png"}
		)
		assert set(result) == {"a.zip", "b.pdf"}


# ---------------------------------------------------------------------------
# Static: check_model_vision_compatible
# ---------------------------------------------------------------------------


class TestCheckModelVisionCompatible:
	"""Tests for AttachmentService.check_model_vision_compatible."""

	def test_no_images_always_compatible(self):
		"""No image attachments → always compatible regardless of model."""
		att = make_attachment("text/plain")
		model = MagicMock()
		model.vision = False
		engine = MagicMock()

		ok, names = AttachmentService.check_model_vision_compatible(
			[att], model, engine
		)
		assert ok is True
		assert names is None

	def test_model_has_vision_compatible(self):
		"""Model with vision=True → compatible even with images."""
		att = make_image_attachment()
		model = MagicMock()
		model.vision = True
		engine = MagicMock()

		ok, names = AttachmentService.check_model_vision_compatible(
			[att], model, engine
		)
		assert ok is True
		assert names is None

	def test_model_no_vision_with_images_returns_vision_models(self):
		"""Model without vision + images → False + list of vision model names."""
		att = make_image_attachment()
		model = MagicMock()
		model.vision = False

		vision_m = MagicMock()
		vision_m.vision = True
		vision_m.name = "gpt-4-vision"

		non_vision_m = MagicMock()
		non_vision_m.vision = False
		non_vision_m.name = "gpt-3.5"

		engine = MagicMock()
		engine.models = [vision_m, non_vision_m]

		ok, names = AttachmentService.check_model_vision_compatible(
			[att], model, engine
		)
		assert ok is False
		assert names == ["gpt-4-vision"]


# ---------------------------------------------------------------------------
# Static: resize_attachments
# ---------------------------------------------------------------------------


class TestResizeAttachments:
	"""Tests for AttachmentService.resize_attachments."""

	def test_skip_non_image(self):
		"""Non-image attachments should not have resize called."""
		# Use plain MagicMock (AttachmentFile has no resize method)
		att = MagicMock()
		att.mime_type = "text/plain"
		AttachmentService.resize_attachments([att], "/storage", 800, 600, 85)
		att.resize.assert_not_called()

	def test_resize_called_on_image(self):
		"""Image attachments should have resize called with correct args."""
		att = make_image_attachment()
		AttachmentService.resize_attachments([att], "/storage", 800, 600, 85)
		att.resize.assert_called_once_with("/storage", 800, 600, 85)

	def test_continue_on_individual_error(self):
		"""An error on one attachment should not abort the rest."""
		bad = make_image_attachment("bad.png")
		bad.resize.side_effect = RuntimeError("disk full")
		good = make_image_attachment("good.png")

		AttachmentService.resize_attachments(
			[bad, good], "/storage", 800, 600, 85
		)

		good.resize.assert_called_once()

	def test_skip_none_mime_type(self):
		"""Attachments with None mime_type are skipped."""
		att = MagicMock()
		att.mime_type = None
		AttachmentService.resize_attachments([att], "/storage", 800, 600, 85)
		att.resize.assert_not_called()


# ---------------------------------------------------------------------------
# Instance: async download
# ---------------------------------------------------------------------------


class TestDownloadFromUrl:
	"""Tests for the async download interface."""

	def _run_and_wait(self, service, url):
		"""Start a download and wait for the thread to finish."""
		service.download_from_url(url)
		if service.task:
			service.task.join(timeout=5)

	def test_success_calls_on_download_success(self, service, success_cb):
		"""On a successful download the success callback is called."""
		fake_attachment = MagicMock(spec=AttachmentFile)

		with (
			patch(
				"basilisk.services.attachment_service.build_from_url",
				return_value=fake_attachment,
			),
			patch(
				"basilisk.services.attachment_service.wx.CallAfter"
			) as mock_ca,
		):
			self._run_and_wait(service, "https://example.com/file.png")

		mock_ca.assert_called_once_with(success_cb, fake_attachment)

	def test_http_error_calls_on_download_error(self, service, error_cb):
		"""An HTTPError should trigger the error callback with an HTTP message."""
		from httpx import HTTPError

		with (
			patch(
				"basilisk.services.attachment_service.build_from_url",
				side_effect=HTTPError("404"),
			),
			patch(
				"basilisk.services.attachment_service.wx.CallAfter"
			) as mock_ca,
		):
			self._run_and_wait(service, "https://example.com/missing.png")

		assert mock_ca.call_count == 1
		args = mock_ca.call_args[0]
		assert args[0] is error_cb
		assert "HTTP error" in args[1]

	def test_generic_exception_calls_on_download_error(self, service, error_cb):
		"""A generic exception should trigger the error callback."""
		with (
			patch(
				"basilisk.services.attachment_service.build_from_url",
				side_effect=ValueError("bad url"),
			),
			patch(
				"basilisk.services.attachment_service.wx.CallAfter"
			) as mock_ca,
		):
			self._run_and_wait(service, "https://example.com/bad")

		assert mock_ca.call_count == 1
		args = mock_ca.call_args[0]
		assert args[0] is error_cb

	def test_task_reset_to_none_after_success(self, service):
		"""The task attribute should be None after the thread completes."""
		fake_attachment = MagicMock(spec=AttachmentFile)

		with (
			patch(
				"basilisk.services.attachment_service.build_from_url",
				return_value=fake_attachment,
			),
			patch("basilisk.services.attachment_service.wx.CallAfter"),
		):
			self._run_and_wait(service, "https://example.com/ok.png")

		assert service.task is None

	def test_task_reset_to_none_after_error(self, service):
		"""The task attribute should be None after a failed download too."""
		with (
			patch(
				"basilisk.services.attachment_service.build_from_url",
				side_effect=RuntimeError("oops"),
			),
			patch("basilisk.services.attachment_service.wx.CallAfter"),
		):
			self._run_and_wait(service, "https://example.com/bad")

		assert service.task is None

	def test_blocked_when_task_already_running(self, service):
		"""A second download_from_url call while busy should be rejected."""
		# Simulate an active task
		mock_thread = MagicMock(spec=threading.Thread)
		mock_thread.is_alive.return_value = True
		service.task = mock_thread

		with patch(
			"basilisk.services.attachment_service.wx.MessageBox"
		) as mock_mb:
			service.download_from_url("https://example.com/file.png")

		# The error message box should have been shown
		mock_mb.assert_called_once()
		# The old task is unchanged
		assert service.task is mock_thread
