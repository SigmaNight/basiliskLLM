"""Dialog windows for checking and downloading basiliskLLM updates.

Both dialogs act as thin view wrappers; all threading and state-machine
logic lives in UpdatePresenter / DownloadPresenter.
"""

from __future__ import annotations

from logging import getLogger
from typing import TYPE_CHECKING, Optional

import wx

from basilisk.views.view_mixins import ErrorDisplayMixin

if TYPE_CHECKING:
	from basilisk.presenters.update_presenter import (
		DownloadPresenter,
		UpdatePresenter,
	)
	from basilisk.updater import BaseUpdater

log = getLogger(__name__)


def show_release_notes(updater: BaseUpdater) -> None:
	"""Display the release notes for the latest version.

	Args:
		updater: The updater instance containing release notes.
	"""
	from .html_view_window import HtmlViewWindow

	HtmlViewWindow(
		parent=None,
		content=updater.release_notes,
		content_format="markdown",
		title=_("Release Notes for basiliskLLM %s") % updater.latest_version,
	).Show()


class DownloadUpdateDialog(wx.Dialog, ErrorDisplayMixin):
	"""Dialog for downloading a basiliskLLM update.

	Acts as the IDownloadView for DownloadPresenter.  All download logic
	is in the presenter; this class only manages widget visibility.
	"""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size: tuple[int, int] = (400, 400),
		*args,
		**kwargs,
	) -> None:
		"""Initialise the dialog.

		Args:
			parent: Parent window.
			title: Title of the dialog window.
			size: Window size. Defaults to (400, 400).
			*args: Additional positional arguments for wx.Dialog.
			**kwargs: Additional keyword arguments for wx.Dialog.
		"""
		wx.Dialog.__init__(
			self, parent, title=title, size=size, *args, **kwargs
		)
		self.presenter: Optional[DownloadPresenter] = None

		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		self.downloading_label = wx.StaticText(
			self.panel, label=_("Downloading update...")
		)
		self.sizer.Add(self.downloading_label, 0, wx.ALL | wx.CENTER, 10)

		self.downloading_gauge = wx.Gauge(self.panel, range=100)
		self.sizer.Add(self.downloading_gauge, 0, wx.ALL | wx.EXPAND, 10)

		self.update_button = wx.Button(self.panel, label=_("Update &now"))
		self.update_button.Bind(wx.EVT_BUTTON, self._on_update)
		self.sizer.Add(self.update_button, 0, wx.ALL | wx.CENTER, 10)

		self.release_notes_button = wx.Button(
			self.panel, label=_("&Release notes")
		)
		self.release_notes_button.Disable()
		self.release_notes_button.Hide()
		self.release_notes_button.Bind(wx.EVT_BUTTON, self._on_release_notes)
		self.sizer.Add(self.release_notes_button, 0, wx.ALL | wx.CENTER, 10)

		self.cancel_button = wx.Button(self.panel, id=wx.ID_CANCEL)
		self.cancel_button.Bind(wx.EVT_BUTTON, self._on_cancel)
		self.sizer.Add(self.cancel_button, 0, wx.ALL | wx.CENTER, 10)

		self.download_finished_label = wx.StaticText(
			self.panel, label=_("Update download finished")
		)
		self.sizer.Add(self.download_finished_label, 0, wx.ALL | wx.CENTER, 10)

		self.update_label = wx.StaticText(self.panel, label="")
		self.sizer.Add(self.update_label, 0, wx.ALL | wx.CENTER, 10)

		# Default: show downloading state (hidden until presenter.start)
		self.download_finished_label.Hide()
		self.update_label.Hide()
		self.update_button.Disable()
		self.update_button.Hide()

		self.panel.SetSizer(self.sizer)
		self.Layout()

	# ------------------------------------------------------------------
	# IDownloadView interface — called by DownloadPresenter
	# ------------------------------------------------------------------

	def update_download_progress(self, pct: int) -> None:
		"""Update the download progress gauge.

		Args:
			pct: Download percentage (0–100).
		"""
		self.downloading_gauge.SetValue(pct)

	def show_download_finished(self, has_notes: bool) -> None:
		"""Switch to the 'download finished' state.

		Args:
			has_notes: True if release notes are available.
		"""
		self.downloading_label.Hide()
		self.downloading_gauge.Hide()
		self.download_finished_label.Show()
		self.update_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		if has_notes:
			self.release_notes_button.Show()
			self.release_notes_button.Enable()
		self.update_button.SetFocus()
		self.Layout()

	def show_error(self, msg: str) -> None:
		"""Display a download-error message and close the dialog.

		Args:
			msg: The error description.
		"""
		dlg = wx.MessageDialog(
			self,
			# Translators: Error message shown when update download fails
			_("Error downloading update: %s") % msg,
			style=wx.OK | wx.ICON_ERROR,
		)
		try:
			dlg.ShowModal()
		finally:
			dlg.Destroy()
		self.close()

	def open_release_notes(self) -> None:
		"""Display the release notes HTML window."""
		show_release_notes(self.presenter.updater)

	def close(self) -> None:
		"""End the modal loop; the caller is responsible for Destroy."""
		self.EndModal(wx.ID_CANCEL)

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def _on_update(self, event: wx.Event) -> None:
		self.presenter.on_update_clicked()

	def _on_cancel(self, event: wx.Event) -> None:
		self.presenter.on_cancel()

	def _on_release_notes(self, event: wx.Event) -> None:
		self.presenter.on_release_notes_clicked()


