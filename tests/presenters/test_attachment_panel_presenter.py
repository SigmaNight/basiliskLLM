"""Tests for PromptAttachmentPresenter."""

from unittest.mock import MagicMock

import pytest
from upath import UPath

from basilisk.presenters.attachment_panel_presenter import (
	PromptAttachmentPresenter,
)


def _make_engine(supported_formats=None, vision_models=None):
	"""Build a mock engine with configurable formats and vision models.

	Args:
		supported_formats: Set of accepted MIME type strings.
		vision_models: List of mock model objects that have .vision=True.
	"""
	engine = MagicMock()
	engine.supported_attachment_formats = supported_formats or {
		"image/png",
		"image/jpeg",
		"text/plain",
	}
	if vision_models is not None:
		engine.models = vision_models
	else:
		vision = MagicMock()
		vision.vision = True
		vision.name = "vision-model"
		engine.models = [vision]
	return engine


@pytest.fixture
def mock_engine():
	"""Build a mock engine with image/png, image/jpeg and text/plain support."""
	return _make_engine()


@pytest.fixture
def mock_view():
	"""Build a mock view with sensible defaults."""
	view = MagicMock()
	view.show_file_dialog.return_value = None
	view.show_url_dialog.return_value = None
	return view


@pytest.fixture
def presenter(mock_view):
	"""Build a PromptAttachmentPresenter with a mock view."""
	return PromptAttachmentPresenter(
		view=mock_view, conv_storage_path=UPath("/tmp/test_conv")
	)


class TestPromptAttachmentPresenterInitialState:
	"""Tests for the initial state of PromptAttachmentPresenter."""

	def test_attachment_files_empty(self, presenter):
		"""attachment_files starts as an empty list."""
		assert presenter.attachment_files == []

	def test_current_engine_none(self, presenter):
		"""current_engine starts as None."""
		assert presenter.current_engine is None

	def test_has_image_attachments_false_when_empty(self, presenter):
		"""has_image_attachments() returns False when no attachments."""
		assert presenter.has_image_attachments() is False


class TestPromptAttachmentPresenterState:
	"""Tests for state management methods."""

	def test_set_engine_assigns(self, presenter, mock_engine):
		"""set_engine() assigns the engine."""
		presenter.set_engine(mock_engine)
		assert presenter.current_engine is mock_engine

	def test_clear_resets_attachment_files(self, presenter):
		"""clear() resets attachment_files to an empty list."""
		presenter.attachment_files = [MagicMock()]
		presenter.clear()
		assert presenter.attachment_files == []

	def test_refresh_view_calls_display(self, presenter, mock_view):
		"""refresh_view() calls view.refresh_attachments_display with the current files."""
		sentinel = [MagicMock()]
		presenter.attachment_files = sentinel
		presenter.refresh_view()
		mock_view.refresh_attachments_display.assert_called_once_with(sentinel)


class TestAddAttachmentsNoEngine:
	"""Tests for add_attachments when no engine is set."""

	def test_shows_error_when_no_engine(self, presenter, mock_view):
		"""add_attachments() shows an error and returns early when current_engine is None."""
		presenter.add_attachments(["/some/file.txt"])
		mock_view.show_error.assert_called_once()
		assert presenter.attachment_files == []


class TestAddAttachmentsWithEngine:
	"""Tests for add_attachments when an engine is configured."""

	def test_adds_valid_path(self, presenter, mock_view, mocker):
		"""add_attachments() adds a file when its MIME type is supported."""
		presenter.set_engine(_make_engine(supported_formats={"image/png"}))

		mock_attachment = MagicMock()
		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
			return_value=(mock_attachment, None),
		)
		presenter.add_attachments(["/path/to/image.png"])

		assert mock_attachment in presenter.attachment_files
		mock_view.refresh_attachments_display.assert_called()
		mock_view.focus_attachments.assert_called()

	def test_shows_error_for_unsupported_format(
		self, presenter, mock_view, mocker
	):
		"""add_attachments() shows an error and skips unsupported MIME types."""
		presenter.set_engine(_make_engine(supported_formats={"image/png"}))

		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
			return_value=(None, "application/pdf"),
		)
		presenter.add_attachments(["/path/to/file.pdf"])

		mock_view.show_error.assert_called_once()
		assert presenter.attachment_files == []

	def test_adds_attachment_object_directly(self, presenter, mock_engine):
		"""add_attachments() appends pre-built attachment objects without validation."""
		from basilisk.conversation import AttachmentFile

		presenter.set_engine(mock_engine)

		attachment = MagicMock(spec=AttachmentFile)
		presenter.add_attachments([attachment])

		assert attachment in presenter.attachment_files


