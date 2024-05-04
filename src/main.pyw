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

from typing import Iterable
from uuid import UUID
from logger import setup_logging
from localization import init_translation
from consts import APP_NAME, APP_VERSION, APP_AUTHORS, APP_SOURCE_URL
from provideraimodel import ProviderAIModel
from providerengine import BaseEngine
from conversation import Conversation, Message, MessageBlock, MessageRoleEnum

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


class TaskBarIcon(wx.adv.TaskBarIcon):
	def __init__(self, frame):
		super(TaskBarIcon, self).__init__()
		log.debug("Initializing taskbar icon")
		self.frame = frame
		# TODO: Set a proper icon
		transparent_icon = wx.Icon()
		transparent_icon.CopyFromBitmap(wx.Bitmap(16, 16))
		self.SetIcon(transparent_icon, APP_NAME)

		self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
		self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

	def on_left_down(self, event):
		self.frame.Show()

	def on_right_down(self, event):
		menu = wx.Menu()
		label = _("Show") if not self.frame.IsShown() else _("Hide")
		show_menu = menu.Append(wx.ID_ANY, label)
		self.Bind(wx.EVT_MENU, self.frame.toggle_visibility, show_menu)
		about_menu = menu.Append(wx.ID_ABOUT, _("About"))
		self.Bind(wx.EVT_MENU, self.frame.on_about, about_menu)
		quit_menu = menu.Append(wx.ID_EXIT, _("Quit"))
		self.Bind(wx.EVT_MENU, self.frame.on_quit, quit_menu)
		self.PopupMenu(menu)
		menu.Destroy()


