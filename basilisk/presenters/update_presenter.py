"""Presenters for the update check and download dialogs.

Extracts threading and state-machine logic from UpdateDialog and
DownloadUpdateDialog into wx-free presenter classes.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
	from basilisk.updater import BaseUpdater

log = logging.getLogger(__name__)


class UpdatePresenter:
	"""Manages the update-check flow for UpdateDialog.

	Handles updater creation, background check thread, and routing of
	events from the view back to business logic.

	Attributes:
		view: Object implementing the IUpdateView interface.
		updater: The BaseUpdater instance (created lazily if None).
	"""

	def __init__(self, view, updater: Optional[BaseUpdater] = None) -> None:
		"""Initialise the presenter.

		Args:
			view: The UpdateDialog view instance.
			updater: Optional pre-existing updater (used for update
				notifications where the check was already done).
		"""
		self.view = view
		self.updater = updater
		self._check_thread: Optional[threading.Thread] = None

	def start(self) -> None:
		"""Start the update process.

		If an updater with results is already available, immediately shows
		the update-available state.  Otherwise creates a fresh updater,
		validates that updates are enabled, and launches a background
		check thread.
		"""
		if self.updater is not None:
			self.view.show_update_available(
				self.updater.current_version,
				self.updater.latest_version,
				bool(self.updater.release_notes),
			)
			return

		from basilisk.config import conf
		from basilisk.updater import get_updater_from_channel

		self.updater = get_updater_from_channel(conf())

		if not self.updater.is_update_enable:
			log.error("Updates are disabled for source application")
			self.view.show_error(
				# Translators: Shown when updates are disabled for source builds
				_("Update are disabled for source application")
			)
			self.view.close()
			return

		self.view.show_checking_state(self.updater.current_version)
		self._check_thread = threading.Thread(
			target=self._do_check, daemon=True
		)
		self._check_thread.start()

	def _do_check(self) -> None:
		"""Worker thread: check for updates and notify the view via CallAfter."""
		import wx

		log.debug("Checking for updates")
		try:
			update_available = self.updater.is_update_available()
			if update_available:
				wx.CallAfter(
					self.view.show_update_available,
					self.updater.current_version,
					self.updater.latest_version,
					bool(self.updater.release_notes),
				)
			else:
				wx.CallAfter(self.view.show_no_updates)
		except Exception as e:
			log.error("Error checking for updates: %s", e, exc_info=True)
			wx.CallAfter(self.view.show_error, str(e))
			wx.CallAfter(self.view.close)

	def on_update_clicked(self) -> None:
		"""Handle the 'Update now' button — delegate download to the view."""
		self.view.start_download(self.updater)
		self.view.close()

	def on_release_notes_clicked(self) -> None:
		"""Handle the 'Release notes' button."""
		self.view.open_release_notes()

	def on_close(self) -> None:
		"""Handle the close/cancel button."""
		self.view.close()


class DownloadPresenter:
	"""Manages the update-download flow for DownloadUpdateDialog.

	Starts the download in a background thread and routes progress/
	completion events back to the view via wx.CallAfter.

	Attributes:
		view: Object implementing the IDownloadView interface.
		updater: The BaseUpdater instance to download with.
	"""

	def __init__(self, view, updater: BaseUpdater) -> None:
		"""Initialise the presenter.

		Args:
			view: The DownloadUpdateDialog view instance.
			updater: The updater that handles the actual download.
		"""
		self.view = view
		self.updater = updater
		self._download_thread: Optional[threading.Thread] = None
		self._stop_download = False

	def start(self) -> None:
		"""Start the download, or show the finished state if already done."""
		if getattr(self.updater, "downloaded_file", None):
			self.view.show_download_finished(bool(self.updater.release_notes))
			return

		self._download_thread = threading.Thread(
			target=self._do_download, daemon=True
		)
		self._download_thread.start()

	def _do_download(self) -> None:
		"""Worker thread: download the update and notify the view."""
		import wx

		log.info("Starting download update")
		try:
			download_finished = self.updater.download(
				self._on_progress, self._stop_download
			)
			if download_finished:
				wx.CallAfter(
					self.view.show_download_finished,
					bool(self.updater.release_notes),
				)
		except Exception as e:
			log.error("Error downloading update: %s", e, exc_info=True)
			wx.CallAfter(self.view.show_error, str(e))

	def _on_progress(self, downloaded_length: int, total_length: int) -> None:
		"""Download progress callback invoked by the updater.

		Args:
			downloaded_length: Number of bytes downloaded so far.
			total_length: Total number of bytes to download.
		"""
		import wx

		if total_length <= 0:
			return
		pct = int(downloaded_length / total_length * 100)
		log.debug(
			"Download progress: %d%% - %d / %d",
			pct,
			downloaded_length,
			total_length,
		)
		wx.CallAfter(self.view.update_download_progress, pct)

	def on_update_clicked(self) -> None:
		"""Run the installer and close the application."""
		log.info("Starting update basiliskLLM")
		self.updater.update()
		self.view.close()
		import wx

		wx.GetApp().GetTopWindow().Close()

	def on_cancel(self) -> None:
		"""Cancel the in-progress download and close the dialog."""
		self._stop_download = True
		self.view.close()

	def on_release_notes_clicked(self) -> None:
		"""Handle the 'Release notes' button."""
		self.view.open_release_notes()
