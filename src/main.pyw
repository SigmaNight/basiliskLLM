import os
import sys
import winsound
if sys.platform == 'win32':
	import win32con
import wx
import wx.adv
import config
config.initialize_config()
conf = config.conf
from logger import get_app_logger
from localization import _
from consts import (
	APP_NAME,
	APP_VERSION,
	APP_AUTHORS,
	APP_SOURCE_URL
)
from account import initialize_accountManager

sys.path.append(os.path.join(os.path.dirname(__file__), ""))

log = get_app_logger(__name__)

class MainApp(wx.App):

	def OnInit(self):
		log.info("Application started")
		log.debug(f"setting received -> {conf}")
		initialize_accountManager()
		self.frame = MainFrame(
			None,
			title=APP_NAME,
		)
		self.SetTopWindow(self.frame)
		self.frame.Show(True)
		return True

	def OnExit(self):
		log.info("Application exited")
		return 0


class TaskBarIcon(wx.adv.TaskBarIcon):

	def __init__(self, frame):
		super(TaskBarIcon, self).__init__()
		self.frame = frame
		# TODO: Set a proper icon
		transparent_icon = wx.Icon()
		transparent_icon.CopyFromBitmap(wx.Bitmap(16, 16))
		self.SetIcon(
			transparent_icon,
			APP_NAME
		)

		self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.OnLeftDown)
		self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.OnRightDown)

	def OnLeftDown(self, event):
		self.frame.Show()

	def OnRightDown(self, event):
		menu = wx.Menu()
		label = _("Show") if not self.frame.IsShown() else _("Hide")
		show_menu = menu.Append(wx.ID_ANY, label)
		self.Bind(wx.EVT_MENU, self.frame.toggleVisibility, show_menu)
		about_menu = menu.Append(wx.ID_ABOUT, _("About"))
		self.Bind(wx.EVT_MENU, self.frame.OnAbout, about_menu)
		quit_menu = menu.Append(wx.ID_EXIT, _("Quit"))
		self.Bind(wx.EVT_MENU, self.frame.OnQuit, quit_menu)
		self.PopupMenu(menu)
		menu.Destroy()


