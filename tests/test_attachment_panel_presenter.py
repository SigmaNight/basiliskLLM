"""Tests for PromptAttachmentPresenter."""

from unittest.mock import MagicMock, patch

from upath import UPath

from basilisk.presenters.attachment_panel_presenter import (
	PromptAttachmentPresenter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_view():
	"""Build a mock view with sensible defaults."""
	view = MagicMock()
	view.show_file_dialog.return_value = None
	view.show_url_dialog.return_value = None
	return view


def make_engine(supported_formats=None, vision_models=None):
	"""Build a mock engine.

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


def make_presenter(view=None, conv_storage_path=None):
	"""Build a PromptAttachmentPresenter with sensible defaults.

	Args:
		view: Mock view object.
		conv_storage_path: UPath for attachment storage.
	"""
	if view is None:
		view = make_view()
	if conv_storage_path is None:
		conv_storage_path = UPath("/tmp/test_conv")
	return PromptAttachmentPresenter(
		view=view, conv_storage_path=conv_storage_path
	)


# ---------------------------------------------------------------------------
# Initial state
# ---------------------------------------------------------------------------


class TestPromptAttachmentPresenterInitialState:
	"""Tests for the initial state of PromptAttachmentPresenter."""

	def test_attachment_files_empty(self):
		"""attachment_files starts as an empty list."""
		p = make_presenter()
		assert p.attachment_files == []

	def test_current_engine_none(self):
		"""current_engine starts as None."""
		p = make_presenter()
		assert p.current_engine is None

	def test_has_image_attachments_false_when_empty(self):
		"""has_image_attachments() returns False when no attachments."""
		p = make_presenter()
		assert p.has_image_attachments() is False


# ---------------------------------------------------------------------------
# set_engine / clear / refresh_view
# ---------------------------------------------------------------------------


class TestPromptAttachmentPresenterState:
	"""Tests for state management methods."""

	def test_set_engine_assigns(self):
		"""set_engine() assigns the engine."""
		p = make_presenter()
		engine = make_engine()
		p.set_engine(engine)
		assert p.current_engine is engine

	def test_clear_resets_attachment_files(self):
		"""clear() resets attachment_files to an empty list."""
		p = make_presenter()
		p.attachment_files = [MagicMock()]
		p.clear()
		assert p.attachment_files == []

	def test_refresh_view_calls_display(self):
		"""refresh_view() calls view.refresh_attachments_display with the current files."""
		view = make_view()
		p = make_presenter(view=view)
		sentinel = [MagicMock()]
		p.attachment_files = sentinel
		p.refresh_view()
		view.refresh_attachments_display.assert_called_once_with(sentinel)


# ---------------------------------------------------------------------------
# add_attachments — no engine
# ---------------------------------------------------------------------------


class TestAddAttachmentsNoEngine:
	"""Tests for add_attachments when no engine is set."""

	def test_shows_error_when_no_engine(self):
		"""add_attachments() shows an error and returns early when current_engine is None."""
		view = make_view()
		p = make_presenter(view=view)
		p.add_attachments(["/some/file.txt"])
		view.show_error.assert_called_once()
		assert p.attachment_files == []


# ---------------------------------------------------------------------------
# add_attachments — with engine
# ---------------------------------------------------------------------------


class TestAddAttachmentsWithEngine:
	"""Tests for add_attachments when an engine is configured."""

	def test_adds_valid_path(self):
		"""add_attachments() adds a file when its MIME type is supported."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine(supported_formats={"image/png"}))

		mock_attachment = MagicMock()
		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
			return_value=(mock_attachment, None),
		):
			p.add_attachments(["/path/to/image.png"])

		assert mock_attachment in p.attachment_files
		view.refresh_attachments_display.assert_called()
		view.focus_attachments.assert_called()

	def test_shows_error_for_unsupported_format(self):
		"""add_attachments() shows an error and skips unsupported MIME types."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine(supported_formats={"image/png"}))

		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
			return_value=(None, "application/pdf"),
		):
			p.add_attachments(["/path/to/file.pdf"])

		view.show_error.assert_called_once()
		assert p.attachment_files == []

	def test_adds_attachment_object_directly(self):
		"""add_attachments() appends pre-built attachment objects without validation."""
		from basilisk.conversation import AttachmentFile

		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		attachment = MagicMock(spec=AttachmentFile)
		p.add_attachments([attachment])

		assert attachment in p.attachment_files


# ---------------------------------------------------------------------------
# has_image_attachments
# ---------------------------------------------------------------------------


class TestHasImageAttachments:
	"""Tests for has_image_attachments()."""

	def test_true_when_image_present(self):
		"""has_image_attachments() returns True when an image attachment exists."""
		p = make_presenter()
		img = MagicMock()
		img.mime_type = "image/png"
		p.attachment_files = [img]
		assert p.has_image_attachments() is True

	def test_false_when_only_text(self):
		"""has_image_attachments() returns False when only non-image attachments exist."""
		p = make_presenter()
		txt = MagicMock()
		txt.mime_type = "text/plain"
		p.attachment_files = [txt]
		assert p.has_image_attachments() is False

	def test_false_when_mime_none(self):
		"""has_image_attachments() returns False when MIME type is None."""
		p = make_presenter()
		att = MagicMock()
		att.mime_type = None
		p.attachment_files = [att]
		assert p.has_image_attachments() is False


# ---------------------------------------------------------------------------
# check_attachments_valid
# ---------------------------------------------------------------------------


class TestCheckAttachmentsValid:
	"""Tests for check_attachments_valid()."""

	def test_returns_false_when_no_engine(self):
		"""check_attachments_valid() returns False when no engine is set."""
		p = make_presenter()
		assert p.check_attachments_valid() is False

	def test_returns_true_when_all_valid(self):
		"""check_attachments_valid() returns True when all attachments pass validation."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine(supported_formats={"image/png"}))

		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.validate_attachments",
			return_value=[],
		):
			result = p.check_attachments_valid()

		assert result is True
		view.show_error.assert_not_called()

	def test_shows_error_for_invalid_attachment(self):
		"""check_attachments_valid() shows an error and returns False for invalid attachments."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.validate_attachments",
			return_value=["/bad/file.xyz"],
		):
			result = p.check_attachments_valid()

		assert result is False
		view.show_error.assert_called_once()


# ---------------------------------------------------------------------------
# ensure_model_compatibility
# ---------------------------------------------------------------------------


class TestEnsureModelCompatibility:
	"""Tests for ensure_model_compatibility()."""

	def test_none_model_shows_error(self):
		"""ensure_model_compatibility() shows error and returns None when model is None."""
		view = make_view()
		p = make_presenter(view=view)
		result = p.ensure_model_compatibility(None)
		view.show_error.assert_called_once()
		assert result is None

	def test_compatible_model_returned(self):
		"""ensure_model_compatibility() returns the model when it is compatible."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		model = MagicMock()
		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.check_model_vision_compatible",
			return_value=(True, None),
		):
			result = p.ensure_model_compatibility(model)

		assert result is model
		view.show_error.assert_not_called()

	def test_incompatible_model_shows_error(self):
		"""ensure_model_compatibility() shows error and returns None for non-vision model with images."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		model = MagicMock()
		with patch(
			"basilisk.presenters.attachment_panel_presenter.AttachmentService.check_model_vision_compatible",
			return_value=(False, ["vision-model"]),
		):
			result = p.ensure_model_compatibility(model)

		assert result is None
		view.show_error.assert_called_once()


# ---------------------------------------------------------------------------
# on_paste_text
# ---------------------------------------------------------------------------


class TestOnPasteText:
	"""Tests for on_paste_text()."""

	def test_url_triggers_download(self):
		"""on_paste_text() starts a URL download when text is a valid URL."""
		view = make_view()
		p = make_presenter(view=view)
		url = "https://example.com/image.png"

		with patch.object(
			p.attachment_service, "download_from_url"
		) as mock_download:
			p.on_paste_text(url)

		mock_download.assert_called_once_with(url)
		view.write_prompt_text.assert_not_called()

	def test_plain_text_written_to_prompt(self):
		"""on_paste_text() writes plain text to the prompt."""
		view = make_view()
		p = make_presenter(view=view)

		p.on_paste_text("hello world")

		view.write_prompt_text.assert_called_once_with("hello world")


# ---------------------------------------------------------------------------
# on_add_url
# ---------------------------------------------------------------------------


class TestOnAddUrl:
	"""Tests for on_add_url()."""

	def test_invalid_url_shows_error(self):
		"""on_add_url() shows an error for an invalid URL."""
		view = make_view()
		view.show_url_dialog.return_value = "not-a-url"
		p = make_presenter(view=view)

		p.on_add_url()

		view.show_error.assert_called_once()

	def test_valid_url_triggers_download(self):
		"""on_add_url() starts download for a valid URL."""
		view = make_view()
		url = "https://example.com/file.png"
		view.show_url_dialog.return_value = url
		p = make_presenter(view=view)

		with patch.object(
			p.attachment_service, "download_from_url"
		) as mock_download:
			p.on_add_url()

		mock_download.assert_called_once_with(url)
		view.show_error.assert_not_called()

	def test_cancelled_dialog_returns_early(self):
		"""on_add_url() does nothing when the dialog is cancelled."""
		view = make_view()
		view.show_url_dialog.return_value = None
		p = make_presenter(view=view)

		with patch.object(
			p.attachment_service, "download_from_url"
		) as mock_download:
			p.on_add_url()

		mock_download.assert_not_called()
		view.show_error.assert_not_called()


# ---------------------------------------------------------------------------
# on_add_files
# ---------------------------------------------------------------------------


class TestOnAddFiles:
	"""Tests for on_add_files()."""

	def test_no_engine_shows_error(self):
		"""on_add_files() shows an error when no engine is set."""
		view = make_view()
		p = make_presenter(view=view)
		p.on_add_files()
		view.show_error.assert_called_once()
		view.show_file_dialog.assert_not_called()

	def test_no_supported_formats_shows_error(self):
		"""on_add_files() shows error when engine has no supported formats."""
		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine(supported_formats=set()))

		with patch(
			"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
			return_value="",
		):
			p.on_add_files()

		view.show_error.assert_called_once()
		view.show_file_dialog.assert_not_called()

	def test_cancelled_dialog_adds_nothing(self):
		"""on_add_files() does nothing when the file dialog is cancelled."""
		view = make_view()
		view.show_file_dialog.return_value = None
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		with patch(
			"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
			return_value="*.png;*.jpg",
		):
			p.on_add_files()

		assert p.attachment_files == []

	def test_valid_selection_calls_add_attachments(self):
		"""on_add_files() calls add_attachments with the selected paths."""
		view = make_view()
		view.show_file_dialog.return_value = ["/img/photo.png"]
		p = make_presenter(view=view)
		p.set_engine(make_engine(supported_formats={"image/png"}))

		mock_attachment = MagicMock()
		with (
			patch(
				"basilisk.presenters.attachment_panel_presenter.parse_supported_attachment_formats",
				return_value="*.png",
			),
			patch(
				"basilisk.presenters.attachment_panel_presenter.AttachmentService.build_attachment_from_path",
				return_value=(mock_attachment, None),
			),
		):
			p.on_add_files()

		assert mock_attachment in p.attachment_files


# ---------------------------------------------------------------------------
# _on_attachment_download_error
# ---------------------------------------------------------------------------


class TestOnAttachmentDownloadError:
	"""Tests for _on_attachment_download_error()."""

	def test_shows_error_with_message(self):
		"""_on_attachment_download_error() calls view.show_error with the message."""
		view = make_view()
		p = make_presenter(view=view)
		p._on_attachment_download_error("HTTP error 404.")
		view.show_error.assert_called_once_with("HTTP error 404.")


# ---------------------------------------------------------------------------
# _on_attachment_downloaded
# ---------------------------------------------------------------------------


class TestOnAttachmentDownloaded:
	"""Tests for _on_attachment_downloaded()."""

	def test_adds_downloaded_attachment(self):
		"""_on_attachment_downloaded() adds the attachment to the list."""
		from basilisk.conversation import AttachmentFile

		view = make_view()
		p = make_presenter(view=view)
		p.set_engine(make_engine())

		attachment = MagicMock(spec=AttachmentFile)
		p._on_attachment_downloaded(attachment)

		assert attachment in p.attachment_files


# ---------------------------------------------------------------------------
# resize_all_attachments
# ---------------------------------------------------------------------------


class TestResizeAllAttachments:
	"""Tests for resize_all_attachments()."""

	def test_no_op_when_resize_disabled(self):
		"""resize_all_attachments() is a no-op when images.resize is False."""
		p = make_presenter()
		conf = MagicMock()
		conf.images.resize = False
		with (
			patch("basilisk.config.conf", return_value=conf),
			patch(
				"basilisk.presenters.attachment_panel_presenter.AttachmentService.resize_attachments"
			) as mock_resize,
		):
			p.resize_all_attachments()

		mock_resize.assert_not_called()

	def test_calls_resize_when_enabled(self):
		"""resize_all_attachments() calls AttachmentService.resize_attachments when enabled."""
		p = make_presenter()
		conf = MagicMock()
		conf.images.resize = True
		conf.images.max_width = 1920
		conf.images.max_height = 1080
		conf.images.quality = 85
		with (
			patch("basilisk.config.conf", return_value=conf),
			patch(
				"basilisk.presenters.attachment_panel_presenter.AttachmentService.resize_attachments"
			) as mock_resize,
		):
			p.resize_all_attachments()

		mock_resize.assert_called_once()
