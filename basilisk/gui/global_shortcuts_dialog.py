"""Global Shortcuts Dialog for managing global keyboard shortcuts.

This module provides a dialog for users to set and manage global
keyboard shortcuts for various actions in the application.
"""

import logging
from enum import StrEnum, auto
from typing import Dict, Optional, Tuple

import win32api
import win32con
import wx
import wx.adv

log = logging.getLogger(__name__)


class HotkeyAction(StrEnum):
	"""Enum for hotkey actions."""

	TOGGLE_VISIBILITY = auto()
	CAPTURE_FULL = auto()
	CAPTURE_WINDOW = auto()


MODIFIER_MAP: Dict[int, str] = {
	# Translators: Modifier key names
	win32con.MOD_ALT: "Alt",
	# Translators: Modifier key names
	win32con.MOD_CONTROL: _("Ctrl"),
	# Translators: Modifier key names
	win32con.MOD_WIN: _("Win"),
	# Translators: Modifier key names
	win32con.MOD_SHIFT: _("Shift"),
}

KEY_MAP: Dict[int, str] = {win32con.VK_SNAPSHOT: "PrintScreen"}


def get_key_name_from_win32con(key_code: int) -> Optional[str]:
	"""Retrieve the key name from win32con module.

	Args:
		key_code: The virtual key code to look up.

	Returns:
		The name of the key if found, otherwise None.
	"""
	for attr_name in dir(win32con):
		if attr_name.startswith("VK_"):
			if getattr(win32con, attr_name) == key_code:
				log.debug(f"Found key code: {attr_name}")
				return attr_name[3:]
	log.debug(f"Key code not found: {key_code}")
	return None


def shortcut_to_string(shortcut: Tuple[int, int]) -> str:
	"""Converts a shortcut tuple to a human-readable string.

	Args:
		shortcut: A tuple containing modifier keys and the raw key code.

	Returns:
		A string representation of the shortcut.
	"""
	modifiers, raw_key_code = shortcut
	mod_parts = [name for mod, name in MODIFIER_MAP.items() if modifiers & mod]
	key_name = get_key_name_from_win32con(raw_key_code) or chr(raw_key_code)
	return '+'.join(mod_parts + [key_name])


class GlobalShortcutsDialog(wx.Dialog):
	"""Dialog for managing global shortcuts."""

	def __init__(self, parent: Optional[wx.Window] = None):
		"""Initialize the Global Shortcuts dialog.

		Args:
			parent: The parent window for the dialog.
		"""
		super().__init__(
			parent,
			# Translators: Title of the global shortcuts dialog
			title=_("Global Shortcuts"),
			size=(350, 250),
		)
		self.current_shortcuts = {
			# Translators: Action name
			_("Minimize/Restore"): (
				win32con.MOD_WIN | win32con.MOD_ALT,
				win32con.VK_SPACE,
			),
			# Translators: Action name
			_("Capture Fullscreen"): (
				win32con.MOD_WIN | win32con.MOD_CONTROL,
				ord('U'),
			),
			# Translators: Action name
			_("Capture Active Window"): (
				win32con.MOD_WIN | win32con.MOD_CONTROL,
				ord('W'),
			),
		}
		self._init_ui()

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		self.action_list = wx.ListCtrl(panel, style=wx.LC_REPORT)
		self.action_list.InsertColumn(
			0,
			# Translators: Column header for the action name
			_("Action"),
			width=180,
		)
		self.action_list.InsertColumn(
			1,
			# Translators: Column header for the shortcut key
			_("Shortcut"),
			width=140,
		)
		self.populate_shortcut_list()

		assign_btn = wx.Button(panel, label="Assign")
		assign_btn.Bind(wx.EVT_BUTTON, self.on_set_shortcut)

		close_button = wx.Button(panel, wx.ID_CLOSE)
		close_button.Bind(wx.EVT_BUTTON, self.on_close)

		main_sizer.Add(
			self.action_list, proportion=1, flag=wx.EXPAND | wx.ALL, border=5
		)
		main_sizer.Add(assign_btn, flag=wx.ALIGN_CENTER | wx.ALL, border=5)
		main_sizer.Add(close_button, flag=wx.ALIGN_CENTER | wx.ALL, border=5)

		panel.SetSizer(main_sizer)

	def populate_shortcut_list(self) -> None:
		"""Populate the list control with current shortcuts."""
		self.action_list.DeleteAllItems()
		for idx, (action, shortcut) in enumerate(
			self.current_shortcuts.items()
		):
			self.action_list.InsertItem(idx, action)
			self.action_list.SetItem(idx, 1, shortcut_to_string(shortcut))

	def on_set_shortcut(self, event: wx.Event) -> None:
		"""Handle the event when the user clicks the 'Assign' button.

		Args:
			event: The event object.
		"""
		selected_index = self.action_list.GetFirstSelected()
		if selected_index == -1:
			wx.MessageBox(
				# Translators: Error message when no action is selected
				_("Please select an action to assign a new shortcut."),
				# Translators: Error message title
				_("Error"),
				wx.ICON_ERROR | wx.OK,
			)
			return

		action = self.action_list.GetItemText(selected_index)
		dlg = ShortcutCaptureDialog(self)
		if dlg.ShowModal() == wx.ID_OK:
			new_shortcut = dlg.get_shortcut()
			if new_shortcut:
				self.current_shortcuts[action] = new_shortcut
				wx.MessageBox(
					# Translators: Message when a new shortcut is assigned
					_("Captured shortcut for {action}: {new_shortcut}").format(
						action=action,
						new_shortcut=shortcut_to_string(new_shortcut),
					),
					# Translators: Message title when a new shortcut is assigned
					_("Shortcut Captured"),
					wx.OK | wx.ICON_INFORMATION,
				)
				self.populate_shortcut_list()

	def on_close(self, event: wx.Event) -> None:
		"""Handle the event when the user clicks the 'Close' button.

		Args:
			event: The event object.
		"""
		self.EndModal(wx.ID_CLOSE)


