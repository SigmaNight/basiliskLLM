import datetime
import logging
import os
import signal
import sys
import tempfile
import wx

if sys.platform == 'win32':
	import win32con
from basilisk.consts import (
	APP_NAME,
	APP_SOURCE_URL,
	HOTKEY_TOGGLE_VISIBILITY,
	HOTKEY_CAPTURE_FULL,
	HOTKEY_CAPTURE_WINDOW,
)
from .conversationtab import ConversationTab
from .taskbaricon import TaskBarIcon
from basilisk.imagefile import ImageFile
from basilisk.screencapturethread import ScreenCaptureThread, CaptureMode
import basilisk.config as config

log = logging.getLogger(__name__)


class MainFrame(wx.Frame):
	def __init__(self, *args, **kwargs):
		self.conf: config.BasiliskConfig = kwargs.pop("conf")
		self.tmp_files = []
		super(MainFrame, self).__init__(*args, **kwargs)
		log.debug("Initializing main frame")
		self.init_ui()
		self.ID_NEW_CONVERSATION = wx.NewIdRef()
		self.ID_CLOSE_CONVERSATION = wx.NewIdRef()
		self.init_accelerators()
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.Bind(wx.EVT_ICONIZE, self.on_minimize)
			self.register_hot_key()
			self.Bind(wx.EVT_HOTKEY, self.on_hotkey)
		self.on_new_conversation(None)

	def init_ui(self):
		def update_item_label_ellipsis(item):
			"""
			Update the label of the given item to include ellipsis at the end if not already present.

			:param item: The item whose label is to be updated.
			"""
			if not item.GetItemLabel().endswith("..."):
				item.SetItemLabel(item.GetItemLabel() + "...")

		menu_bar = wx.MenuBar()

		conversation_menu = wx.Menu()
		new_conversation_item = conversation_menu.Append(
			wx.ID_ANY, _("New conversation")
		)
		self.Bind(wx.EVT_MENU, self.on_new_conversation, new_conversation_item)
		close_conversation_item = conversation_menu.Append(
			wx.ID_ANY, _("Close conversation")
		)
		self.Bind(
			wx.EVT_MENU, self.on_close_conversation, close_conversation_item
		)
		conversation_menu.AppendSeparator()
		add_image_files_item = conversation_menu.Append(
			wx.ID_ANY, _("Add image files...")
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_add_image_files(e, False),
			add_image_files_item,
		)
		add_image_url = conversation_menu.Append(
			wx.ID_ANY, _("Add image URL...")
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_add_image_files(e, True),
			add_image_url,
		)
		conversation_menu.AppendSeparator()
		manage_accounts_item = conversation_menu.Append(
			wx.ID_ANY, _("Manage &accounts")
		)
		self.Bind(wx.EVT_MENU, self.on_manage_accounts, manage_accounts_item)
		update_item_label_ellipsis(manage_accounts_item)
		preferences_item = conversation_menu.Append(wx.ID_PREFERENCES)
		self.Bind(wx.EVT_MENU, self.on_preferences, preferences_item)
		update_item_label_ellipsis(preferences_item)
		quit_item = conversation_menu.Append(wx.ID_EXIT)
		self.Bind(wx.EVT_MENU, self.on_quit, quit_item)
		self.signal_received = False
		signal.signal(signal.SIGINT, self.on_ctrl_c)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.on_timer)
		self.timer.Start(100)

		help_menu = wx.Menu()
		about_item = help_menu.Append(wx.ID_ABOUT)
		self.Bind(wx.EVT_MENU, self.on_about, about_item)
		update_item_label_ellipsis(about_item)
		check_updates_item = help_menu.Append(wx.ID_ANY, _("Check updates"))
		self.Bind(wx.EVT_MENU, self.on_check_updates, check_updates_item)
		check_updates_item.Enable(False)
		github_repo_item = help_menu.Append(wx.ID_ANY, _("&GitHub repository"))
		self.Bind(wx.EVT_MENU, self.on_github_repo, github_repo_item)
		roko_basilisk_item = help_menu.Append(wx.ID_ANY, _("Roko's Basilisk"))
		self.Bind(wx.EVT_MENU, self.on_roko_basilisk, roko_basilisk_item)

		menu_bar.Append(conversation_menu, _("&Conversation"))
		menu_bar.Append(help_menu, _("&Help"))
		self.SetMenuBar(menu_bar)

		sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel = wx.Panel(self)
		actions_button = wx.Button(self.panel, label=_("Actions"))
		sizer.Add(actions_button, flag=wx.EXPAND)

		self.notebook = wx.Notebook(self.panel)
		sizer.Add(self.notebook, proportion=1, flag=wx.EXPAND)
		self.panel.SetSizer(sizer)
		self.tabs_panels = []

		self.CreateStatusBar()
		self.SetStatusText(_("Ready"))

		self.SetSize((800, 600))
		self.Layout()
		self.Maximize(True)

	def init_accelerators(self):
		self.Bind(wx.EVT_CLOSE, self.on_close)
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
			(wx.ACCEL_CTRL, ord('W'), self.ID_CLOSE_CONVERSATION),
		]

		for i in range(1, 10):
			id_ref = wx.NewIdRef()
			accelerators.append((wx.ACCEL_CTRL, ord(str(i)), id_ref))
			self.Bind(wx.EVT_MENU, self.make_on_goto_tab(i), id=id_ref)

		self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

	def register_hot_key(self):
		self.RegisterHotKey(
			HOTKEY_TOGGLE_VISIBILITY,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('B'),
		)
		self.RegisterHotKey(
			HOTKEY_CAPTURE_FULL,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('F'),
		)
		self.RegisterHotKey(
			HOTKEY_CAPTURE_WINDOW,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('W'),
		)

	def on_hotkey(self, event):
		hotkey_id = event.GetId()
		if hotkey_id == HOTKEY_TOGGLE_VISIBILITY:
			self.toggle_visibility(None)
		elif hotkey_id == HOTKEY_CAPTURE_WINDOW:
			self.screen_capture(CaptureMode.WINDOW)
		elif hotkey_id == HOTKEY_CAPTURE_FULL:
			self.screen_capture(CaptureMode.FULL)

	def toggle_visibility(self, event):
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.Show()
			self.Restore()
			self.Layout()

	def capture_partial_screen(
		self, screen_coordinates: tuple[int, int, int, int]
	):
		log.debug(f"Capturing partial screen: {screen_coordinates}")
		now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		fd, path = tempfile.mkstemp(
			prefix=f"basilisk_{now_str}_", suffix=".png"
		)
		os.close(fd)
		self.tmp_files.append(path)
		log.debug(f"Temporary file: {path}")
		thread = ScreenCaptureThread(
			self,
			path=path,
			capture_mode=CaptureMode.PARTIAL,
			screen_coordinates=screen_coordinates,
		)
		thread.start()

	def screen_capture(self, capture_mode: CaptureMode):
		log.debug("Capturing screen")
		now_str = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
		fd, path = tempfile.mkstemp(
			prefix=f"basilisk_{now_str}_", suffix=".png"
		)
		os.close(fd)
		self.tmp_files.append(path)
		log.debug(f"Temporary file: {path}")
		thread = ScreenCaptureThread(self, path, capture_mode)
		thread.start()

	def post_screen_capture(self, imagefile: ImageFile | str):
		log.debug("Screen capture received")
		self.current_tab.add_images([imagefile])
		if not self.IsShown():
			self.Show()
			self.Restore()
			self.Layout()
		self.Raise()

	def on_minimize(self, event):
		log.debug("Minimized to tray")
		self.Hide()

	def on_close(self, event):
		log.info("Closing application")
		for tmp_file in self.tmp_files:
			log.debug(f"Removing temporary file: {tmp_file}")
			os.remove(tmp_file)
		self.tray_icon.RemoveIcon()
		self.tray_icon.Destroy()
		self.Destroy()

	def on_tab_changed(self, event):
		tab_index = event.GetSelection()
		self.SetTitle(f"Conversation {tab_index + 1} - {APP_NAME}")

	def make_on_goto_tab(self, tab_index):
		def on_goto_tab(event):
			if tab_index <= len(self.tabs_panels):
				self.notebook.SetSelection(tab_index - 1)

		return on_goto_tab

	def on_new_conversation(self, event):
		log.debug("Creating a new conversation")
		self.tabs_panels.append(ConversationTab(self.notebook))
		self.notebook.AddPage(
			self.tabs_panels[-1], f"Conversation {len(self.tabs_panels)}"
		)
		self.notebook.SetSelection(len(self.tabs_panels) - 1)
		self.SetTitle(f"Conversation {len(self.tabs_panels)} - {APP_NAME}")

	def on_close_conversation(self, event):
		current_tab = self.notebook.GetSelection()
		if current_tab != wx.NOT_FOUND:
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

	@property
	def current_tab(self):
		return self.tabs_panels[self.notebook.GetSelection()]

	def on_add_image_files(self, event, from_url=False):
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if from_url:
			current_tab.add_image_url()
		else:
			current_tab.add_image_files()

	def refresh_tabs(self):
		for tab in self.tabs_panels:
			tab.on_config_change()

	def on_manage_accounts(self, event):
		from .accountdialog import AccountDialog

		account_dialog = AccountDialog(self, _("Manage accounts"))
		if account_dialog.ShowModal() == wx.ID_OK:
			self.refresh_tabs()
		account_dialog.Destroy()

	def on_preferences(self, event):
		log.debug("Opening preferences dialog")
		from .preferencesdialog import PreferencesDialog

		preferences_dialog = PreferencesDialog(self, title=_("Settings"))
		if preferences_dialog.ShowModal() == wx.ID_OK:
			self.refresh_tabs()
		preferences_dialog.Destroy()

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

	def on_ctrl_c(self, signum, frame):
		self.signal_received = True

	def on_timer(self, event):
		if self.signal_received:
			log.debug("Received SIGINT")
			wx.CallAfter(self.on_quit, None)

	def on_quit(self, event):
		if sys.platform == "win32":
			self.tray_icon.RemoveIcon()
		self.Close()