class UpdateDialog(wx.Dialog, ErrorDisplayMixin):
	"""Dialog for checking and initiating basiliskLLM updates.

	Acts as the IUpdateView for UpdatePresenter.  All update-check
	threading is in the presenter; this class only manages widget
	visibility.
	"""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size: tuple[int, int] = (400, 400),
		*args,
		**kwargs,
	) -> None:
		"""Initialise the dialog.

		Args:
			parent: Parent window.
			title: Title of the dialog window.
			size: Window size. Defaults to (400, 400).
			*args: Additional positional arguments for wx.Dialog.
			**kwargs: Additional keyword arguments for wx.Dialog.
		"""
		wx.Dialog.__init__(
			self, parent, title=title, size=size, *args, **kwargs
		)
		self.presenter: Optional[UpdatePresenter] = None

		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)

		self.checking_label = wx.StaticText(
			self.panel, label=_("Checking for updates...")
		)
		self.sizer.Add(self.checking_label, 0, wx.ALL | wx.CENTER, 10)

		self.checking_gauge = wx.Gauge(self.panel, range=100)
		self.sizer.Add(self.checking_gauge, 0, wx.ALL | wx.EXPAND, 10)

		self.update_message_label = wx.StaticText(
			self.panel,
			label=_(
				"A new version of basiliskLLM is available."
				" Do you want to update?"
			),
		)
		self.sizer.Add(self.update_message_label, 0, wx.ALL | wx.CENTER, 10)

		self.current_version_label = wx.StaticText(
			self.panel, label=_("Current version: ")
		)
		self.sizer.Add(self.current_version_label, 0, wx.ALL | wx.CENTER, 10)

		self.new_version_label = wx.StaticText(
			self.panel, label=_("New version: ")
		)
		self.sizer.Add(self.new_version_label, 0, wx.ALL | wx.CENTER, 10)

		self.update_button = wx.Button(self.panel, label=_("Update &now"))
		self.update_button.Bind(wx.EVT_BUTTON, self._on_update)
		self.sizer.Add(self.update_button, 0, wx.ALL | wx.CENTER, 10)

		self.release_notes_button = wx.Button(
			self.panel, label=_("&Release notes")
		)
		self.release_notes_button.Disable()
		self.release_notes_button.Hide()
		self.release_notes_button.Bind(wx.EVT_BUTTON, self._on_release_notes)
		self.sizer.Add(self.release_notes_button, 0, wx.ALL | wx.CENTER, 10)

		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)
		self.close_button.Bind(wx.EVT_BUTTON, self._on_close)
		self.sizer.Add(self.close_button, 0, wx.ALL | wx.CENTER, 10)

		# Start hidden; presenter.start() will reveal the right widgets
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.Hide()
		self.current_version_label.Hide()
		self.new_version_label.Hide()
		self.update_button.Hide()
		self.update_button.Disable()

		self.panel.SetSizer(self.sizer)
		self.Layout()

	# ------------------------------------------------------------------
	# IUpdateView interface — called by UpdatePresenter
	# ------------------------------------------------------------------

	def show_checking_state(self, current_version: str) -> None:
		"""Switch to the 'checking' state.

		Args:
			current_version: The currently installed version string.
		"""
		self.current_version_label.SetLabel(
			_("Current version: %s") % current_version
		)
		self.checking_label.Show()
		self.checking_gauge.Show()
		self.checking_gauge.Pulse()
		self.update_message_label.Hide()
		self.current_version_label.Hide()
		self.new_version_label.Hide()
		self.update_button.Disable()
		self.update_button.Hide()
		self.sizer.Fit(self)
		self.Layout()

	def show_update_available(
		self, current: str, latest: str, has_notes: bool
	) -> None:
		"""Switch to the 'update available' state.

		Args:
			current: The currently installed version string.
			latest: The latest available version string.
			has_notes: True if release notes are available.
		"""
		log.debug("prepare dialog for update available")
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.Show()
		self.current_version_label.SetLabel(_("Current version: %s") % current)
		self.current_version_label.Show()
		log.debug("Setting new version label to: %s", latest)
		self.new_version_label.SetLabel(_("New version: %s") % latest)
		self.new_version_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		self.update_button.SetFocus()
		if has_notes:
			self.release_notes_button.Enable()
			self.release_notes_button.Show()
		self.Layout()

	def show_no_updates(self) -> None:
		"""Switch to the 'no updates available' state."""
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.SetLabel(
			# Translators: Shown when the application is up to date
			_("You are using the latest version of basiliskLLM")
		)
		self.update_message_label.Show()
		self.Layout()

	def show_error(self, msg: str) -> None:
		"""Display an update-check-error message.

		Args:
			msg: The error description.
		"""
		dlg = wx.MessageDialog(
			self,
			# Translators: Error message shown when update check fails
			_("Error checking for updates: %s") % msg,
			style=wx.OK | wx.ICON_ERROR,
		)
		try:
			dlg.ShowModal()
		finally:
			dlg.Destroy()

	def start_download(self, updater: BaseUpdater) -> None:
		"""Spawn a DownloadUpdateDialog and run it modal.

		Args:
			updater: The updater carrying the download URL / metadata.
		"""
		from basilisk.presenters.update_presenter import DownloadPresenter

		dlg = DownloadUpdateDialog(
			parent=self.Parent, title=_("Downloading update")
		)
		try:
			# Store latest_version for the update_label
			dlg.update_label.SetLabel(
				_("Update basiliskLLM version: %s") % updater.latest_version
			)
			pres = DownloadPresenter(view=dlg, updater=updater)
			dlg.presenter = pres
			pres.start()
			dlg.ShowModal()
		finally:
			dlg.Destroy()

	def open_release_notes(self) -> None:
		"""Display the release notes HTML window."""
		show_release_notes(self.presenter.updater)

	def close(self) -> None:
		"""Destroy the dialog (ends modal loop if active)."""
		self.Destroy()

	def get_parent(self) -> wx.Window:
		"""Return the parent window.

		Returns:
			The parent wx.Window.
		"""
		return self.Parent

	# ------------------------------------------------------------------
	# Event handlers
	# ------------------------------------------------------------------

	def _on_update(self, event: wx.Event) -> None:
		self.presenter.on_update_clicked()

	def _on_close(self, event: wx.Event) -> None:
		self.presenter.on_close()

	def _on_release_notes(self, event: wx.Event) -> None:
		self.presenter.on_release_notes_clicked()