class TestHasImageAttachments:
	"""Tests for has_image_attachments()."""

	def test_true_when_image_present(self, presenter):
		"""has_image_attachments() returns True when an image attachment exists."""
		img = MagicMock()
		img.mime_type = "image/png"
		presenter.attachment_files = [img]
		assert presenter.has_image_attachments() is True

	def test_false_when_only_text(self, presenter):
		"""has_image_attachments() returns False when only non-image attachments exist."""
		txt = MagicMock()
		txt.mime_type = "text/plain"
		presenter.attachment_files = [txt]
		assert presenter.has_image_attachments() is False

	def test_false_when_mime_none(self, presenter):
		"""has_image_attachments() returns False when MIME type is None."""
		att = MagicMock()
		att.mime_type = None
		presenter.attachment_files = [att]
		assert presenter.has_image_attachments() is False


class TestCheckAttachmentsValid:
	"""Tests for check_attachments_valid()."""

	def test_returns_false_when_no_engine(self, presenter):
		"""check_attachments_valid() returns False when no engine is set."""
		assert presenter.check_attachments_valid() is False

	def test_returns_true_when_all_valid(self, presenter, mock_view, mocker):
		"""check_attachments_valid() returns True when all attachments pass validation."""
		presenter.set_engine(_make_engine(supported_formats={"image/png"}))

		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.validate_attachments",
			return_value=[],
		)
		result = presenter.check_attachments_valid()

		assert result is True
		mock_view.show_error.assert_not_called()

	def test_shows_error_for_invalid_attachment(
		self, presenter, mock_view, mocker
	):
		"""check_attachments_valid() shows an error and returns False for invalid attachments."""
		presenter.set_engine(_make_engine())

		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.validate_attachments",
			return_value=["/bad/file.xyz"],
		)
		result = presenter.check_attachments_valid()

		assert result is False
		mock_view.show_error.assert_called_once()


class TestEnsureModelCompatibility:
	"""Tests for ensure_model_compatibility()."""

	def test_none_model_shows_error(self, presenter, mock_view):
		"""ensure_model_compatibility() shows error and returns None when model is None."""
		result = presenter.ensure_model_compatibility(None)
		mock_view.show_error.assert_called_once()
		assert result is None

	@pytest.mark.parametrize(
		("compat_result", "expect_result", "expect_error"),
		[((True, None), True, False), ((False, ["vision-model"]), False, True)],
		ids=["compatible", "incompatible"],
	)
	def test_model_compatibility(
		self,
		presenter,
		mock_view,
		mocker,
		compat_result,
		expect_result,
		expect_error,
	):
		"""ensure_model_compatibility returns model on success or None on failure."""
		presenter.set_engine(_make_engine())
		model = MagicMock()
		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.check_model_vision_compatible",
			return_value=compat_result,
		)
		result = presenter.ensure_model_compatibility(model)
		assert (result is model) is expect_result
		if expect_error:
			mock_view.show_error.assert_called_once()
		else:
			mock_view.show_error.assert_not_called()


class TestOnPasteText:
	"""Tests for on_paste_text()."""

	def test_url_triggers_download(self, presenter, mock_view, mocker):
		"""on_paste_text() starts a URL download when text is a valid URL."""
		url = "https://example.com/image.png"
		mock_download = mocker.patch.object(
			presenter.attachment_service, "download_from_url"
		)
		presenter.on_paste_text(url)

		mock_download.assert_called_once_with(url)
		mock_view.write_prompt_text.assert_not_called()

	def test_plain_text_written_to_prompt(self, presenter, mock_view):
		"""on_paste_text() writes plain text to the prompt."""
		presenter.on_paste_text("hello world")
		mock_view.write_prompt_text.assert_called_once_with("hello world")