class ShortcutCaptureDialog(wx.Dialog):
	"""Dialog for capturing a global shortcut key combination."""

	def __init__(self, parent: Optional[wx.Window] = None):
		"""Initialize the Shortcut Capture dialog.

		Args:
			parent: The parent window for the dialog.
		"""
		super().__init__(
			parent,
			# Translators: Title of the shortcut capture dialog
			title=_("Press the Shortcut"),
			size=(250, 100),
		)
		self.shortcut: Optional[Tuple[int, int]] = None
		self._init_ui()

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		instruction = wx.StaticText(
			panel, label="Press the desired shortcut key combination."
		)
		sizer.Add(instruction, flag=wx.EXPAND | wx.ALL, border=5)

		panel.SetSizer(sizer)
		panel.Bind(wx.EVT_KEY_UP, self.on_key_up)

	def on_key_up(self, event: wx.KeyEvent) -> None:
		"""Handle the key up event to capture the shortcut.

		Args:
			event: The key event object.
		"""
		raw_key_code = event.GetRawKeyCode()

		mods = 0
		if win32api.GetAsyncKeyState(
			win32con.VK_LWIN
		) or win32api.GetAsyncKeyState(win32con.VK_RWIN):
			mods |= win32con.MOD_WIN
		if win32api.GetAsyncKeyState(win32con.VK_MENU):  # Alt key
			mods |= win32con.MOD_ALT
		if win32api.GetAsyncKeyState(win32con.VK_CONTROL):
			mods |= win32con.MOD_CONTROL
		if win32api.GetAsyncKeyState(win32con.VK_SHIFT):
			mods |= win32con.MOD_SHIFT

		log.debug(f"Key down: {mods=}, key_code={raw_key_code=}")
		if raw_key_code and mods:
			self.shortcut = (mods, raw_key_code)
			self.EndModal(wx.ID_OK)
		else:
			log.debug("Invalid shortcut key combination.")
			wx.MessageBox(
				# Translators: Error message when an invalid shortcut key is pressed
				_(
					"Please press a valid key with at least one modifier ({modifiers})."
				).format(modifiers=', '.join(MODIFIER_MAP.values())),
				# Translators: Error message title
				_("Invalid Shortcut"),
				wx.OK | wx.ICON_WARNING,
			)

	def get_shortcut(self) -> Optional[Tuple[int, int]]:
		"""Get the captured shortcut."""
		return self.shortcut
