"""Main application frame for BasiliskLLM.

This is the *view* layer: it creates menus, widgets, and handles pure-UI
events. All business logic is delegated to the MainFramePresenter.
"""

import logging
import os
import signal
import sys
from types import FrameType
from typing import Callable, Optional

import wx
from more_itertools import locate

if sys.platform == "win32":
	import win32con
import basilisk.config as config
from basilisk import global_vars
from basilisk.consts import APP_NAME, APP_SOURCE_URL, HotkeyAction
from basilisk.conversation import ImageFile
from basilisk.logger import get_log_file_path
from basilisk.presenters.main_frame_presenter import MainFramePresenter
from basilisk.presenters.update_presenter import (
	DownloadPresenter,
	UpdatePresenter,
)
from basilisk.screen_capture_thread import CaptureMode
from basilisk.updater import BaseUpdater

from .conversation_tab import ConversationTab
from .taskbar_icon import TaskBarIcon
from .update_dialog import DownloadUpdateDialog, UpdateDialog

log = logging.getLogger(__name__)


class MainFrame(wx.Frame):
	"""Main application frame for BasiliskLLM.

	This is the *view* layer: it creates the UI, handles pure-UI events,
	and delegates orchestration to the MainFramePresenter.

	Attributes:
		conf: The application configuration.
		presenter: The MainFramePresenter instance.
	"""

	def __init__(self, *args, **kwargs):
		"""Initialize the main application frame.

		Args:
			args: Variable length argument list passed to wx.Frame.
			kwargs: Keyword arguments with special handling for:
				conf: The basilisk configuration to use.
				open_file: Path to a conversation file to open on startup.
		"""
		self.conf: config.BasiliskConfig = kwargs.pop("conf", config.conf())
		open_file = kwargs.pop("open_file", None)
		super(MainFrame, self).__init__(*args, **kwargs)
		log.debug("Initializing main frame")

		self.presenter = MainFramePresenter(self)

		self.init_ui()
		self.init_accelerators()
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.register_hot_key()
			self.Bind(wx.EVT_HOTKEY, self.on_hotkey)
		if open_file:
			self.presenter.open_conversation(open_file)
		elif not self.presenter.try_reopen_last_conversation():
			self.presenter.on_new_default_conversation()

	def init_ui(self):
		"""Initialize the user interface for the main application frame."""

		def update_item_label_suffix(item: wx.MenuItem, suffix: str = "..."):
			if not item.GetItemLabel().endswith(suffix):
				item.SetItemLabel(item.GetItemLabel() + suffix)

		menu_bar = wx.MenuBar()

		conversation_menu = wx.Menu()

		new_conversation_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to create a new conversation
			_("New conversation") + "\tCtrl+N",
		)
		self.Bind(
			wx.EVT_MENU, self.on_new_default_conversation, new_conversation_item
		)
		new_private_conversation_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to create a new private conversation
			_("New private conversation") + "\tCtrl+Shift+N",
		)
		self.Bind(
			wx.EVT_MENU,
			self.on_new_private_conversation,
			new_private_conversation_item,
		)
		self.new_conversation_profile_item: wx.MenuItem = conversation_menu.AppendSubMenu(
			self.build_profile_menu(self.on_new_conversation),
			# Translators: A label for a menu item to create a new conversation from a profile
			_("New conversation from profile"),
		)
		open_conversation_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to open a conversation
			_("Open conversation") + "...\tCtrl+O",
		)
		self.Bind(
			wx.EVT_MENU, self.on_open_conversation, open_conversation_item
		)
		history_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to browse conversation history
			_("Conversation &history") + "...\tCtrl+H",
		)
		self.Bind(wx.EVT_MENU, self.on_conversation_history, history_item)
		conversation_menu.AppendSubMenu(
			self.build_name_conversation_menu(),
			# Translators: A label for a menu item to name a conversation
			_("Name conversation"),
		)
		save_conversation_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to save a conversation
			_("Save conversation") + "\tCtrl+S",
		)
		self.Bind(
			wx.EVT_MENU, self.on_save_conversation, save_conversation_item
		)
		save_as_conversation_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to save a conversation as a new file
			_("Save conversation as") + "...\tCtrl+Shift+S",
		)
		self.Bind(
			wx.EVT_MENU, self.on_save_as_conversation, save_as_conversation_item
		)
		close_conversation_item = conversation_menu.Append(
			wx.ID_ANY, _("Close conversation") + "\tCtrl+W"
		)
		self.Bind(
			wx.EVT_MENU, self.on_close_conversation, close_conversation_item
		)
		conversation_menu.AppendSeparator()
		attach_files_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to attach files to a conversation
			_("Attach f&iles") + "...\tCtrl+I",
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_add_attachments(e, False),
			attach_files_item,
		)
		add_image_url = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to add an image from a URL
			_("Add image from &URL") + "...\tCtrl+U",
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_add_attachments(e, True),
			add_image_url,
		)
		transcribe_audio_microphone_item = conversation_menu.Append(
			wx.ID_ANY, _("Transcribe audio from microphone") + "...\tCtrl+R"
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_transcribe_audio(e, True),
			transcribe_audio_microphone_item,
		)
		transcribe_audio_file_item = conversation_menu.Append(
			wx.ID_ANY, _("Transcribe audio file") + "...\tCtrl+Shift+R"
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_transcribe_audio(e, False),
			transcribe_audio_file_item,
		)
		conversation_menu.AppendSeparator()
		quit_item = conversation_menu.Append(wx.ID_EXIT)
		self.Bind(wx.EVT_MENU, self.on_quit, quit_item)
		self.signal_received = False
		signal.signal(signal.SIGINT, self.on_ctrl_c)
		self.timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self.on_timer)
		self.timer.Start(100)

		tool_menu = wx.Menu()
		manage_accounts_item = tool_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to manage accounts
			_("Manage &accounts") + "...\tCtrl+Shift+A",
		)
		self.Bind(wx.EVT_MENU, self.on_manage_accounts, manage_accounts_item)
		tool_menu.Append(self.build_manage_profile_item())
		preferences_item = tool_menu.Append(wx.ID_PREFERENCES)
		self.Bind(wx.EVT_MENU, self.on_preferences, preferences_item)
		update_item_label_suffix(preferences_item, "...\tCtrl+,")
		tool_menu.AppendSeparator()
		install_nvda_addon = tool_menu.Append(
			wx.ID_ANY, _("Install NVDA addon")
		)
		self.Bind(wx.EVT_MENU, self.on_install_nvda_addon, install_nvda_addon)

		help_menu = wx.Menu()
		about_item = help_menu.Append(wx.ID_ABOUT)
		self.Bind(wx.EVT_MENU, self.on_about, about_item)
		update_item_label_suffix(about_item, "...\tShift+F1")
		check_updates_item = help_menu.Append(
			wx.ID_ANY, _("Check updates") + "\tCtrl+Shift+U"
		)
		self.Bind(wx.EVT_MENU, self.on_manual_update_check, check_updates_item)
		github_repo_item = help_menu.Append(
			wx.ID_ANY, _("&GitHub repository") + "\tCtrl+Shift+G"
		)
		self.Bind(wx.EVT_MENU, self.on_github_repo, github_repo_item)
		roko_basilisk_item = help_menu.Append(
			wx.ID_ANY, _("Roko's Basilisk") + "\tCtrl+Shift+K"
		)
		self.Bind(wx.EVT_MENU, self.on_roko_basilisk, roko_basilisk_item)
		view_log_item = help_menu.Append(
			wx.ID_ANY, _("View &log") + "\tCtrl+Shift+F1"
		)
		self.Bind(wx.EVT_MENU, self.on_view_log, view_log_item)

		menu_bar.Append(conversation_menu, _("&Conversation"))
		menu_bar.Append(tool_menu, _("Too&ls"))
		menu_bar.Append(help_menu, _("&Help"))
		self.SetMenuBar(menu_bar)
		sizer = wx.BoxSizer(wx.VERTICAL)
		self.panel = wx.Panel(self)
		minimize_taskbar = wx.Button(
			self.panel, label=_("Minimize to tray") + " (Ctrl+Alt+Shift+B)"
		)
		minimize_taskbar.Bind(wx.EVT_BUTTON, self.on_minimize)
		sizer.Add(minimize_taskbar, flag=wx.EXPAND)

		self.notebook = wx.Notebook(self.panel)
		sizer.Add(self.notebook, proportion=1, flag=wx.EXPAND)
		self.panel.SetSizer(sizer)
		self.tabs_panels = []

		self.CreateStatusBar()
		self.SetStatusText(_("Ready"))
		self.Layout()
		self.Maximize(True)

	def init_accelerators(self):
		"""Initialize keyboard accelerators for tab switching."""
		self.Bind(wx.EVT_CLOSE, self.on_close)
		self.notebook.Bind(wx.EVT_CONTEXT_MENU, self.on_notebook_context_menu)
		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		accelerators = []
		for i in range(1, 10):
			id_ref = wx.NewIdRef()
			accelerators.append((wx.ACCEL_CTRL, ord(str(i)), id_ref))
			self.Bind(wx.EVT_MENU, self.make_on_goto_tab(i), id=id_ref)
		self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

	# -- Hotkeys --

	def register_hot_key(self):
		"""Register global hotkeys for the main application frame."""
		self.RegisterHotKey(
			HotkeyAction.TOGGLE_VISIBILITY.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord("B"),
		)
		self.RegisterHotKey(
			HotkeyAction.CAPTURE_FULL.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord("F"),
		)
		self.RegisterHotKey(
			HotkeyAction.CAPTURE_WINDOW.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord("W"),
		)

	def on_hotkey(self, event):
		"""Handle global hotkey events.

		Args:
			event: The hotkey event.
		"""
		match HotkeyAction(event.GetId()):
			case HotkeyAction.TOGGLE_VISIBILITY:
				self.toggle_visibility(None)
			case HotkeyAction.CAPTURE_WINDOW:
				self.presenter.screen_capture(CaptureMode.WINDOW)
			case HotkeyAction.CAPTURE_FULL:
				self.presenter.screen_capture(CaptureMode.FULL)
			case _:
				log.error("Unknown hotkey action: %s", event.GetId())

	# -- Window visibility --

	def toggle_visibility(self, event):
		"""Toggle the visibility of the main application frame.

		Args:
			event: The triggering event. Can be None.
		"""
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.on_restore(None)

	def on_minimize(self, event: wx.Event | None):
		"""Minimize to the system tray.

		Args:
			event: The triggering event. Can be None.
		"""
		if not self.IsShown():
			log.debug("Already minimized")
			return
		log.debug("Minimized to tray")
		self.Hide()

	def on_restore(self, event: wx.Event | None):
		"""Restore from the system tray.

		Args:
			event: The triggering event. Can be None.
		"""
		if self.IsShown():
			log.debug("Already restored")
			return
		log.debug("Restored from tray")
		self.Show(True)
		self.Raise()

	def on_close(self, event: wx.Event | None):
		"""Handle the close event.

		Args:
			event: The close event. Can be None.
		"""
		if self.conf.general.quit_on_close:
			self.on_quit(event)
		else:
			self.on_minimize(event)

	def on_quit(self, event: wx.Event | None):
		"""Gracefully close the application.

		Args:
			event: The triggering event. Can be None.
		"""
		log.info("Closing application")
		global_vars.app_should_exit = True
		self.presenter.flush_and_save_on_quit()
		if sys.platform == "win32":
			self.UnregisterHotKey(HotkeyAction.TOGGLE_VISIBILITY.value)
			self.UnregisterHotKey(HotkeyAction.CAPTURE_WINDOW.value)
			self.UnregisterHotKey(HotkeyAction.CAPTURE_FULL.value)
			self.tray_icon.RemoveIcon()
			self.tray_icon.Destroy()
		self.Destroy()
		wx.GetApp().ExitMainLoop()

	# -- Tab navigation --

	def on_tab_changed(self, event: wx.Event):
		"""Handle tab change events.

		Args:
			event: The tab change event.
		"""
		tab_index = event.GetSelection()
		if tab_index < len(self.tabs_panels):
			self.refresh_tab_title(True)

	def make_on_goto_tab(
		self, tab_index: int
	) -> Callable[[wx.Event | None], None]:
		"""Create a handler for switching to a specific tab.

		Args:
			tab_index: The 1-based tab index.

		Returns:
			An event handler function.
		"""

		def on_goto_tab(event: wx.Event | None):
			if tab_index <= len(self.tabs_panels):
				self.notebook.SetSelection(tab_index - 1)

		return on_goto_tab

	@property
	def current_tab(self) -> ConversationTab:
		"""Get the currently selected conversation tab."""
		return self.tabs_panels[self.notebook.GetSelection()]

	def add_conversation_tab(self, new_tab: ConversationTab):
		"""Add a new conversation tab to the notebook.

		Args:
			new_tab: The conversation tab to add.
		"""
		self.tabs_panels.append(new_tab)
		self.notebook.AddPage(self.tabs_panels[-1], new_tab.title, select=True)
		self.refresh_frame_title()

	# -- Delegating event handlers (to presenter) --

	def on_new_default_conversation(self, event: wx.Event | None):
		"""Create a new default conversation tab.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.on_new_default_conversation()

	def on_new_private_conversation(self, event: wx.Event | None):
		"""Create a new private conversation tab.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.on_new_private_conversation()

	def on_new_conversation(self, event: wx.Event):
		"""Create a new conversation with the selected profile.

		Args:
			event: The menu event with profile selection.
		"""
		profile = self.get_selected_profile_from_menu(event)
		if not profile:
			return
		log.info("Creating a new conversation with profile: %s", profile.name)
		self.presenter.new_conversation(profile)

	def on_open_conversation(self, event: wx.Event | None):
		"""Open a conversation file via file dialog.

		Args:
			event: The triggering event. Can be None.
		"""
		file_dialog = wx.FileDialog(
			self,
			# Translators: A title for the open conversation dialog
			message=_("Open conversation"),
			wildcard=_("Basilisk conversation files") + "(*.bskc)|*.bskc",
			style=wx.FD_OPEN,
		)
		if file_dialog.ShowModal() == wx.ID_OK:
			self.presenter.open_conversation(file_dialog.GetPath())
		file_dialog.Destroy()

	def on_conversation_history(self, event: wx.Event | None):
		"""Open conversation history dialog and load selected conversation.

		Args:
			event: The triggering event. Can be None.
		"""
		from .conversation_history_dialog import ConversationHistoryDialog

		dlg = ConversationHistoryDialog(self)
		if dlg.ShowModal() == wx.ID_OK and dlg.selected_conv_id is not None:
			self.presenter.open_from_db(dlg.selected_conv_id)
		dlg.Destroy()

	def on_save_conversation(self, event: wx.Event | None):
		"""Save the current conversation.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.save_current_conversation()

	def on_save_as_conversation(self, event: wx.Event | None) -> Optional[str]:
		"""Save the current conversation to a user-specified path.

		Args:
			event: The triggering event. Can be None.

		Returns:
			The file path if saved successfully, or None.
		"""
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return None
		file_dialog = wx.FileDialog(
			self,
			# Translators: A title for the save conversation dialog
			message=_("Save conversation"),
			wildcard=_("Basilisk conversation files") + "(*.bskc)|*.bskc",
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		)
		file_path = None
		if file_dialog.ShowModal() == wx.ID_OK:
			file_path = file_dialog.GetPath()
			if self.presenter.save_conversation_as(file_path):
				file_dialog.Destroy()
				return file_path
			file_path = None
		file_dialog.Destroy()
		return file_path

	def on_close_conversation(self, event: wx.Event | None):
		"""Close the current conversation tab.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.close_conversation()

	def on_name_conversation(self, event: wx.Event | None, auto: bool = False):
		"""Name the current conversation.

		Args:
			event: The triggering event. Can be None.
			auto: If True, auto-generate the title.
		"""
		self.presenter.name_conversation(auto)

	def on_manage_accounts(self, event: wx.Event | None):
		"""Open the account management dialog.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.manage_accounts()

	def on_preferences(self, event: wx.Event | None):
		"""Open the preferences dialog.

		Args:
			event: The triggering event. Can be None.
		"""
		self.presenter.manage_preferences()

	def on_manage_conversation_profiles(self, event: wx.Event | None):
		"""Open the conversation profile management dialog.

		Args:
			event: The triggering event. Can be None.
		"""
		menu_update = self.presenter.manage_conversation_profiles()
		if menu_update:
			self._rebuild_profile_menu()

	def on_apply_conversation_profile(self, event: wx.Event):
		"""Apply the selected conversation profile to the current tab.

		Args:
			event: The menu event with profile selection.
		"""
		profile = self.get_selected_profile_from_menu(event)
		if not profile:
			return
		self.presenter.apply_conversation_profile(profile)

	def on_toggle_privacy(self, event: wx.Event):
		"""Toggle the private flag on the current conversation tab.

		Args:
			event: The triggering event.
		"""
		self.presenter.toggle_privacy()

	def on_install_nvda_addon(self, event):
		"""Install the NVDA addon.

		Args:
			event: The triggering event.
		"""
		self.presenter.install_nvda_addon()

	# -- Screen capture delegation --

	def screen_capture(
		self,
		capture_mode: CaptureMode,
		screen_coordinates: Optional[tuple[int, int, int, int]] = None,
		name: str = "",
	):
		"""Capture a screenshot. Delegates to presenter.

		Args:
			capture_mode: The type of screen capture.
			screen_coordinates: Coordinates for partial capture.
			name: Custom name for the captured image.
		"""
		self.presenter.screen_capture(capture_mode, screen_coordinates, name)

	def post_screen_capture(self, image_file: ImageFile | str):
		"""Handle a completed screen capture. Delegates to presenter.

		Args:
			image_file: The captured image file or path.
		"""
		self.presenter.post_screen_capture(image_file)

	# -- Thin delegation to current tab --

	def on_add_attachments(
		self, event: wx.Event | None, from_url: bool = False
	):
		"""Add an attachment to the current conversation tab.

		Args:
			event: The triggering event. Can be None.
			from_url: If True, add from URL. Otherwise from file.
		"""
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if from_url:
			current_tab.prompt_panel.add_attachment_url_dlg(event)
		else:
			current_tab.prompt_panel.add_attachments_dlg()

	def on_transcribe_audio(
		self, event: wx.Event | None, from_microphone: bool = False
	):
		"""Transcribe audio from a file or microphone.

		Args:
			event: The triggering event. Can be None.
			from_microphone: If True, use microphone. Otherwise use file.
		"""
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if from_microphone:
			current_tab.toggle_recording(event)
		else:
			current_tab.on_transcribe_audio_file()

	# -- UI updates --

	def refresh_tab_title(self, include_frame: bool = False):
		"""Refresh the title of the current conversation tab.

		Args:
			include_frame: If True, also refresh the frame title.
		"""
		current_tab = self.current_tab
		if not current_tab:
			return
		title = current_tab.conversation.title or current_tab.title
		self.notebook.SetPageText(self.notebook.GetSelection(), title)
		if include_frame:
			self.refresh_frame_title()

	def refresh_frame_title(self):
		"""Refresh the main frame title based on the current tab."""
		current_tab = self.current_tab
		if not current_tab:
			return
		tab_title = current_tab.conversation.title or current_tab.title
		if current_tab.private:
			# Translators: Label appended to window title when conversation is private
			private_label = _("private")
			tab_title = f"{tab_title} ({private_label})"
		self.SetTitle(f"{tab_title} - {APP_NAME}")

	def refresh_tabs(self):
		"""Refresh all conversation tabs after config changes."""
		for tab in self.tabs_panels:
			tab.on_config_change()

	# -- Menu building (pure UI) --

	def get_selected_profile_from_menu(
		self, event: wx.Event
	) -> config.ConversationProfile | None:
		"""Get the selected profile from a menu event.

		Args:
			event: The menu event.

		Returns:
			The selected profile, or None if not found.
		"""
		selected_menu_item: wx.MenuItem = event.GetEventObject().FindItemById(
			event.GetId()
		)
		profile_name = selected_menu_item.GetItemLabelText()
		profile = config.conversation_profiles().get_profile(name=profile_name)
		if not profile:
			wx.MessageBox(
				# Translators: An error message when a conversation profile is not found
				_("Profile '%s' not found") % profile_name,
				# Translators: An error message title
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return None
		return profile

	def build_manage_profile_item(self) -> wx.MenuItem:
		"""Build the manage conversation profile menu item.

		Returns:
			The menu item.
		"""
		manage_profile_item = wx.MenuItem(
			id=wx.ID_ANY,
			# Translators: A label for a menu item to manage conversation profiles
			text=_("Manage conversation &profiles") + "...\tCtrl+Shift+P",
		)
		self.Bind(
			wx.EVT_MENU,
			self.on_manage_conversation_profiles,
			manage_profile_item,
		)
		return manage_profile_item

	def build_profile_menu(self, event_handler) -> wx.Menu:
		"""Build the conversation profile menu.

		Args:
			event_handler: The event handler for profile selection.

		Returns:
			The profile menu.
		"""
		profile_menu = wx.Menu()
		for profile in config.conversation_profiles():
			profile_item = profile_menu.Append(wx.ID_ANY, profile.name)
			self.Bind(wx.EVT_MENU, event_handler, profile_item)
		profile_menu.AppendSeparator()
		profile_menu.Append(self.build_manage_profile_item())
		return profile_menu

	def build_name_conversation_menu(self) -> wx.Menu:
		"""Build the name conversation menu.

		Returns:
			The name conversation menu.
		"""
		name_conversation_menu = wx.Menu()
		manual_item = name_conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to name a conversation
			_("Manual name conversation") + "...\tF2",
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_name_conversation(e, False),
			manual_item,
		)
		auto_item = name_conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to automatically name a conversation
			_("&Auto name conversation") + "...\tShift+F2",
		)
		self.Bind(
			wx.EVT_MENU, lambda e: self.on_name_conversation(e, True), auto_item
		)
		return name_conversation_menu

	def _rebuild_profile_menu(self):
		"""Rebuild the profile submenu after profile changes."""
		menu: wx.Menu = self.new_conversation_profile_item.GetMenu()
		item_index = next(
			locate(
				menu.GetMenuItems(),
				lambda x: (
					x.GetId() == self.new_conversation_profile_item.GetId()
				),
			)
		)
		menu.Remove(self.new_conversation_profile_item.GetId())
		self.new_conversation_profile_item.GetSubMenu().Destroy()
		self.new_conversation_profile_item.SetSubMenu(
			self.build_profile_menu(self.on_new_conversation)
		)
		menu.Insert(item_index, self.new_conversation_profile_item)

	def on_notebook_context_menu(self, event: wx.Event | None):
		"""Handle the notebook context menu event.

		Args:
			event: The context menu event. Can be None.
		"""
		menu = wx.Menu()
		menu.AppendSubMenu(
			self.build_profile_menu(self.on_apply_conversation_profile),
			# Translators: A label for a menu item to apply a conversation profile to the current conversation
			text=_("Apply conversation profile"),
		)
		menu.AppendSubMenu(
			self.build_name_conversation_menu(),
			# Translators: A label for a menu item to name a conversation
			_("Name conversation"),
		)
		privacy_item = menu.AppendCheckItem(
			wx.ID_ANY,
			# Translators: A label for a menu item to mark conversation as private (not saved to database)
			_("&Private conversation"),
		)
		privacy_item.Check(self.current_tab.private)
		self.Bind(wx.EVT_MENU, self.on_toggle_privacy, privacy_item)
		close_conversation_item = menu.Append(
			wx.ID_CLOSE,
			# Translators: A label for a menu item to close a conversation
			item=_("Close conversation") + " (Ctrl+W)",
		)
		self.Bind(
			wx.EVT_MENU, self.on_close_conversation, close_conversation_item
		)
		self.PopupMenu(menu)
		menu.Destroy()

	# -- Simple actions (pure UI) --

	def on_github_repo(self, event: wx.Event | None):
		"""Open the GitHub repository in the default browser.

		Args:
			event: The triggering event. Can be None.
		"""
		wx.LaunchDefaultBrowser(APP_SOURCE_URL)

	def on_roko_basilisk(self, event: wx.Event | None):
		"""Open the Wikipedia page for Roko's Basilisk.

		Args:
			event: The triggering event. Can be None.
		"""
		wx.LaunchDefaultBrowser(
			"https://en.wikipedia.org/wiki/Roko%27s_basilisk"
		)

	def on_about(self, event: wx.Event | None):
		"""Display the about dialog.

		Args:
			event: The triggering event. Can be None.
		"""
		from .about_dialog import display_about_dialog

		display_about_dialog(self)

	def on_manual_update_check(self, event: wx.Event | None):
		"""Manually check for updates.

		Args:
			event: The triggering event. Can be None.
		"""
		log.debug("Checking for updates")
		dialog = UpdateDialog(parent=self, title=_("Check updates"))
		presenter = UpdatePresenter(view=dialog)
		dialog.presenter = presenter
		presenter.start()
		dialog.Show()

	def on_view_log(self, event: wx.Event | None):
		"""Open the application log file.

		Args:
			event: The triggering event. Can be None.
		"""
		try:
			os.startfile(get_log_file_path())
		except Exception as e:
			log.error("Failed to open log file: %s", e)
			wx.MessageBox(
				_("Failed to open log file"), _("Error"), wx.OK | wx.ICON_ERROR
			)

	# -- SIGINT handling --

	def on_ctrl_c(self, signum: int, frame: FrameType):
		"""Handle SIGINT signal.

		Args:
			signum: The signal number.
			frame: The current stack frame.
		"""
		self.signal_received = True

	def on_timer(self, event: wx.Event | None):
		"""Handle timer events to check for pending signals.

		Args:
			event: The timer event. Can be None.
		"""
		if self.signal_received:
			log.debug("Received SIGINT")
			wx.CallAfter(self.on_quit, None)

	# -- Update notifications --

	def show_update_notification(self, updater: BaseUpdater):
		"""Show a notification dialog for a new update.

		Args:
			updater: The updater instance.
		"""
		log.info("Showing update notification")

		def show_dialog():
			update_dialog = UpdateDialog(
				parent=self, title=_("New version available")
			)
			presenter = UpdatePresenter(view=update_dialog, updater=updater)
			update_dialog.presenter = presenter
			presenter.start()
			update_dialog.ShowModal()
			log.debug("Update dialog shown: %s", update_dialog.IsShown())

		wx.CallAfter(show_dialog)

	def show_update_download(self, updater: BaseUpdater):
		"""Show a download dialog for a new update.

		Args:
			updater: The updater instance.
		"""
		log.info("Showing update download dialog")

		def show_dialog():
			download_dialog = DownloadUpdateDialog(
				parent=self, title=_("Downloading update")
			)
			download_dialog.update_label.SetLabel(
				_("Update basiliskLLM version: %s") % updater.latest_version
			)
			pres = DownloadPresenter(view=download_dialog, updater=updater)
			download_dialog.presenter = pres
			pres.start()
			download_dialog.ShowModal()
			log.debug("Download dialog shown: %s", download_dialog.IsShown())

		wx.CallAfter(show_dialog)