class MainFrame(wx.Frame):

	def __init__(self, *args, **kwargs):
		super(MainFrame, self).__init__(*args, **kwargs)
		self.InitUI()
		self.ID_NEW_CONVERSATION = wx.NewIdRef()
		self.ID_CLOSE_CONVERSATION = wx.NewIdRef()
		self.InitAccelerators()
		self.Bind(wx.EVT_CLOSE, self.onClose)
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.Bind(wx.EVT_ICONIZE, self.onMinimize)
			self.registerHotKey()
			self.Bind(wx.EVT_HOTKEY, self.toggleVisibility)

	def registerHotKey(self):
		self.RegisterHotKey(
			1,
			win32con.MOD_CONTROL | win32con.MOD_ALT,
			ord('B')
		)

	def toggleVisibility(self, event):
		if self.IsShown():
			self.onMinimize(None)
		elif not self.IsShown():
			self.Show()
			self.Restore()

	def onMinimize(self, event):
		log.debug("Minimized to tray")
		self.Hide()

	def onClose(self, event):
		log.info("Closing application")
		self.tray_icon.RemoveIcon()
		self.tray_icon.Destroy()
		self.Destroy()

	def InitUI(self):
		menubar = wx.MenuBar()
		fileMenu = wx.Menu()
		new_conversation = fileMenu.Append(wx.ID_ANY, _("New conversation"))
		self.Bind(wx.EVT_MENU, self.OnNewConversation, new_conversation)
		close_conversation = fileMenu.Append(wx.ID_ANY, _("Close conversation"))
		self.Bind(wx.EVT_MENU, self.OnCloseConversation, close_conversation)
		fileMenu.AppendSeparator()
		add_image_files = fileMenu.Append(wx.ID_ANY, _('Add image files'))
		fileMenu.AppendSeparator()
		settings_menu = fileMenu.Append(wx.ID_ANY, _("Settings..."))
		self.Bind(wx.EVT_MENU, self.OnSettings, settings_menu)
		quit_menu = fileMenu.Append(wx.ID_EXIT, _('Quit'))
		self.Bind(wx.EVT_MENU, self.OnQuit, quit_menu)

		helpMenu = wx.Menu()
		about_menu = helpMenu.Append(wx.ID_ABOUT, _("About"))
		self.Bind(wx.EVT_MENU, self.OnAbout, about_menu)
		check_updates = helpMenu.Append(wx.ID_ANY, _("Check updates"))
		github_repo = helpMenu.Append(wx.ID_ANY, _("&GitHub repository"))
		self.Bind(wx.EVT_MENU, self.OnGithubRepo, github_repo)
		roko_basilisk = helpMenu.Append(wx.ID_ANY, _("Roko's Basilisk"))
		self.Bind(wx.EVT_MENU, self.OnRokoBasilisk, roko_basilisk)

		menubar.Append(fileMenu, "&File")
		menubar.Append(helpMenu, "&Help")
		self.SetMenuBar(menubar)

		self.notebook = wx.Notebook(self)
		self.tabs = []
		self.OnNewConversation(None)

		self.CreateStatusBar()
		self.SetStatusText(_("Ready"))

		self.SetSize((800, 600))

	def InitAccelerators(self):
		self.Bind(wx.EVT_MENU, self.OnNewConversation, id=self.ID_NEW_CONVERSATION)
		self.Bind(wx.EVT_MENU, self.OnCloseConversation, id=self.ID_CLOSE_CONVERSATION)

		self.notebook	.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		accelerators = [
			(
				wx.ACCEL_CTRL,
				ord('N'),
				self.ID_NEW_CONVERSATION
			),
			(
				wx.ACCEL_CTRL,
				ord('W'),
				self.ID_CLOSE_CONVERSATION
			),
		]

		for i in range(1, 10):
			id_ref = wx.NewIdRef()
			accelerators.append(
				(
					wx.ACCEL_CTRL,
					ord(str(i)),
					id_ref
				)
			)
			self.Bind(wx.EVT_MENU, self.make_on_goto_tab(i), id=id_ref)

		self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

	def on_tab_changed(self, event):
		tab_index = event.GetSelection()
		self.SetTitle(f"Conversation {tab_index + 1} - {APP_NAME}")

	def make_on_goto_tab(self, tab_index):
		def on_goto_tab(event):
			if tab_index <= len(self.tabs):
				self.notebook.SetSelection(tab_index - 1)
			else:
				winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC)
		return on_goto_tab

	def OnNewConversation(self, event):
		tab_panel = wx.Panel(self.notebook)
		tab_panel.SetBackgroundColour('light gray')

		tab_sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(tab_panel, label=_("S&ystem prompt:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.system_prompt = wx.TextCtrl(tab_panel, style=wx.TE_MULTILINE)
		tab_sizer.Add(self.system_prompt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(tab_panel, label=_("&Messages:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(tab_panel, style=wx.TE_MULTILINE|wx.TE_READONLY)
		tab_sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(tab_panel, label=_("&Prompt:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(tab_panel, style=wx.TE_MULTILINE)
		tab_sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		label = wx.StaticText(tab_panel, label=_("M&odels:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.model_list = wx.ListCtrl(tab_panel, style=wx.LC_REPORT)
		self.model_list.InsertColumn(0, _("name"))
		self.model_list.InsertColumn(1, _("Provider"))
		self.model_list.InsertColumn(2, _("ID"))
		self.model_list.InsertColumn(3, _("Context window"))
		self.model_list.InsertColumn(4, _("Max tokens"))
		tab_sizer.Add(self.model_list, proportion=2, flag=wx.EXPAND)

		label = wx.StaticText(tab_panel, label=_("&Temperature:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.temp_spinner = wx.SpinCtrl(
			tab_panel,
			value='0',
			min=0,
			max=200,
		)
		tab_sizer.Add(self.temp_spinner, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(tab_panel, label=_("Probability &Mass (top P):"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.top_p_spinner = wx.SpinCtrl(
			tab_panel,
			value='0',
			min=0,
			max=100,
		)
		tab_sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)

		submit_btn = wx.Button(tab_panel, label=_('Submit'))
		tab_sizer.Add(submit_btn, proportion=0, flag=wx.EXPAND)

		tab_panel.SetSizer(tab_sizer)

		self.tabs.append(tab_panel)
		self.notebook.AddPage(tab_panel, f"Conversation {len(self.tabs)}")
		self.notebook.SetSelection(len(self.tabs) - 1)
		self.SetTitle(f"Conversation {len(self.tabs)} - {APP_NAME}")

	def OnCloseConversation(self, event):
		current_tab = self.notebook.GetSelection()
		if current_tab != wx.NOT_FOUND:
			self.notebook.DeletePage(current_tab)
			self.tabs.pop(current_tab)
			current_tab_count = self.notebook.GetPageCount()
			if current_tab_count == 0:
				self.OnNewConversation(None)
			else:
				for tab_index in range(current_tab_count):
					self.notebook.SetPageText(tab_index, f"Conversation {tab_index + 1}")
				self.notebook.SetSelection(current_tab_count - 1)
				self.SetTitle(f"Conversation {current_tab_count} - {APP_NAME}")

	def OnSettings(self, event):
		log.debug("Opening settings dialog")
		from configdialog import ConfigDialog
		config_dialog = ConfigDialog(
			self,
			title=_("Settings")
		)
		if config_dialog.ShowModal() == wx.ID_OK:
			log.debug("Settings saved")
		config_dialog.Destroy()

	def OnGithubRepo(self, event):
		wx.LaunchDefaultBrowser(
			APP_SOURCE_URL
		)

	def OnRokoBasilisk(self, event):
		wx.LaunchDefaultBrowser("https://en.wikipedia.org/wiki/Roko%27s_basilisk")

	def OnAbout(self, event):
		wx.MessageBox(
			f"{APP_NAME} v{APP_VERSION}\n\n"
			f"Developed by: {APP_AUTHORS}\n\n"
			f"Source code: {APP_SOURCE_URL}\n\n"
			f"Licensed under the GNU GPL v2",
			_("About"),
			wx.OK | wx.ICON_INFORMATION
		)

	def OnQuit(self, event):
		if sys.platform == "win32":
			self.tray_icon.RemoveIcon()
		self.Close()

if __name__ == '__main__':
	app = MainApp()
	app.MainLoop()
