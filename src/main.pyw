import logging
import os
import sys
import threading
import winsound

if sys.platform == 'win32':
	import win32con
import wx
import wx.adv
import config
from consts import APP_NAME, APP_SOURCE_URL
from gui.conversationtab import ConversationTab
from gui.taskbaricon import TaskBarIcon
from localization import init_translation
from logger import setup_logging, logging_uncaught_exceptions
from providerengine import BaseEngine

sys.path.append(os.path.join(os.path.dirname(__file__), ""))

log = logging.getLogger(__name__)


class MainApp(wx.App):

	def OnInit(self) -> bool:
		self.conf = config.initialize_config()
		setup_logging(self.conf.general.log_level.name)
		log.debug(f"setting received -> {self.conf}")
		self.locale = init_translation(self.conf.general.language)
		log.info("translation initialized")
		self.frame = MainFrame(None, title=APP_NAME, conf=self.conf)
		self.SetTopWindow(self.frame)
		self.frame.Show(True)
		log.info("Application started")
		return True

	def OnExit(self):
		log.info("Application exited")
		return 0


class MainFrame(wx.Frame):

	def __init__(self, *args, **kwargs):
		self.conf: config.BasiliskConfig = kwargs.pop("conf")
		super(MainFrame, self).__init__(*args, **kwargs)
		log.debug("Initializing main frame")
		self.init_ui()
		self.ID_NEW_CONVERSATION = wx.NewIdRef()
		self.ID_CLOSE_CONVERSATION = wx.NewIdRef()
		self.init_accelerators()
		self.Bind(wx.EVT_CLOSE, self.on_close)
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.Bind(wx.EVT_ICONIZE, self.on_minimize)
			self.register_hot_key()
			self.Bind(wx.EVT_HOTKEY, self.toggle_visibility)

	def register_hot_key(self):
		self.RegisterHotKey(
			1, win32con.MOD_CONTROL | win32con.MOD_ALT, ord('B')
		)

	def toggle_visibility(self, event):
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.Show()
			self.Restore()

	def on_minimize(self, event):
		log.debug("Minimized to tray")
		self.Hide()

	def on_close(self, event):
		log.info("Closing application")
		self.tray_icon.RemoveIcon()
		self.tray_icon.Destroy()
		self.Destroy()

	def init_ui(self):
		menubar = wx.MenuBar()
		fileMenu = wx.Menu()
		new_conversation = fileMenu.Append(wx.ID_ANY, _("New conversation"))
		self.Bind(wx.EVT_MENU, self.on_new_conversation, new_conversation)
		close_conversation = fileMenu.Append(wx.ID_ANY, _("Close conversation"))
		self.Bind(wx.EVT_MENU, self.on_close_conversation, close_conversation)
		fileMenu.AppendSeparator()
		add_image_files = fileMenu.Append(wx.ID_ANY, _('Add image files'))
		fileMenu.AppendSeparator()
		settings_menu = fileMenu.Append(wx.ID_PREFERENCES)
		self.Bind(wx.EVT_MENU, self.on_settings, settings_menu)
		quit_menu = fileMenu.Append(wx.ID_EXIT)
		self.Bind(wx.EVT_MENU, self.on_quit, quit_menu)

		helpMenu = wx.Menu()

		about_menu = helpMenu.Append(wx.ID_ABOUT)
		self.Bind(wx.EVT_MENU, self.on_about, about_menu)

		check_updates = helpMenu.Append(wx.ID_ANY, _("Check updates"))
		self.Bind(wx.EVT_MENU, self.on_check_updates, check_updates)

		github_repo = helpMenu.Append(wx.ID_ANY, _("&GitHub repository"))
		self.Bind(wx.EVT_MENU, self.on_github_repo, github_repo)

		roko_basilisk = helpMenu.Append(wx.ID_ANY, _("Roko's Basilisk"))
		self.Bind(wx.EVT_MENU, self.on_roko_basilisk, roko_basilisk)

		menubar.Append(fileMenu, _("&Conversation"))
		menubar.Append(helpMenu, _("&Help"))
		self.SetMenuBar(menubar)

		self.panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		self.notebook = wx.Notebook(self.panel)
		self.tabs_panels = []
		self.on_new_conversation(None)
		sizer.Add(self.notebook, proportion=1, flag=wx.EXPAND)

		self.CreateStatusBar()
		self.SetStatusText(_("Ready"))

		self.SetSize((800, 600))


	def init_accelerators(self):
		self.Bind(
			wx.EVT_MENU, self.on_new_conversation, id=self.ID_NEW_CONVERSATION
		)
		self.Bind(
			wx.EVT_MENU,
			self.on_close_conversation,
			id=self.ID_CLOSE_CONVERSATION,
		)

		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		accelerators = [
			(wx.ACCEL_CTRL, ord('N'), self.ID_NEW_CONVERSATION),
			(wx.ACCEL_CTRL, ord('W'), self.ID_CLOSE_CONVERSATION)
		]

		for i in range(1, 10):
			id_ref = wx.NewIdRef()
			accelerators.append((wx.ACCEL_CTRL, ord(str(i)), id_ref))
			self.Bind(wx.EVT_MENU, self.make_on_goto_tab(i), id=id_ref)

		self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

	def on_tab_changed(self, event):
		tab_index = event.GetSelection()
		self.SetTitle(f"Conversation {tab_index + 1} - {APP_NAME}")

	def make_on_goto_tab(self, tab_index):
		def on_goto_tab(event):
			if tab_index <= len(self.tabs_panels):
				self.notebook.SetSelection(tab_index - 1)
			else:
				winsound.PlaySound(
					"SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC
				)

		return on_goto_tab

	def on_new_conversation(self, event):
		log.debug("Creating a new conversation")
		self.tabs_panels.append(
			ConversationTab(self.notebook)
		)
		self.notebook.AddPage(
			self.tabs_panels[-1], f"Conversation {len(self.tabs_panels)}"
		)
		self.notebook.SetSelection(len(self.tabs_panels) - 1)
		self.SetTitle(f"Conversation {len(self.tabs_panels)} - {APP_NAME}")
		self.tabs_panels[-1].on_account_change(None)
		self.tabs_panels[-1].on_model_change(None)

	def on_close_conversation(self, event):
		current_tab = self.notebook.GetSelection()
		if current_tab != wx.NOT_FOUND:
			# delete task and conversation from the dictionary
			self.tabs_tasks.pop(current_tab)
			self.tabs_id_conversations.pop(self.tabs_panels[current_tab].GetId())
			self.notebook.DeletePage(current_tab)
			self.tabs_panels.pop(current_tab)
			current_tab_count = self.notebook.GetPageCount()
			if current_tab_count == 0:
				self.on_new_conversation(None)
			else:
				for tab_index in range(current_tab_count):
					self.notebook.SetPageText(
						tab_index, f"Conversation {tab_index + 1}"
					)
				self.notebook.SetSelection(current_tab_count - 1)
				self.SetTitle(f"Conversation {current_tab_count} - {APP_NAME}")

	def on_settings(self, event):
		log.debug("Opening settings dialog")
		from configdialog import ConfigDialog

		config_dialog = ConfigDialog(self, title=_("Settings"))
		if config_dialog.ShowModal() == wx.ID_OK:
			self.update_ui()
			log.debug("Settings saved")
		config_dialog.Destroy()

	def on_github_repo(self, event):
		wx.LaunchDefaultBrowser(APP_SOURCE_URL)

	def on_roko_basilisk(self, event):
		wx.LaunchDefaultBrowser(
			"https://en.wikipedia.org/wiki/Roko%27s_basilisk"
		)

	def on_about(self, event):
		from gui.aboutdialog import display_about_dialog
		display_about_dialog(self)

	def on_check_updates(self, event):
		log.debug("Checking for updates")

	def on_quit(self, event):
		if sys.platform == "win32":
			self.tray_icon.RemoveIcon()
		self.Close()


if __name__ == '__main__':
	sys.excepthook = logging_uncaught_exceptions
	app = MainApp()
	app.MainLoop()