class TestOnAddUrl:
	"""Tests for on_add_url()."""

	def test_invalid_url_shows_error(self, presenter, mock_view):
		"""on_add_url() shows an error for an invalid URL."""
		mock_view.show_url_dialog.return_value = "not-a-url"
		presenter.on_add_url()
		mock_view.show_error.assert_called_once()

	def test_valid_url_triggers_download(self, presenter, mock_view, mocker):
		"""on_add_url() starts download for a valid URL."""
		url = "https://example.com/file.png"
		mock_view.show_url_dialog.return_value = url
		mock_download = mocker.patch.object(
			presenter.attachment_service, "download_from_url"
		)
		presenter.on_add_url()

		mock_download.assert_called_once_with(url)
		mock_view.show_error.assert_not_called()

	def test_cancelled_dialog_returns_early(self, presenter, mock_view, mocker):
		"""on_add_url() does nothing when the dialog is cancelled."""
		mock_view.show_url_dialog.return_value = None
		mock_download = mocker.patch.object(
			presenter.attachment_service, "download_from_url"
		)
		presenter.on_add_url()

		mock_download.assert_not_called()
		mock_view.show_error.assert_not_called()


class TestOnAddFiles:
	"""Tests for on_add_files()."""

	def test_no_engine_shows_error(self, presenter, mock_view):
		"""on_add_files() shows an error when no engine is set."""
		presenter.on_add_files()
		mock_view.show_error.assert_called_once()
		mock_view.show_file_dialog.assert_not_called()

	def test_no_supported_formats_shows_error(
		self, presenter, mock_view, mocker
	):
		"""on_add_files() shows error when engine has no supported formats."""
		presenter.set_engine(_make_engine(supported_formats=set()))

		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
			return_value="",
		)
		presenter.on_add_files()

		mock_view.show_error.assert_called_once()
		mock_view.show_file_dialog.assert_not_called()

	def test_cancelled_dialog_adds_nothing(self, presenter, mock_view, mocker):
		"""on_add_files() does nothing when the file dialog is cancelled."""
		mock_view.show_file_dialog.return_value = None
		presenter.set_engine(_make_engine())

		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
			return_value="*.png;*.jpg",
		)
		presenter.on_add_files()

		assert presenter.attachment_files == []

	def test_valid_selection_calls_add_attachments(
		self, presenter, mock_view, mocker
	):
		"""on_add_files() calls add_attachments with the selected paths."""
		mock_view.show_file_dialog.return_value = ["/img/photo.png"]
		presenter.set_engine(_make_engine(supported_formats={"image/png"}))

		mock_attachment = MagicMock()
		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
			return_value="*.png",
		)
		mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
			return_value=(mock_attachment, None),
		)
		presenter.on_add_files()

		assert mock_attachment in presenter.attachment_files


class TestOnAttachmentDownloadError:
	"""Tests for _on_attachment_download_error()."""

	def test_shows_error_with_message(self, presenter, mock_view):
		"""_on_attachment_download_error() calls view.show_error with the message."""
		presenter._on_attachment_download_error("HTTP error 404.")
		mock_view.show_error.assert_called_once_with("HTTP error 404.")


class TestOnAttachmentDownloaded:
	"""Tests for _on_attachment_downloaded()."""

	def test_adds_downloaded_attachment(self, presenter, mock_engine):
		"""_on_attachment_downloaded() adds the attachment to the list."""
		from basilisk.conversation import AttachmentFile

		presenter.set_engine(mock_engine)

		attachment = MagicMock(spec=AttachmentFile)
		presenter._on_attachment_downloaded(attachment)

		assert attachment in presenter.attachment_files


class TestResizeAllAttachments:
	"""Tests for resize_all_attachments()."""

	def test_no_op_when_resize_disabled(self, presenter, mocker):
		"""resize_all_attachments() is a no-op when images.resize is False."""
		conf = MagicMock()
		conf.images.resize = False
		mocker.patch("basilisk.config.conf", return_value=conf)
		mock_resize = mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.resize_attachments"
		)
		presenter.resize_all_attachments()
		mock_resize.assert_not_called()

	def test_calls_resize_when_enabled(self, presenter, mocker):
		"""resize_all_attachments() calls AttachmentService.resize_attachments when enabled."""
		conf = MagicMock()
		conf.images.resize = True
		conf.images.max_width = 1920
		conf.images.max_height = 1080
		conf.images.quality = 85
		mocker.patch("basilisk.config.conf", return_value=conf)
		mock_resize = mocker.patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.resize_attachments"
		)
		presenter.resize_all_attachments()
		mock_resize.assert_called_once()
