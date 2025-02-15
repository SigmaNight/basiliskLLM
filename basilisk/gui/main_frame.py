"""Main application frame for BasiliskLLM."""

import datetime
import logging
import os
import signal
import sys
import tempfile
from types import FrameType
from typing import Callable, Optional

import wx
from more_itertools import locate

if sys.platform == 'win32':
	import win32con
import basilisk.config as config
from basilisk import global_vars
from basilisk.consts import APP_NAME, APP_SOURCE_URL, HotkeyAction
from basilisk.conversation import ImageFile
from basilisk.logger import get_log_file_path
from basilisk.screen_capture_thread import CaptureMode, ScreenCaptureThread
from basilisk.updater import BaseUpdater

from .conversation_tab import ConversationTab
from .taskbar_icon import TaskBarIcon
from .update_dialog import DownloadUpdateDialog, UpdateDialog

log = logging.getLogger(__name__)


class MainFrame(wx.Frame):
	"""Main application frame for BasiliskLLM.

	This class represents the main application window for BasiliskLLM. It contains the entire user interface, including menus, conversation tabs, and various controls for managing conversations, accounts, and settings.
	"""

	def __init__(self, *args, **kwargs):
		"""Initialize the main application frame with configuration and optional conversation file.

		Behavior:
			- Sets up the main frame configuration
			- Initializes user interface and keyboard accelerators
			- On Windows, creates a system tray icon and registers global hotkeys
			- Opens a specified conversation file or creates a new conversation

		Args:
			args: Variable length argument list passed to the parent class constructor.
			kwargs: Arbitrary keyword arguments with special handling for configuration and file opening.
				conf: The basilisk configuration objects to use. If not provided, a default configuration is used.
				open_file: Path to a conversation file to open on startup. If not provided, a new conversation is created.
		"""
		self.conf: config.BasiliskConfig = kwargs.pop("conf", config.conf())
		open_file = kwargs.pop("open_file", None)
		self.last_conversation_id = 0
		super(MainFrame, self).__init__(*args, **kwargs)
		log.debug("Initializing main frame")
		self.init_ui()

		self.init_accelerators()
		if sys.platform == "win32":
			self.tray_icon = TaskBarIcon(self)
			self.register_hot_key()
			self.Bind(wx.EVT_HOTKEY, self.on_hotkey)
		if open_file:
			self.open_conversation(open_file)
		else:
			self.on_new_default_conversation(None)

	def init_ui(self):
		"""Initialize the user interface for the main application frame.

		The method performs the following key tasks:
		- Creates a menu bar with three main menus: Conversation, Tools, and Help
		- Binds keyboard shortcuts to various menu items
		- Sets up a panel with a minimize to tray button
		- Creates a notebook for managing conversation tabs
		- Configures signal handling and a timer for application control
		- Maximizes the application window and sets an initial status message
		"""

		def update_item_label_suffix(item: wx.MenuItem, suffix: str = "..."):
			"""Update the label of the given item to include ellipsis at the end if not already present.

			Args:
				item: The item whose label is to be updated.
				suffix: The suffix to add to the label.
			"""
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
		add_image_files_item = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to add an image from a file
			_("Add image from f&ile") + "...\tCtrl+I",
		)
		self.Bind(
			wx.EVT_MENU,
			lambda e: self.on_add_image(e, False),
			add_image_files_item,
		)
		add_image_url = conversation_menu.Append(
			wx.ID_ANY,
			# Translators: A label for a menu item to add an image from a URL
			_("Add image from &URL") + "...\tCtrl+U",
		)
		self.Bind(
			wx.EVT_MENU, lambda e: self.on_add_image(e, True), add_image_url
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
		"""Initialize keyboard accelerators for the main application frame.

		Setup accelerator to change tabs using Ctrl+1 to Ctrl+9 and register event handlers for context menu and tab change events.
		"""
		self.Bind(wx.EVT_CLOSE, self.on_close)
		self.notebook.Bind(wx.EVT_CONTEXT_MENU, self.on_notebook_context_menu)
		self.notebook.Bind(wx.EVT_NOTEBOOK_PAGE_CHANGED, self.on_tab_changed)

		accelerators = []

		for i in range(1, 10):
			id_ref = wx.NewIdRef()
			accelerators.append((wx.ACCEL_CTRL, ord(str(i)), id_ref))
			self.Bind(wx.EVT_MENU, self.make_on_goto_tab(i), id=id_ref)

		self.SetAcceleratorTable(wx.AcceleratorTable(accelerators))

	def register_hot_key(self):
		"""Register global hotkeys for the main application frame.

		Registers global hotkeys for toggling visibility, capturing full screen, and capturing a window.
		"""
		self.RegisterHotKey(
			HotkeyAction.TOGGLE_VISIBILITY.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('B'),
		)
		self.RegisterHotKey(
			HotkeyAction.CAPTURE_FULL.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('F'),
		)
		self.RegisterHotKey(
			HotkeyAction.CAPTURE_WINDOW.value,
			win32con.MOD_CONTROL | win32con.MOD_ALT | win32con.MOD_SHIFT,
			ord('W'),
		)

	def on_hotkey(self, event):
		"""Handle global hotkey events for the main application frame.

		Args:
			event: The event that triggered the hotkey action.
		"""
		match HotkeyAction(event.GetId()):
			case HotkeyAction.TOGGLE_VISIBILITY:
				self.toggle_visibility(None)
			case HotkeyAction.CAPTURE_WINDOW:
				self.screen_capture(CaptureMode.WINDOW)
			case HotkeyAction.CAPTURE_FULL:
				self.screen_capture(CaptureMode.FULL)
			case _:
				log.error(f"Unknown hotkey action: {event.GetId()}")

	def toggle_visibility(self, event):
		"""Toggle the visibility of the main application frame. If the frame is shown, it is minimized to the system tray. If it is hidden, it is restored.

		Args:
			event: The event that triggered the visibility toggle. Can be None.
		"""
		if self.IsShown():
			self.on_minimize(None)
		elif not self.IsShown():
			self.on_restore(None)

	def screen_capture(
		self,
		capture_mode: CaptureMode,
		screen_coordinates: Optional[tuple[int, int, int, int]] = None,
		name: str = "",
	):
		"""Capture a screenshot of the screen or a specific region.

		Initiates a screen capture based on the specified capture mode and optional screen coordinates.
		The captured image is saved in the current conversation's attachments directory.

		Notes:
			- Creates a background thread for screen capture to prevent UI freezing
			- Saves the captured image in the current conversation's attachments folder
			- Uses a timestamp-based filename if no custom name is provided

		Args:
			capture_mode: The type of screen capture to perform (full screen, partial screen, or window capture).
			screen_coordinates: Coordinates for partial screen capture (left, top, width, height). Defaults to None.
			name: Custom name for the captured image. If not provided, a timestamp-based name is generated.
		"""
		log.debug(f"Capturing {capture_mode.value} screen")
		conv_tab = self.current_tab
		if not conv_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if capture_mode == CaptureMode.PARTIAL and not screen_coordinates:
			wx.MessageBox(
				_("No screen coordinates provided"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		now = datetime.datetime.now()
		capture_name = f"capture_{now.isoformat(timespec='seconds')}.png"
		capture_path = (
			conv_tab.conv_storage_path / f"attachments/{capture_name}"
		)
		name = name or capture_name
		log.debug(f"Capture file URL: {capture_path}")
		thread = ScreenCaptureThread(
			self,
			capture_path,
			capture_mode,
			name=name,
			screen_coordinates=screen_coordinates,
		)
		thread.start()

	def post_screen_capture(self, imagefile: ImageFile | str):
		"""Handle a screen capture event by adding the image to the current conversation tab.

		Args:
			imagefile: The image file object or path to the captured image.
		"""
		log.debug("Screen capture received")
		self.current_tab.add_images([imagefile])
		if not self.IsShown():
			self.Show()
			self.Restore()
			self.Layout()
		self.Raise()

	def on_minimize(self, event: wx.Event | None):
		"""Minimize the main application frame to the system tray.

		Args:
			event: The event that triggered the minimize action. Can be None.
		"""
		if not self.IsShown():
			log.debug("Already minimized")
			return
		log.debug("Minimized to tray")
		self.Hide()

	def on_restore(self, event: wx.Event | None):
		"""Restore the main application frame from the system tray.

		Args:
			event: The event that triggered the restore action. Can be None.
		"""
		if self.IsShown():
			log.debug("Already restored")
			return
		log.debug("Restored from tray")
		self.Show(True)
		self.Raise()

	def on_close(self, event: wx.Event | None):
		"""Handle the close event for the main application frame.

		Args:
			event: The event that triggered the close action. Can be None.
		"""
		if self.conf.general.quit_on_close:
			self.on_quit(event)
		else:
			self.on_minimize(event)

	def on_quit(self, event: wx.Event | None):
		"""Gracefully close the application, stopping all conversation tasks and cleaning up resources.

		This method performs the following actions:
		- Sets a global flag to indicate the application should exit
		- Waits for all active conversation tasks to complete
		- Unregisters global hotkeys on Windows platforms
		- Removes and destroys the system tray icon
		- Destroys the main application window
		- Exits the main event loop

		Raises:
			No explicit exceptions are raised, but underlying system calls may raise exceptions
		"""
		log.info("Closing application")
		global_vars.app_should_exit = True
		# ensure all conversation tasks are stopped
		for tab in self.tabs_panels:
			if tab.task:
				task_id = tab.task.ident
				log.debug(
					f"Waiting for conversation task {task_id} to finish..."
				)
				tab.task.join()
				log.debug("... is dead")
		if sys.platform == "win32":
			self.UnregisterHotKey(HotkeyAction.TOGGLE_VISIBILITY.value)
			self.UnregisterHotKey(HotkeyAction.CAPTURE_WINDOW.value)
			self.UnregisterHotKey(HotkeyAction.CAPTURE_FULL.value)
			self.tray_icon.RemoveIcon()
			self.tray_icon.Destroy()
		self.Destroy()
		wx.GetApp().ExitMainLoop()

	def on_tab_changed(self, event: wx.Event):
		"""Handle the tab change event for the main application frame.

		Args:
			event: The event that triggered the tab change action.
		"""
		tab_index = event.GetSelection()
		if tab_index < len(self.tabs_panels):
			self.refresh_tab_title(True)

	def make_on_goto_tab(
		self, tab_index: int
	) -> Callable[[wx.Event | None], None]:
		"""Create a function to handle tab selection based on the specified index.

		Args:
			tab_index: The index of the tab to select.

		Returns:
			A function to handle tab selection based on the specified index.
		"""

		def on_goto_tab(event: wx.Event | None):
			if tab_index <= len(self.tabs_panels):
				self.notebook.SetSelection(tab_index - 1)

		return on_goto_tab

	def on_new_default_conversation(self, event: wx.Event | None):
		"""Create a new default conversation tab with the default profile.

		Args:
			event: The event that triggered the new conversation action. Can be None.
		"""
		self.handle_no_account_configured()
		profile = config.conversation_profiles().default_profile
		if profile:
			log.info(
				f"Creating a new conversation with default profile ({profile.name})"
			)
		self.new_conversation(profile)

	def get_selected_profile_from_menu(
		self, event: wx.Event
	) -> config.ConversationProfile | None:
		"""Get the selected conversation profile from the specified event.

		Args:
			event: The event that triggered the profile selection.
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

	def on_new_conversation(self, event: wx.Event):
		"""Create a new conversation tab with the selected profile.

		Args:
			event: The event that triggered the new conversation action.
		"""
		profile = self.get_selected_profile_from_menu(event)
		if not profile:
			return
		log.info(f"Creating a new conversation with profile: {profile.name}")
		self.new_conversation(profile)

	def refresh_tab_title(self, include_frame: bool = False):
		"""Refresh the title of the current conversation tab.

		Args:
			include_frame: If True, refresh the main frame title as well. Defaults to False.
		"""
		current_tab = self.current_tab
		if not current_tab:
			return
		title = current_tab.conversation.title or current_tab.title
		self.notebook.SetPageText(self.notebook.GetSelection(), title)
		if include_frame:
			self.refresh_frame_title()

	def on_name_conversation(self, event: wx.Event | None, auto: bool = False):
		"""Open a dialog to name the current conversation, either manually or automatically.

		This method allows renaming the current conversation tab's title. If no conversation is selected,
		it displays an error message. When `auto` is True, it attempts to generate a title automatically
		using the conversation's content.

		Args:
			event: The event that triggered the method (typically a menu or button click)
			auto: If True, automatically generates a conversation title. If False, opens a manual naming dialog. Defaults to False.
		"""
		from .name_conversation_dialog import NameConversationDialog

		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		title = current_tab.conversation.title or current_tab.title
		if auto:
			title = current_tab.generate_conversation_title()
			if not title:
				return
			title = title.strip().replace('\n', ' ')
		dialog = NameConversationDialog(self, title=title, auto=auto)
		if dialog.ShowModal() != wx.ID_OK or not dialog.get_name():
			dialog.Destroy()
			return

		current_tab.conversation.title = dialog.get_name()
		self.refresh_tab_title(True)
		dialog.Destroy()

	def get_default_conv_title(self) -> str:
		"""Generate a default title for a new conversation.

		This method increments an internal conversation ID counter and returns a localized conversation title with the current ID.

		Returns:
			A localized conversation title in the format "Conversation X", where X is an incrementing number.
		"""
		self.last_conversation_id += 1
		# Translators: A default title for a conversation
		return _("Conversation %d") % self.last_conversation_id

	def new_conversation(self, profile: config.ConversationProfile | None):
		"""Create a new conversation tab with the specified profile.

		Creates a new conversation tab in the notebook with a default title and the specified profile.
		The tab is automatically added to the notebook and becomes the active tab.

		Args:
			profile: The conversation profile to use for the new tab. If None, a default profile will be used.
		"""
		new_tab = ConversationTab(
			self.notebook, title=self.get_default_conv_title(), profile=profile
		)
		self.add_conversation_tab(new_tab)

	def add_conversation_tab(self, new_tab: ConversationTab):
		"""Add a new conversation tab to the notebook and update the frame title.

		Args:
			new_tab: The conversation tab to be added to the notebook.
		"""
		self.tabs_panels.append(new_tab)
		self.notebook.AddPage(self.tabs_panels[-1], new_tab.title, select=True)
		self.refresh_frame_title()

	def on_close_conversation(self, event: wx.Event | None):
		"""Close the currently selected conversation tab and manage tab selection.

		This method removes the current tab from the notebook and the tabs_panels list. If no tabs remain,
		a new default conversation is created. Otherwise, the last tab is selected and the frame title is refreshed.

		Args:
			event: The event that triggered the tab closure. Can be None.
		"""
		current_tab_index = self.notebook.GetSelection()
		if current_tab_index == wx.NOT_FOUND:
			return
		self.notebook.DeletePage(current_tab_index)
		self.tabs_panels.pop(current_tab_index)
		current_tab_count = self.notebook.GetPageCount()
		if current_tab_count == 0:
			self.on_new_default_conversation(None)
		else:
			self.notebook.SetSelection(current_tab_count - 1)
			self.refresh_frame_title()

	@property
	def current_tab(self) -> ConversationTab:
		"""Get the currently selected conversation tab.

		Returns:
			The currently selected conversation tab.
		"""
		return self.tabs_panels[self.notebook.GetSelection()]

	def on_add_image(self, event: wx.Event | None, from_url: bool = False):
		"""Add an image to the current conversation tab.

		Args:
			event: The event that triggered the image addition. Can be None.
			from_url: If True, add an image from a URL. If False, add an image from a file. Defaults to False.
		"""
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if from_url:
			current_tab.add_image_url_dlg(event)
		else:
			current_tab.add_image_files(event)

	def on_transcribe_audio(
		self, event: wx.Event | None, from_microphone: bool = False
	):
		"""Transcribe audio from a file or microphone.

		Args:
			event: The event that triggered the audio transcription. Can be None.
			from_microphone: If True, transcribe audio from the microphone. If False, transcribe audio from a file. Defaults to False.
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

	def refresh_frame_title(self):
		"""Refresh the title of the main application frame based on the current conversation tab.

		The frame title is updated to include the title of the currently selected conversation tab.
		"""
		current_tab = self.current_tab
		if not current_tab:
			return
		tab_title = current_tab.conversation.title or current_tab.title
		self.SetTitle(f"{tab_title} - {APP_NAME}")

	def refresh_tabs(self):
		"""Refresh all conversation tabs in the notebook.

		Iterates over all conversation tabs and calls the on_config_change method to refresh the tab content.
		"""
		for tab in self.tabs_panels:
			tab.on_config_change()

	def on_manage_accounts(self, event: wx.Event | None):
		"""Open the account management dialog to manage user accounts.

		Args:
			event: The event that triggered the account management action. Can be None.
		"""
		log.debug("Opening account management dialog")
		from .account_dialog import AccountDialog

		account_dialog = AccountDialog(self, _("Manage accounts"))
		if account_dialog.ShowModal() == wx.ID_OK:
			if not config.accounts():
				self.handle_no_account_configured()
			else:
				self.refresh_tabs()
		account_dialog.Destroy()

	def on_preferences(self, event: wx.Event | None):
		"""Open the preferences dialog to manage application settings.

		Args:
			event: The event that triggered the preferences action. Can be None.
		"""
		log.debug("Opening preferences dialog")
		from .preferences_dialog import PreferencesDialog

		preferences_dialog = PreferencesDialog(self, title=_("Settings"))
		if preferences_dialog.ShowModal() == wx.ID_OK:
			self.refresh_tabs()
		preferences_dialog.Destroy()

	def on_manage_conversation_profiles(self, event: wx.Event | None):
		"""Open the conversation profile management dialog to manage conversation profiles.

		Open the conversation profile management dialog to create, edit, or delete conversation profiles. If the dialog is closed with changes, it updates the profile menu.

		Args:
			event: The event that triggered the profile management action. Can be None.
		"""
		from .conversation_profile_dialog import ConversationProfileDialog

		profile_dialog = ConversationProfileDialog(
			self, _("Manage conversation profiles")
		)
		profile_dialog.ShowModal()
		if profile_dialog.menu_update:
			menu: wx.Menu = self.new_conversation_profile_item.GetMenu()
			item_index = next(
				locate(
					menu.GetMenuItems(),
					lambda x: x.GetId()
					== self.new_conversation_profile_item.GetId(),
				)
			)
			menu.Remove(self.new_conversation_profile_item.GetId())
			self.new_conversation_profile_item.GetSubMenu().Destroy()
			self.new_conversation_profile_item.SetSubMenu(
				self.build_profile_menu(self.on_new_conversation)
			)
			menu.Insert(item_index, self.new_conversation_profile_item)
		profile_dialog.Destroy()

	def on_install_nvda_addon(self, event):
		"""Install the NVDA addon for BasiliskLLM.

		Extract the NVDA addon files from the resource folder and create a temporary nvda addon (zip) file. If the nvda addon  file is successfully created, it is opened using the system default application for nvda addon files. If the operation fails, an error message is displayed.
		"""
		import zipfile

		res_nvda_addon_path = os.path.join(
			global_vars.resource_path, "connectors", "nvda"
		)
		try:
			if not os.path.isdir(res_nvda_addon_path):
				raise ValueError(
					f"NVDA addon folder not found: {res_nvda_addon_path}"
				)

			tmp_nvda_addon_path = os.path.join(
				tempfile.gettempdir(), "basiliskllm.nvda-addon"
			)
			log.debug(f"Creating NVDA addon: {tmp_nvda_addon_path}")
			with zipfile.ZipFile(
				tmp_nvda_addon_path, 'w', zipfile.ZIP_DEFLATED
			) as zipf:
				for root, _, files in os.walk(res_nvda_addon_path):
					for file in files:
						file_path = os.path.join(root, file)
						arcname = os.path.relpath(
							file_path, start=res_nvda_addon_path
						)
						zipf.write(file_path, arcname)
			log.debug("NVDA addon created")
			os.startfile(tmp_nvda_addon_path)
		except Exception as e:
			log.error(f"Failed to create NVDA addon: {e}")
			wx.MessageBox(
				_("Failed to create NVDA addon"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)

	def on_github_repo(self, event: wx.Event | None):
		"""Open the GitHub repository for BasiliskLLM in the default browser.

		Args:
			event: The event that triggered the GitHub repository action. Can be None.
		"""
		wx.LaunchDefaultBrowser(APP_SOURCE_URL)

	def on_roko_basilisk(self, event: wx.Event | None):
		"""Open the Wikipedia page for Roko's Basilisk in the default browser.

		Args:
			event: The event that triggered the Roko's Basilisk action. Can be None.
		"""
		wx.LaunchDefaultBrowser(
			"https://en.wikipedia.org/wiki/Roko%27s_basilisk"
		)

	def on_about(self, event: wx.Event | None):
		"""Display the about dialog for the application.

		Args:
			event: The event that triggered the about dialog action. Can be None.
		"""
		from .about_dialog import display_about_dialog

		display_about_dialog(self)

	def on_manual_update_check(self, event: wx.Event | None):
		"""Manually check for application updates.

		Args:
			event: The event that triggered the update check action. Can be None.
		"""
		log.debug("Checking for updates")
		UpdateDialog(parent=self, title=_("Check updates")).Show()

	def on_view_log(self, event: wx.Event | None):
		"""Open the application log file in the system default text editor.

		Args:
			event: The event that triggered the log view action.
		"""
		try:
			os.startfile(get_log_file_path())
		except Exception as e:
			log.error(f"Failed to open log file: {e}")
			wx.MessageBox(
				_("Failed to open log file"), _("Error"), wx.OK | wx.ICON_ERROR
			)

	def on_ctrl_c(self, signum: int, frame: FrameType):
		"""Handle the SIGINT signal (Ctrl+C) to gracefully exit the application.

		Args:
			signum: The signal number that triggered the handler.
			frame: The current stack frame when the signal was received.
		"""
		self.signal_received = True

	def on_timer(self, event: wx.Event | None):
		"""Handle the timer event to check for pending signal actions.

		Args:
			event: The event that triggered the timer action. Can be None.
		"""
		if self.signal_received:
			log.debug("Received SIGINT")
			wx.CallAfter(self.on_quit, None)

	def show_update_notification(self, updater: BaseUpdater):
		"""Show a notification dialog for a new application update.

		Args:
			updater: The updater instance with the update information.
		"""
		log.info("Showing update notification")

		def show_dialog():
			update_dialog = UpdateDialog(
				parent=self, title=_("New version available"), updater=updater
			)
			update_dialog.ShowModal()
			log.debug(f"Update dialog shown: {update_dialog.IsShown()}")

		wx.CallAfter(show_dialog)

	def show_update_download(self, updater: BaseUpdater):
		"""Show a download dialog for a new application update.

		Args:
			updater: The updater instance with the update information.
		"""
		log.info("Showing update download dialog")

		def show_dialog():
			download_dialog = DownloadUpdateDialog(
				parent=self, title=_("Downloading update"), updater=updater
			)
			download_dialog.ShowModal()
			log.debug(f"Download dialog shown: {download_dialog.IsShown()}")

		wx.CallAfter(show_dialog)

	def build_manage_profile_item(self) -> wx.MenuItem:
		"""Build the manage conversation profile menu item.

		Returns:
			The manage conversation profile menu item.
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
			event_handler: The event handler to apply the selected profile.

		Returns:
			The conversation profile menu.
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

	def on_notebook_context_menu(self, event: wx.Event | None):
		"""Handle the context menu event for the notebook.

		Args:
			event: The event that triggered the context menu action. Can be None.
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

	def on_apply_conversation_profile(self, event: wx.Event):
		"""Apply the selected conversation profile to the current conversation.

		Args:
			event: The event that triggered the profile application action.
		"""
		profile = self.get_selected_profile_from_menu(event)
		if not profile:
			return
		log.info(f"Applying profile: {profile.name} to conversation")
		self.current_tab.apply_profile(profile)

	def handle_no_account_configured(self):
		"""Handles the scenario when no account is configured for the application.

		This method checks if any accounts are configured. If no accounts exist, it displays a message box
		prompting the user to add an account. If the user confirms, it opens the account management dialog.
		"""
		if config.accounts():
			return
		first_account_msg = wx.MessageBox(
			# translators: This message is displayed when no account is configured and the user tries to use the conversation tab.
			_(
				"Please add an account first. Do you want to add an account now?"
			),
			# translators: This is a title for the message box
			_("No account configured"),
			wx.YES_NO | wx.ICON_QUESTION,
		)
		if first_account_msg == wx.YES:
			self.on_manage_accounts(None)

	def on_save_conversation(self, event: wx.Event | None):
		"""Save the current conversation to its associated file path.

		If no conversation tab is selected, displays an error message. If the conversation
		does not have an associated file path, prompts the user to choose a save location
		using the save-as dialog. Otherwise, saves the conversation to its existing file path.

		Args:
			event: The event that triggered the save action
		"""
		current_tab = self.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if not current_tab.bskc_path:
			current_tab.bskc_path = self.on_save_as_conversation(event)
			return
		current_tab.save_conversation(current_tab.bskc_path)

	def on_save_as_conversation(self, event: wx.Event | None) -> Optional[str]:
		"""Save the current conversation to a user-specified file path.

		Opens a file dialog for the user to choose a location and filename for saving the current conversation. Supports saving Basilisk conversation files with the .bskc extension.

		Args:
			event: The event that triggered the save action (typically a menu or button click)

		Returns:
			The full file path where the conversation was saved if successful, or None if no file was selected or the save operation failed
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
			success = current_tab.save_conversation(file_path)
		file_dialog.Destroy()
		return file_path if success else None

	def open_conversation(self, file_path: str):
		"""Open a conversation from a specified file path.

		Attempts to create a new conversation tab by loading a conversation file. If successful,
		the new tab is added to the notebook. If an error occurs during file opening, an error
		message is displayed to the user and logged.

		Args:
			file_path: The full path to the conversation file to be opened.
		"""
		try:
			new_tab = ConversationTab.open_conversation(
				self.notebook, file_path, self.get_default_conv_title()
			)
			if new_tab:
				self.add_conversation_tab(new_tab)
		except Exception as e:
			wx.MessageBox(
				# Translators: An error message when a conversation file cannot be opened
				_("Failed to open conversation file: '%s', error: %s")
				% (file_path, e),
				style=wx.OK | wx.ICON_ERROR,
			)
			log.error(
				f"Failed to open conversation file: {file_path}, error: {e}",
				exc_info=e,
			)

	def on_open_conversation(self, event: wx.Event | None):
		"""Open a conversation file selected by the user.

		This method displays a file dialog for the user to choose a Basilisk conversation file (*.bskc),
		and then opens the selected conversation file using the `open_conversation` method.

		Args:
			event: The event that triggered the file dialog (typically a menu or button click)
		"""
		file_dialog = wx.FileDialog(
			self,
			# Translators: A title for the open conversation dialog
			message=_("Open conversation"),
			wildcard=_("Basilisk conversation files") + "(*.bskc)|*.bskc",
			style=wx.FD_OPEN,
		)
		if file_dialog.ShowModal() == wx.ID_OK:
			file_path = file_dialog.GetPath()
			self.open_conversation(file_path)
			file_dialog.Destroy()
