import threading
from logging import getLogger

import wx

from basilisk.config import conf
from basilisk.updater import BaseUpdater, get_updater_from_channel

log = getLogger(__name__)


class DownloadUpdateDialog(wx.Dialog):
	def __init__(
		self,
		parent: wx.Window,
		title: str,
		updater: BaseUpdater,
		size=(400, 400),
		*args,
		**kwargs,
	):
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
		self.update_button = wx.Button(self.panel, label=_("Update now"))
		self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
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
		try:
			log.info("starting download update")
			download_finished = self.updater.download(
				self.on_download_progress, self.stop_download
			)
			if download_finished:
				wx.CallAfter(self.on_download_finished)
		except Exception as e:
			log.error(f"Error downloading update: {e}", exc_info=True)
			wx.CallAfter(self.on_download_error, e)

	def on_download_finished(self):
		self.downloading_label.Hide()
		self.downloading_gauge.Hide()
		self.download_finished_label.Show()
		self.update_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		self.update_button.SetFocus()
		self.Layout()

	def on_update(self, event):
		log.info("starting update basiliskLLM")
		self.updater.update()
		self.Destroy()
		wx.GetApp().GetTopWindow().Close()

	def on_download_progress(self, downloaded_length: int, total_length: int):
		download_percent = int(downloaded_length / total_length * 100)
		log.debug(
			f"Download progress: {download_percent}% - {downloaded_length} / {total_length}"
		)
		wx.CallAfter(self.downloading_gauge.SetValue, download_percent)

	def on_cancel(self, event):
		if hasattr(self, "download_thread") and self.download_thread.is_alive():
			self.stop_download = True
		self.Destroy()

	def on_download_error(self, error: Exception):
		wx.MessageDialog(
			self,
			_("Error downloading update: %s") % error,
			style=wx.OK | wx.ICON_ERROR,
		).ShowModal()
		self.Destroy()


class UpdateDialog(wx.Dialog):
	def __init__(
		self,
		parent: wx.Window,
		title: str,
		size=(400, 400),
		updater: BaseUpdater = None,
		*args,
		**kwargs,
	):
		log.debug("Creating update dialog")
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
		self.update_button = wx.Button(self.panel, label=_("Update now"))
		self.update_button.Bind(wx.EVT_BUTTON, self.on_update)
		self.sizer.Add(self.update_button, 0, wx.ALL | wx.CENTER, 10)
		self.close_button = wx.Button(self.panel, id=wx.ID_CLOSE)
		self.close_button.Bind(wx.EVT_BUTTON, self.on_close)
		self.sizer.Add(self.close_button, 0, wx.ALL | wx.CENTER, 10)
		self.panel.SetSizer(self.sizer)
		if updater is not None:
			self.init_with_updater(updater)
		else:
			self.init_without_updater()

	def init_with_updater(self, updater: BaseUpdater):
		log.debug("Initializing update dialog with updater")
		self.updater = updater
		self.current_version_label.SetLabel(
			_("Current version: %s") % self.updater.current_version
		)
		self.on_update_available()

	def init_without_updater(self):
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
		log.debug("prepare dialog for update available")
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.Show()
		self.current_version_label.Show()
		log.debug(f"Setting new version label to {self.updater.latest_version}")
		self.new_version_label.SetLabel(
			_("New version: %s") % self.updater.latest_version
		)
		self.new_version_label.Show()
		self.update_button.Enable()
		self.update_button.Show()
		self.update_button.SetFocus()
		self.Layout()

	def on_no_updates(self):
		self.checking_label.Hide()
		self.checking_gauge.Hide()
		self.update_message_label.SetLabel(
			_("You are using the latest version of basiliskLLM")
		)
		self.update_message_label.Show()
		self.Layout()

	def on_check_for_updates(self):
		log.debug("Checking for updates")
		try:
			update_available = self.updater.is_update_available()
			if update_available:
				wx.CallAfter(self.on_update_available)
			else:
				wx.CallAfter(self.on_no_updates)
		except Exception as e:
			log.error(f"Error checking for updates: {e}")
			wx.CallAfter(self.on_check_update_error, e)
			self.Destroy()

	def on_update(self, event):
		download_dialog = DownloadUpdateDialog(
			parent=self.Parent,
			title=_("Downloading update"),
			updater=self.updater,
		)
		log.info("Showing download dialog")
		download_dialog.ShowModal()
		self.Destroy()

	def on_close(self, event):
		self.Destroy()

	def on_check_update_error(self, error: Exception):
		wx.MessageDialog(
			self,
			_("Error checking for updates: %s") % error,
			style=wx.OK | wx.ICON_ERROR,
		).ShowModal()
		self.Destroy()
