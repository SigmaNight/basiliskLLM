import logging
import sys
import wx

if sys.platform == 'win32':
	import win32con
from basilisk.consts import APP_NAME, APP_SOURCE_URL
from .conversationtab import ConversationTab
from .taskbaricon import TaskBarIcon
import basilisk.config as config

log = logging.getLogger(__name__)


class MainFrame(wx.Frame):
	def __init__(self, *args, **kwargs):
		self.conf: config.BasiliskConfig = kwargs.pop("conf")
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
			self.Bind(wx.EVT_HOTKEY, self.toggle_visibility)
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
			wx.ID_ANY, _("Add image files")
		)
		add_image_files_item.Enable(False)
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
			1, win32con.MOD_CONTROL | win32con.MOD_ALT, ord('B')
		)

	def toggle_visibility(self, event):
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.Show()
			self.Restore()
			self.Layout()

	def on_minimize(self, event):
		log.debug("Minimized to tray")
		self.Hide()

	def on_close(self, event):
		log.info("Closing application")
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

	def on_quit(self, event):
		if sys.platform == "win32":
			self.tray_icon.RemoveIcon()
		self.Close()
