"""This module Provides dialog windows for checking and downloading basiliskLLM updates."""

import threading
from logging import getLogger

import wx

from basilisk.config import conf
from basilisk.updater import BaseUpdater, get_updater_from_channel

log = getLogger(__name__)


def show_release_notes(updater: BaseUpdater):
	"""Display the release notes for the latest version of basiliskLLM.

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


class DownloadUpdateDialog(wx.Dialog):
	"""Dialog window for downloading basiliskLLM updates.

	This dialog shows download progress and provides options to start the update
	process or view release notes.
	"""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		updater: BaseUpdater,
		size=(400, 400),
		*args,
		**kwargs,
	):
		"""Initialize the dialog.

		Args:
			parent: Parent window.
			title: Title of the dialog window.
			updater: Instance of the updater to handle downloads.
			size: Window size. Defaults to (400, 400).
			*args: Additional positional arguments for wx.Dialog.
			**kwargs: Additional keyword arguments for wx.Dialog.
		"""
		wx.Dialog.__init__(
			self, parent, title=title, size=size, *args, **kwargs
		)
		self.updater = updater
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.downloading_label = wx.StaticText(
			self.panel, label=_("Downloading update...")
		)
		self.sizer.Add(self.downloading_label, 0, wx.ALL | wx.CENTER, 10)
		self.downloading_gauge = wx.Gauge(self.panel, range=100)
		self.sizer.Add(self.downloading_gauge, 0, wx.ALL | wx.EXPAND, 10)
		self.update_button = wx.Button(self.panel, label=_("Update &now"))
		self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
		self.sizer.Add(self.update_button, 0, wx.ALL | wx.CENTER, 10)
		self.release_notes_button = wx.Button(
			self.panel, label=_("&Release notes")
		)
		self.release_notes_button.Disable()
		self.release_notes_button.Hide()
		self.release_notes_button.Bind(
			wx.EVT_BUTTON, lambda _: show_release_notes(self.updater)
		)
		self.sizer.Add(self.release_notes_button, 0, wx.ALL | wx.CENTER, 10)
		self.cancel_button = wx.Button(self.panel, id=wx.ID_CANCEL)
		self.cancel_button.Bind(wx.EVT_BUTTON, self.on_cancel)
		self.sizer.Add(self.cancel_button, 0, wx.ALL | wx.CENTER, 10)
		self.download_finished_label = wx.StaticText(
			self.panel, label=_("Update download finished")
		)
		self.sizer.Add(self.download_finished_label, 0, wx.ALL | wx.CENTER, 10)
		self.update_label = wx.StaticText(
			self.panel,
			label=_("Update basiliskLLM version: %s")
			% self.updater.latest_version,
		)
		self.sizer.Add(self.update_label, 0, wx.ALL | wx.CENTER, 10)
		self.panel.SetSizer(self.sizer)
		if getattr(self.updater, "downloaded_file", None):
			self.on_download_finished()
		else:
			self.download_finished_label.Hide()
			self.update_label.Hide()
			self.update_button.Disable()
			self.update_button.Hide()
			self.stop_download = False
			self.download_thread = threading.Thread(
				target=self.on_download_update
			)
			self.download_thread.start()
			self.Layout()

	def on_download_update(self):
		"""Handle the download process in a separate thread.

		Downloads the update using the updater instance and updates the UI
		when finished or if an error occurs.
		"""
		try:
			log.info("starting download update")
			download_finished = self.updater.download(
				self.on_download_progress, self.stop_download
			)
			if download_finished:
				wx.CallAfter(self.on_download_finished)
		except Exception as e:
			log.error("Error downloading update: %s", e, exc_info=True)
			wx.CallAfter(self.on_download_error, e)

	def on_download_finished(self):
		"""Update the UI when the download is complete."""
		self.downloading_label.Hide()
		self.downloading_gauge.Hide()
		self.download_finished_label.Show()
		self.update_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		if self.updater.release_notes:
			self.release_notes_button.Show()
			self.release_notes_button.Enable()
		self.update_button.SetFocus()
		self.Layout()

	def on_update(self, event: wx.Event | None):
		"""Handle the update button click.

		Args:
			event: The button click event.
		"""
		log.info("starting update basiliskLLM")
		self.updater.update()
		self.Destroy()
		wx.GetApp().GetTopWindow().Close()

	def on_download_progress(self, downloaded_length: int, total_length: int):
		"""Update the progress bar during download.

		Args:
			downloaded_length: Number of bytes downloaded.
			total_length: Total number of bytes to download.
		"""
		download_percent = int(downloaded_length / total_length * 100)
		log.debug(
			"Download progress: %d%% - %d / %d",
			download_percent,
			downloaded_length,
			total_length,
		)
		wx.CallAfter(self.downloading_gauge.SetValue, download_percent)

	def on_cancel(self, event: wx.Event | None):
		"""Handle the cancel button click.

		Args:
			event: The button click event.
		"""
		if hasattr(self, "download_thread") and self.download_thread.is_alive():
			self.stop_download = True
		self.Destroy()

	def on_download_error(self, error: Exception):
		"""Display an error message when download fails.

		Args:
			error: The error that occurred during download.
		"""
		wx.MessageDialog(
			self,
			_("Error downloading update: %s") % error,
			style=wx.OK | wx.ICON_ERROR,
		).ShowModal()
		self.Destroy()


class UpdateDialog(wx.Dialog):
	"""Dialog window for checking and initiating basiliskLLM updates.

	This dialog checks for available updates and allows users to start
	the download process or view release notes.
	"""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size=(400, 400),
		updater: BaseUpdater = None,
		*args,
		**kwargs,
	):
		"""Initialize the dialog.

		Args:
			parent: Parent window.
			title: Title of the dialog window.
			size: Window size. Defaults to (400, 400).
			updater: Updater instance. Defaults to None.
			*args: Additional positional arguments for wx.Dialog.
			**kwargs: Additional keyword arguments for wx.Dialog.
		"""
		wx.Dialog.__init__(
			self, parent, title=title, size=size, *args, **kwargs
		)
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
				"A new version of basiliskLLM is available. Do you want to update?"
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
		self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
		self.sizer.Add(self.update_button, 0, wx.ALL | wx.CENTER, 10)
		self.release_notes_button = wx.Button(
			self.panel, label=_("&Release notes")
		)
		self.release_notes_button.Disable()
		self.release_notes_button.Hide()
		self.release_notes_button.Bind(
			wx.EVT_BUTTON, lambda _: show_release_notes(self.updater)
		)
		self.sizer.Add(self.release_notes_button, 0, wx.ALL | wx.CENTER, 10)
		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)
		self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
		self.sizer.Add(self.close_button, 0, wx.ALL | wx.CENTER, 10)
		self.panel.SetSizer(self.sizer)
		if updater is not None:
			self.init_with_updater(updater)
		else:
			self.init_without_updater()

	def init_with_updater(self, updater: BaseUpdater):
		"""Initialize the dialog with an existing updater instance.

		Update the UI to show the current and latest version numbers.

		Args:
			updater: The updater instance to use.
		"""
		log.debug("Initializing update dialog with updater")
		self.updater = updater
		self.current_version_label.SetLabel(
			_("Current version: %s") % self.updater.current_version
		)
		self.on_update_available()

	def init_without_updater(self):
		"""Initialize the dialog by creating a new updater instance.

		Check for updates in a separate thread and update the UI accordingly.
		"""
		self.updater = get_updater_from_channel(conf())
		if not self.updater.is_update_enable:
			log.error("Update are disabled for source application")
			wx.MessageDialog(
				self,
				_("Update are disabled for source application"),
				_("Update disabled"),
				wx.OK | wx.ICON_INFORMATION,
			).ShowModal()
			self.Destroy()
			return
		self.current_version_label.SetLabel(
			_("Current version: %s") % self.updater.current_version
		)
		self.update_button.Disable()
		self.update_button.Hide()
		self.checking_gauge.Pulse()
		self.update_message_label.Hide()
		self.current_version_label.Hide()
		self.new_version_label.Hide()
		self.update_button.Disable()
		self.update_button.Hide()
		self.sizer.Fit(self)
		self.Layout()
		log.debug("Starting check for updates thread")
		self.check_thread = threading.Thread(target=self.on_check_for_updates)
		self.check_thread.start()

	def on_update_available(self):
		"""Update the UI to show that an update is available."""
		log.debug("prepare dialog for update available")
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.Show()
		self.current_version_label.Show()
		log.debug(
			"Setting new version label to: %s", self.updater.latest_version
		)
		self.new_version_label.SetLabel(
			_("New version: %s") % self.updater.latest_version
		)
		self.new_version_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		self.update_button.SetFocus()
		if self.updater.release_notes:
			self.release_notes_button.Enable()
			self.release_notes_button.Show()
		self.Layout()

	def on_no_updates(self):
		"""Update the UI to show that no updates are available."""
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.SetLabel(
			_("You are using the latest version of basiliskLLM")
		)
		self.update_message_label.Show()
		self.Layout()

	def on_check_for_updates(self):
		"""Check for updates in a separate thread."""
		log.debug("Checking for updates")
		try:
			update_available = self.updater.is_update_available()
			if update_available:
				wx.CallAfter(self.on_update_available)
			else:
				wx.CallAfter(self.on_no_updates)
		except Exception as e:
			log.error("Error checking for updates: %s", e, exc_info=True)
			wx.CallAfter(self.on_check_update_error, e)
			self.Destroy()

	def on_update(self, event: wx.Event | None):
		"""Handle the update button click.

		Args:
			event: The button click event.
		"""
		download_dialog = DownloadUpdateDialog(
			parent=self.Parent,
			title=_("Downloading update"),
			updater=self.updater,
		)
		log.info("Showing download dialog")
		download_dialog.ShowModal()
		self.Destroy()

	def on_close(self, event: wx.Event | None):
		"""Handle the close button click.

		Args:
			event: The button click event.
		"""
		self.Destroy()

	def on_check_update_error(self, error: Exception):
		"""Display an error message when update check fails.

		Args:
			error: The error that occurred during the update check.
		"""
		wx.MessageDialog(
			self,
			_("Error checking for updates: %s") % error,
			style=wx.OK | wx.ICON_ERROR,
		).ShowModal()
		self.Destroy()