class MainFrame(wx.Frame):
	def __init__(self, *args, **kwargs):
		self.conf: config.BasiliskConfig = kwargs.pop("conf")
		super(MainFrame, self).__init__(*args, **kwargs)
		log.debug("Initializing main frame")
		self.accounts_engines: dict[UUID, BaseEngine] = {}
		self.tabs_id_conversations: dict[int, Conversation] = {}
		self.init_ui()
		self.update_ui()
		self.ID_NEW_CONVERSATION = wx.NewIdRef()
		self.ID_CLOSE_CONVERSATION = wx.NewIdRef()
		self.ID_SUBMIT = wx.NewIdRef()
		self.init_accelerators()
		self.Bind(wx.EVT_CLOSE, self.on_close)
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.Bind(wx.EVT_ICONIZE, self.on_minimize)
			self.register_hotKey()
			self.Bind(wx.EVT_HOTKEY, self.toggle_visibility)

	def register_hotKey(self):
		self.RegisterHotKey(
			1, win32con.MOD_CONTROL | win32con.MOD_ALT, ord('B')
		)

	def toggle_visibility(self, event):
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.Show()
			self.Restore()

	def update_ui(self):
		controls = (
			self.temperature_spinner,
			self.top_p_spinner,
			self.debug_mode,
			self.stream_mode,
		)
		for control in controls:
			control.Show(config.conf.general.advanced_mode)

	def on_key_down(self, event):
		if (
			event.GetModifiers() == wx.ACCEL_CTRL
			and event.GetKeyCode() == wx.WXK_RETURN
		):
			self.on_submit(event)
		event.Skip()

	@property
	def current_engine(self) -> BaseEngine:
		account_index = self.account_combo.GetSelection()
		account = self.conf.accounts[account_index]
		return self.accounts_engines[account.id]

	@property
	def current_model(self) -> ProviderAIModel:
		model_index = self.model_list.GetFirstSelected()
		return self.current_engine.models[model_index]

	@property
	def current_conversation(self) -> Conversation:
		tab_index = self.notebook.GetSelection()
		return self.tabs_id_conversations[self.tabs[tab_index].GetId()]

	def get_display_models(self) -> list[tuple[str, str, str]]:
		return [m.display_model for m in self.current_engine.models]

	def on_submit(self, event):
		new_block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=self.prompt.GetValue()
			),
			model=self.current_model,
			top_p = self.top_p_spinner.GetValue() / 100,
			temperature=self.temperature_spinner.GetValue(),
			max_tokens=self.max_tokens_spin_ctrl.GetValue(),
			stream=self.stream_mode.GetValue()
		)
		completion_kw = {
			"system_message": self.system_prompt_txt.GetValue(),
			"conversation": self.current_conversation,
			"new_block": new_block,
			"debug": self.debug_mode.GetValue(),
			"engine": self.current_engine,
			"stream": new_block.stream
		}
		log.debug(f"Completion params: {completion_kw}")
		self.messages.SetFocus()
		thread = threading.Thread(target=self._handle_completion, kwargs=completion_kw)
		thread.start()

	def _handle_completion(self, engine: BaseEngine, **kwargs):
		response = engine.completion(**kwargs)
		new_block = kwargs["new_block"]
		if kwargs.get("stream", False):
			new_block.response = Message(
				role=MessageRoleEnum.ASSISTANT,
				content=""
			)
			self.current_conversation.messages.append(new_block)
			self.update_messages()
			self.prompt.Clear()
			self.messages.SetFocus()
			for chunk in self.current_engine.completion_response_with_stream(response):
				new_block.response.content += chunk
				self.messages.AppendText(chunk)
			wx.CallAfter(self._post_completion_with_stream, new_block)
		else:
			new_block = engine.completion_response_without_stream(
				response=response, **kwargs
			)
			wx.CallAfter(self._post_completion_without_stream, new_block)

	def _post_completion_with_stream(self, new_block):
		pass

	def _post_completion_without_stream(self, new_block):
		self.current_conversation.messages.append(new_block)
		self.update_messages()
		self.prompt.Clear()

	def update_messages(self):
		self.messages.Clear()
		for block in self.current_conversation.messages:
			self.messages.AppendText(
				f"{block.request.role.value}: {block.request.content}\n"
			)
			if block.response:
				self.messages.AppendText(
					f"{block.response.role.value}: {block.response.content}\n"
				)

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

		self.notebook = wx.Notebook(self)
		self.tabs = []
		self.on_new_conversation(None)

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
		self.Bind(wx.EVT_MENU, self.on_submit, id=self.ID_SUBMIT)
		self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		accelerators = [
			(wx.ACCEL_CTRL, ord('N'), self.ID_NEW_CONVERSATION),
			(wx.ACCEL_CTRL, ord('W'), self.ID_CLOSE_CONVERSATION),
			(wx.ACCEL_CTRL, wx.WXK_RETURN, self.ID_SUBMIT),
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
			if tab_index <= len(self.tabs):
				self.notebook.SetSelection(tab_index - 1)
			else:
				winsound.PlaySound(
					"SystemExclamation", winsound.SND_ALIAS | winsound.SND_ASYNC
				)

		return on_goto_tab

	def get_display_accounts(self) -> list:
		accounts = []
		for account in self.conf.accounts:
			name = account.name
			organization = account.active_organization or _("Personal")
			provider_name = account.provider.name
			accounts.append(f"{name} ({organization}) - {provider_name}")
		return accounts

	def on_new_conversation(self, event):
		tab_panel = wx.Panel(self.notebook)
		tab_panel_id = tab_panel.GetId()
		log.debug(
			f"a new conversation is linked with Tab panel ID: {tab_panel_id}"
		)
		self.tabs_id_conversations.setdefault(tab_panel_id, Conversation())
		tab_panel.SetBackgroundColour('light gray')

		tab_sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for account in the main window
			label=_("&Account:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.account_combo = wx.ComboBox(
			tab_panel, style=wx.CB_READONLY, choices=self.get_display_accounts()
		)
		self.account_combo.Bind(wx.EVT_COMBOBOX, self.on_account_change)
		if len(self.account_combo.GetItems()) > 0:
			self.account_combo.SetSelection(0)
		tab_sizer.Add(self.account_combo, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for system prompt in the main window
			label=_("S&ystem prompt:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.system_prompt_txt = wx.TextCtrl(tab_panel, style=wx.TE_MULTILINE)
		tab_sizer.Add(self.system_prompt_txt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for user prompt in the main window
			label=_("&Messages:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(
			tab_panel, style=wx.TE_MULTILINE | wx.TE_READONLY
		)
		tab_sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for user prompt in the main window
			label=_("&Prompt:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(tab_panel, style=wx.TE_MULTILINE)
		tab_sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		label = wx.StaticText(tab_panel, label=_("M&odels:"))
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.model_list = wx.ListCtrl(tab_panel, style=wx.LC_REPORT)
		self.model_list.InsertColumn(0, _("Name"))
		self.model_list.InsertColumn(1, _("Context window"))
		self.model_list.InsertColumn(2, _("Max tokens"))
		tab_sizer.Add(self.model_list, proportion=2, flag=wx.EXPAND)
		self.on_account_change(None)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for max tokens in the main window
			label=_("Max to&kens:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.max_tokens_spin_ctrl = wx.SpinCtrl(
			tab_panel,
			value='1024',
			min=1,
			max=64000,
		)
		tab_sizer.Add(self.max_tokens_spin_ctrl, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for temperature in the main window
			label=_("&Temperature:"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.temperature_spinner = wx.SpinCtrl(
			tab_panel, value='0', min=0, max=200
		)
		tab_sizer.Add(self.temperature_spinner, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			tab_panel,
			# Translators: This is a label for top P in the main window
			label=_("Probability &Mass (top P):"),
		)
		tab_sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.top_p_spinner = wx.SpinCtrl(tab_panel, value='0', min=0, max=100)
		tab_sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)

		self.debug_mode = wx.CheckBox(
			tab_panel,
			# Translators: This is a label for debug mode in the main window
			label=_("Debu&g mode"),
		)
		tab_sizer.Add(self.debug_mode, proportion=0, flag=wx.EXPAND)

		self.stream_mode = wx.CheckBox(
			tab_panel,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)
		tab_sizer.Add(self.stream_mode, proportion=0, flag=wx.EXPAND)

		self.submit_btn = wx.Button(
			tab_panel,
			# Translators: This is a label for submit button in the main window
			label=_("Submit (Ctrl+Enter)"),
		)
		self.submit_btn.Bind(wx.EVT_BUTTON, self.on_submit)
		tab_sizer.Add(self.submit_btn, proportion=0, flag=wx.EXPAND)

		tab_panel.SetSizerAndFit(tab_sizer)
		tab_panel.Layout()

		self.tabs.append(tab_panel)
		self.notebook.AddPage(tab_panel, f"Conversation {len(self.tabs)}")
		self.notebook.SetSelection(len(self.tabs) - 1)
		self.SetTitle(f"Conversation {len(self.tabs)} - {APP_NAME}")

	def on_account_change(self, event):
		account_index = self.account_combo.GetSelection()
		account = self.conf.accounts[account_index]
		self.accounts_engines.setdefault(
			account.id, account.provider.engine_cls(account)
		)
		self.model_list.DeleteAllItems()
		for i, model in enumerate(self.get_display_models()):
			self.model_list.InsertItem(i, model[0])
			self.model_list.SetItem(i, 1, model[1])
			self.model_list.SetItem(i, 2, model[2])
		self.model_list.SetItemState(
			0,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)

	def on_close_conversation(self, event):
		current_tab = self.notebook.GetSelection()
		if current_tab != wx.NOT_FOUND:
			self.notebook.DeletePage(current_tab)
			self.tabs.pop(current_tab)
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
		wx.MessageBox(
			f"{APP_NAME} v{APP_VERSION}\n\n"
			f"Developed by: {APP_AUTHORS}\n\n"
			f"Source code: {APP_SOURCE_URL}\n\n"
			f"Licensed under the GNU GPL v2",
			_("About"),
			wx.OK | wx.ICON_INFORMATION,
		)

	def on_check_updates(self, event):
		log.debug("Checking for updates")

	def on_quit(self, event):
		if sys.platform == "win32":
			self.tray_icon.RemoveIcon()
		self.Close()


if __name__ == '__main__':
	app = MainApp()
	app.MainLoop()
