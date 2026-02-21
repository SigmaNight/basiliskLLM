"""Service layer for attachment validation and download logic.

Provides both an instance-based async download interface (with callbacks,
following the CompletionHandler pattern) and pure static helpers for
validation that do not depend on wx.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Callable

import wx
from httpx import HTTPError
from upath import UPath

from basilisk.conversation import (
	AttachmentFile,
	ImageFile,
	build_from_url,
	get_mime_type,
)
from basilisk.decorators import ensure_no_task_running

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class AttachmentService:
	"""Manages attachment downloads and provides validation helpers.

	Instance interface (async download):
		Create an ``AttachmentService`` with success/error callbacks and call
		:meth:`download_from_url`.  The download runs in a daemon thread;
		results are dispatched back to the wx main thread via
		``wx.CallAfter``.

	Static interface (synchronous validation):
		All ``@staticmethod`` methods have no wx dependency and can be called
		freely from the service or test code.
	"""

	# ------------------------------------------------------------------
	# Instance-based: async download with callbacks
	# ------------------------------------------------------------------

	def __init__(
		self,
		on_download_success: Callable[[AttachmentFile | ImageFile], None],
		on_download_error: Callable[[str], None],
	):
		"""Initialise the service with result callbacks.

		Args:
			on_download_success: Called on the main thread when a URL
				download succeeds.  Receives the resulting attachment object.
			on_download_error: Called on the main thread when a URL download
				fails.  Receives a human-readable error string.
		"""
		self.task: threading.Thread | None = None
		self._on_download_success = on_download_success
		self._on_download_error = on_download_error

	@ensure_no_task_running
	def download_from_url(self, url: str) -> None:
		"""Start an async download of *url* in a daemon thread.

		Guarded by :func:`~basilisk.decorators.ensure_no_task_running`: if a
		download is already active the call is silently ignored and an error
		message box is shown.

		Args:
			url: The URL of the file to download.
		"""
		self.task = threading.Thread(
			target=self._download_worker, args=(url,), daemon=True
		)
		self.task.start()

	def _download_worker(self, url: str) -> None:
		"""Worker that fetches *url* and dispatches results to the main thread.

		Args:
			url: The URL to fetch.
		"""
		try:
			attachment = build_from_url(url)
			wx.CallAfter(self._on_download_success, attachment)
		except HTTPError as err:
			wx.CallAfter(
				self._on_download_error,
				# Translators: Error message shown when an HTTP error occurs while downloading an attachment
				_("HTTP error %s.") % err,
			)
		except Exception as err:
			if isinstance(err, (KeyboardInterrupt, SystemExit)):
				raise
			log.error(err, exc_info=True)
			wx.CallAfter(
				self._on_download_error,
				# Translators: Error message shown when an unknown error occurs while downloading an attachment
				_("Error adding attachment from URL: %s") % err,
			)
		finally:
			self.task = None

	# ------------------------------------------------------------------
	# Static helpers: pure validation, no wx dependency
	# ------------------------------------------------------------------

	@staticmethod
	def is_format_supported(
		mime_type: str | None, supported_formats: set[str]
	) -> bool:
		"""Return True if *mime_type* is in *supported_formats*.

		Args:
			mime_type: MIME type string or None.
			supported_formats: Set of accepted MIME type strings.

		Returns:
			True if the MIME type is supported, False otherwise.
		"""
		return mime_type in supported_formats

	@staticmethod
	def build_attachment_from_path(
		path: str, supported_formats: set[str]
	) -> tuple[AttachmentFile | ImageFile | None, str | None]:
		"""Create an attachment object from a local file path.

		Args:
			path: Path to the local file.
			supported_formats: Set of accepted MIME type strings.

		Returns:
			A tuple ``(attachment, None)`` on success, or
			``(None, mime_type)`` when the file's MIME type is not in
			*supported_formats*.
		"""
		mime_type = get_mime_type(path)
		if mime_type not in supported_formats:
			return None, mime_type
		if mime_type.startswith("image/"):
			return ImageFile(location=UPath(path)), None
		return AttachmentFile(location=UPath(path)), None

	@staticmethod
	def validate_attachments(
		attachments: list[AttachmentFile | ImageFile],
		supported_formats: set[str],
	) -> list[str]:
		"""Return location strings of attachments with unsupported MIME types.

		Args:
			attachments: The list of attachments to validate.
			supported_formats: Set of accepted MIME type strings.

		Returns:
			A list of ``str(attachment.location)`` for each invalid
			attachment.  An empty list means all attachments are valid.
		"""
		return [
			str(attachment.location)
			for attachment in attachments
			if attachment.mime_type not in supported_formats
		]

	@staticmethod
	def check_model_vision_compatible(
		attachments: list[AttachmentFile | ImageFile],
		current_model: ProviderAIModel,
		engine: BaseEngine,
	) -> tuple[bool, list[str] | None]:
		"""Check whether the model supports all image attachments.

		Args:
			attachments: Current list of attachments.
			current_model: The selected AI model.
			engine: The engine providing the model list.

		Returns:
			``(True, None)`` when compatible, or ``(False, vision_model_names)``
			when the model does not support vision but image attachments are
			present.  *vision_model_names* is a list of model names/IDs that
			do support vision.
		"""
		has_images = any(
			a.mime_type is not None and a.mime_type.startswith("image/")
			for a in attachments
		)
		if not has_images:
			return True, None
		if current_model.vision:
			return True, None
		vision_model_names = [m.name or m.id for m in engine.models if m.vision]
		return False, vision_model_names

	@staticmethod
	def resize_attachments(
		attachments: list[AttachmentFile | ImageFile],
		conv_storage_path,
		max_width: int,
		max_height: int,
		quality: int,
	) -> None:
		"""Resize all image attachments in-place.

		Non-image attachments and attachments without a MIME type are skipped.
		Errors for individual attachments are logged and do not abort the loop.

		Args:
			attachments: The list of attachments to process.
			conv_storage_path: Storage path passed to :meth:`ImageFile.resize`.
			max_width: Maximum output width in pixels.
			max_height: Maximum output height in pixels.
			quality: JPEG/WebP quality (1–100).
		"""
		for attachment in attachments:
			if not attachment.mime_type or not attachment.mime_type.startswith(
				"image/"
			):
				continue
			try:
				attachment.resize(
					conv_storage_path, max_width, max_height, quality
				)
			except Exception as e:
				log.error(
					"Error resizing image attachment %s: %s",
					attachment.location,
					e,
					exc_info=True,
				)
