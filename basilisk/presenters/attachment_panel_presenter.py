"""Presenter for PromptAttachmentsPanel.

Extracts state and business logic from PromptAttachmentsPanel, leaving
the panel responsible only for widget management and event dispatch.
"""

from __future__ import annotations

import datetime
import logging
import re
from typing import TYPE_CHECKING

import basilisk.config as config
from basilisk.conversation import (
	URL_PATTERN,
	AttachmentFile,
	ImageFile,
	parse_supported_attachment_formats,
)
from basilisk.services.attachment_service import AttachmentService

if TYPE_CHECKING:
	from upath import UPath

	from basilisk.provider_ai_model import ProviderAIModel
	from basilisk.provider_engine.base_engine import BaseEngine
	from basilisk.views.prompt_attachments_panel import PromptAttachmentsPanel

log = logging.getLogger(__name__)


class PromptAttachmentPresenter:
	"""Owns attachment state and business logic for PromptAttachmentsPanel.

	Delegates all UI interactions to the view interface. The view must
	implement the following methods:

	- ``show_error(msg: str) -> None``
	- ``show_file_dialog(wildcard: str) -> list[str] | None``
	- ``show_url_dialog() -> str | None``
	- ``refresh_attachments_display(files: list) -> None``
	- ``write_prompt_text(text: str) -> None``
	- ``get_prompt_text() -> str``
	- ``focus_attachments() -> None``
	- ``get_clipboard_bitmap_image() -> object | None``

	Attributes:
		view: The PromptAttachmentsPanel view.
		conv_storage_path: Path for storing conversation attachments.
		attachment_files: Current list of attachment objects.
		current_engine: Currently selected provider engine.
		attachment_service: Service for async URL downloads.
	"""

	def __init__(
		self, view: PromptAttachmentsPanel, conv_storage_path: UPath
	) -> None:
		"""Initialise the presenter.

		Args:
			view: The PromptAttachmentsPanel view instance.
			conv_storage_path: Path for storing conversation attachments.
		"""
		self.view = view
		self.conv_storage_path = conv_storage_path
		self.attachment_files: list[AttachmentFile | ImageFile] = []
		self.current_engine: BaseEngine | None = None
		self.attachment_service = AttachmentService(
			on_download_success=self._on_attachment_downloaded,
			on_download_error=self._on_attachment_download_error,
		)

	# ------------------------------------------------------------------
	# State management
	# ------------------------------------------------------------------

	def set_engine(self, engine: BaseEngine) -> None:
		"""Set the current engine used for attachment validation.

		Args:
			engine: The provider engine to use.
		"""
		self.current_engine = engine

	def clear(self) -> None:
		"""Reset the attachment list."""
		self.attachment_files = []

	def refresh_view(self) -> None:
		"""Push current attachment state to the view."""
		self.view.refresh_attachments_display(self.attachment_files)

	# ------------------------------------------------------------------
	# Queries
	# ------------------------------------------------------------------

	def has_image_attachments(self) -> bool:
		"""Check if any attachment is an image.

		Returns:
			True if at least one image attachment is present.
		"""
		return any(
			attachment.mime_type and attachment.mime_type.startswith("image/")
			for attachment in self.attachment_files
		)

	# ------------------------------------------------------------------
	# Adding attachments
	# ------------------------------------------------------------------

	def add_attachments(
		self, paths: list[str | AttachmentFile | ImageFile]
	) -> None:
		"""Add one or more attachments.

		Already-built attachment objects are added directly. String paths
		are validated against the current engine's supported formats.

		Args:
			paths: List of file paths (str) or attachment objects.
		"""
		log.debug("Adding attachments: %s", paths)

		if not self.current_engine:
			self.view.show_error(
				_("No engine available. Please select an account.")
			)
			return

		supported_attachment_formats = (
			self.current_engine.supported_attachment_formats
		)

		for path in paths:
			if isinstance(path, (AttachmentFile, ImageFile)):
				self.attachment_files.append(path)
			else:
				attachment, _mime = (
					AttachmentService.build_attachment_from_path(
						str(path), supported_attachment_formats
					)
				)
				if attachment is None:
					self.view.show_error(
						_(
							"This attachment format is not supported by the current provider. Source: \n%s"
						)
						% path
					)
					continue
				self.attachment_files.append(attachment)

		self.view.refresh_attachments_display(self.attachment_files)
		self.view.focus_attachments()

	def on_paste_files(self, paths: list[str]) -> None:
		"""Handle file paths pasted from the clipboard.

		Args:
			paths: List of file paths from the clipboard.
		"""
		self.add_attachments(paths)

	def on_paste_text(self, text: str) -> None:
		"""Handle text pasted from the clipboard.

		If the text is a URL it is downloaded as an attachment; otherwise
		it is inserted into the prompt.

		Args:
			text: The pasted text.
		"""
		if re.fullmatch(URL_PATTERN, text):
			log.info("Pasting URL from clipboard, adding attachment")
			self.attachment_service.download_from_url(text)
		else:
			log.info("Pasting text from clipboard")
			self.view.write_prompt_text(text)

	def on_paste_bitmap(self, image) -> None:
		"""Save a pasted bitmap image and add it as an attachment.

		Args:
			image: A wx.Image (or compatible) object from the clipboard.
		"""
		dt_now = datetime.datetime.now()
		file_name = f"clipboard_{dt_now.strftime('%Y_%m_%d_%H_%M_%S')}.png"
		path = self.conv_storage_path / file_name
		with path.open("wb") as f:
			image.SaveFile(f, self._wx_bitmap_type_png())
		self.add_attachments([ImageFile(location=path)])

	@staticmethod
	def _wx_bitmap_type_png() -> int:
		"""Return wx.BITMAP_TYPE_PNG without importing wx at module level.

		Returns:
			The wx.BITMAP_TYPE_PNG constant value.
		"""
		import wx

		return wx.BITMAP_TYPE_PNG

	# ------------------------------------------------------------------
	# Dialog-driven actions
	# ------------------------------------------------------------------

	def on_add_files(self) -> None:
		"""Open a file-picker dialog and add the selected files."""
		if not self.current_engine:
			self.view.show_error(
				_("No engine available. Please select an account.")
			)
			return

		wildcard = parse_supported_attachment_formats(
			self.current_engine.supported_attachment_formats
		)
		if not wildcard:
			self.view.show_error(
				# Translators: This message is displayed when there are no supported attachment formats.
				_("This provider does not support any attachment formats.")
			)
			return

		wildcard = _("All supported formats (%s)|(%s)") % (wildcard, wildcard)
		paths = self.view.show_file_dialog(wildcard)
		if paths:
			self.add_attachments(paths)

	def on_add_url(self) -> None:
		"""Open a URL-entry dialog and download the attachment."""
		url = self.view.show_url_dialog()
		if not url:
			return

		if not re.fullmatch(URL_PATTERN, url):
			self.view.show_error(_("Invalid URL format."))
			return

		self.attachment_service.download_from_url(url)

	# ------------------------------------------------------------------
	# Validation
	# ------------------------------------------------------------------

	def check_attachments_valid(self) -> bool:
		"""Validate all attachments against the current engine.

		Shows an error for each invalid attachment.

		Returns:
			True if all attachments are valid, False otherwise.
		"""
		if not self.current_engine:
			return False

		supported_attachment_formats = (
			self.current_engine.supported_attachment_formats
		)

		invalid_locations = AttachmentService.validate_attachments(
			self.attachment_files, supported_attachment_formats
		)
		for location in invalid_locations:
			self.view.show_error(
				_(
					"This attachment format is not supported by the current provider. Source: %s"
				)
				% location
			)

		return not invalid_locations

	def ensure_model_compatibility(
		self, current_model: ProviderAIModel | None
	) -> ProviderAIModel | None:
		"""Check that the model supports all current attachments.

		Args:
			current_model: The selected AI model, or None.

		Returns:
			The model if compatible, None otherwise.
		"""
		if not current_model:
			self.view.show_error(_("Please select a model"))
			return None
		if not self.current_engine:
			self.view.show_error(_("Please select an engine"))
			return None
		compatible, vision_models = (
			AttachmentService.check_model_vision_compatible(
				self.attachment_files, current_model, self.current_engine
			)
		)
		if not compatible:
			self.view.show_error(
				_(
					"The selected model does not support images. Please select a vision model instead (%s)."
				)
				% ", ".join(vision_models)
			)
			return None
		return current_model

	def resize_all_attachments(self) -> None:
		"""Resize all image attachments if configured to do so."""
		if not config.conf().images.resize:
			return
		AttachmentService.resize_attachments(
			self.attachment_files,
			self.conv_storage_path,
			config.conf().images.max_width,
			config.conf().images.max_height,
			config.conf().images.quality,
		)

	# ------------------------------------------------------------------
	# Download callbacks (called via wx.CallAfter from worker thread)
	# ------------------------------------------------------------------

	def _on_attachment_downloaded(
		self, attachment: AttachmentFile | ImageFile
	) -> None:
		"""Handle a successful URL download.

		Args:
			attachment: The downloaded attachment object.
		"""
		self.add_attachments([attachment])

	def _on_attachment_download_error(self, error_msg: str) -> None:
		"""Handle a URL download error.

		Args:
			error_msg: Human-readable error description.
		"""
		self.view.show_error(error_msg)
