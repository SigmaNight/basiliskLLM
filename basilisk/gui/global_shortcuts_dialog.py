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

WXK_TO_VK_CODE_MAP: Dict[int, int] = {
	wx.WXK_ESCAPE: win32con.VK_ESCAPE,
	wx.WXK_F1: win32con.VK_F1,
	wx.WXK_F2: win32con.VK_F2,
	wx.WXK_F3: win32con.VK_F3,
	wx.WXK_F4: win32con.VK_F4,
	wx.WXK_F5: win32con.VK_F5,
	wx.WXK_F6: win32con.VK_F6,
	wx.WXK_F7: win32con.VK_F7,
	wx.WXK_F8: win32con.VK_F8,
	wx.WXK_F9: win32con.VK_F9,
	wx.WXK_F10: win32con.VK_F10,
	wx.WXK_F11: win32con.VK_F11,
	wx.WXK_F12: win32con.VK_F12,
	wx.WXK_F13: win32con.VK_F13,
	wx.WXK_F14: win32con.VK_F14,
	wx.WXK_F15: win32con.VK_F15,
	wx.WXK_F16: win32con.VK_F16,
	wx.WXK_F17: win32con.VK_F17,
	wx.WXK_F18: win32con.VK_F18,
	wx.WXK_F19: win32con.VK_F19,
	wx.WXK_F20: win32con.VK_F20,
	wx.WXK_F21: win32con.VK_F21,
	wx.WXK_F22: win32con.VK_F22,
	wx.WXK_F23: win32con.VK_F23,
	wx.WXK_F24: win32con.VK_F24,
	wx.WXK_SPACE: win32con.VK_SPACE,
	wx.WXK_PAGEUP: win32con.VK_PRIOR,
	wx.WXK_PAGEDOWN: win32con.VK_NEXT,
	wx.WXK_HOME: win32con.VK_HOME,
	wx.WXK_END: win32con.VK_END,
	wx.WXK_LEFT: win32con.VK_LEFT,
	wx.WXK_RIGHT: win32con.VK_RIGHT,
	wx.WXK_UP: win32con.VK_UP,
	wx.WXK_DOWN: win32con.VK_DOWN,
	wx.WXK_INSERT: win32con.VK_INSERT,
	wx.WXK_DELETE: win32con.VK_DELETE,
	wx.WXK_MULTIPLY: win32con.VK_MULTIPLY,
	wx.WXK_ADD: win32con.VK_ADD,
	wx.WXK_SEPARATOR: win32con.VK_SEPARATOR,
	wx.WXK_SUBTRACT: win32con.VK_SUBTRACT,
	wx.WXK_DECIMAL: win32con.VK_DECIMAL,
	wx.WXK_DIVIDE: win32con.VK_DIVIDE,
	wx.WXK_NUMPAD0: win32con.VK_NUMPAD0,
	wx.WXK_NUMPAD1: win32con.VK_NUMPAD1,
	wx.WXK_NUMPAD2: win32con.VK_NUMPAD2,
	wx.WXK_NUMPAD3: win32con.VK_NUMPAD3,
	wx.WXK_NUMPAD4: win32con.VK_NUMPAD4,
	wx.WXK_NUMPAD5: win32con.VK_NUMPAD5,
	wx.WXK_NUMPAD6: win32con.VK_NUMPAD6,
	wx.WXK_NUMPAD7: win32con.VK_NUMPAD7,
	wx.WXK_NUMPAD8: win32con.VK_NUMPAD8,
	wx.WXK_NUMPAD9: win32con.VK_NUMPAD9,
	wx.WXK_NUMLOCK: win32con.VK_NUMLOCK,
	wx.WXK_SCROLL: win32con.VK_SCROLL,
	wx.WXK_BROWSER_BACK: win32con.VK_BROWSER_BACK,
	wx.WXK_BROWSER_FORWARD: win32con.VK_BROWSER_FORWARD,
	wx.WXK_VOLUME_MUTE: win32con.VK_VOLUME_MUTE,
	wx.WXK_VOLUME_UP: win32con.VK_VOLUME_UP,
	wx.WXK_VOLUME_DOWN: win32con.VK_VOLUME_DOWN,
	wx.WXK_MEDIA_PREV_TRACK: win32con.VK_MEDIA_PREV_TRACK,
	wx.WXK_MEDIA_NEXT_TRACK: win32con.VK_MEDIA_NEXT_TRACK,
	wx.WXK_MEDIA_PLAY_PAUSE: win32con.VK_MEDIA_PLAY_PAUSE,
	wx.WXK_BACK: win32con.VK_BACK,
	wx.WXK_TAB: win32con.VK_TAB,
	wx.WXK_RETURN: win32con.VK_RETURN,
	wx.WXK_SHIFT: win32con.VK_SHIFT,
	wx.WXK_CONTROL: win32con.VK_CONTROL,
	wx.WXK_MENU: win32con.VK_MENU,
	wx.WXK_PAUSE: win32con.VK_PAUSE,
	wx.WXK_CAPITAL: win32con.VK_CAPITAL,
}

DISPLAY_NAME_KEY_MAP: Dict[int, str] = {win32con.VK_SNAPSHOT: "PrintScreen"}


def get_vk_code_display_name(key_code: int) -> Optional[str]:
	"""Retrieve the key name from win32con module.

	Args:
		key_code: The virtual key code.

	Returns:
		A string representation of the key name.
	"""
	if ord('0') <= key_code <= ord('9') or ord('A') <= key_code <= ord('Z'):
		return chr(key_code)
	if key_code in DISPLAY_NAME_KEY_MAP:
		return DISPLAY_NAME_KEY_MAP[key_code]
	for attr_name in dir(win32con):
		if attr_name.startswith("VK_"):
			if getattr(win32con, attr_name) == key_code:
				return attr_name[3:]
	log.debug(f"Key code not found: {key_code}")
	return None


def shortcut_to_string(shortcut: Tuple[int, int]) -> str:
	"""Converts a shortcut tuple to a human-readable string.

	Args:
		shortcut: A tuple containing the modifiers and the virtual key code.

	Returns:
		A string representation of the shortcut.
	"""
	""""""
	modifiers, vk_code = shortcut
	mod_parts = [name for mod, name in MODIFIER_MAP.items() if modifiers & mod]
	key_name = get_vk_code_display_name(vk_code)
	return '+'.join(mod_parts + [key_name])


def get_vk_code(wx_key_code: int) -> Optional[int]:
	"""Converts a WX key code to a VK code."""
	if wx_key_code in WXK_TO_VK_CODE_MAP:
		return WXK_TO_VK_CODE_MAP[wx_key_code]
	elif ord('0') <= wx_key_code <= ord('9') or ord('A') <= wx_key_code <= ord(
		'Z'
	):
		return wx_key_code
	return None


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
		self._update_ui()

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
		self.action_list.Bind(wx.EVT_KEY_DOWN, self.on_action_list)

		assign_btn = wx.Button(panel, label="Assign")
		assign_btn.Bind(wx.EVT_BUTTON, self.on_set_shortcut)

		close_button = wx.Button(panel, wx.ID_CLOSE)
		close_button.Bind(wx.EVT_BUTTON, self.on_close)
		self.SetEscapeId(wx.ID_CLOSE)

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

	def _update_ui(self) -> None:
		self.populate_shortcut_list()

	def on_action_list(self, event: wx.KeyEvent) -> None:
		"""Handle key events in the action list.

		Args:
			event: The key event object.
		"""
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_set_shortcut(event)
		else:
			event.Skip()

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
			new_shortcut = dlg.shortcut
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
				self.action_list.Select(selected_index, on=True)
				self.action_list.Focus(selected_index)

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
		self._shortcut: Optional[Tuple[int, int]] = None
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
		"""Handle the key up event.

		Args:
			event: The key event object.
		"""
		key_code = event.GetKeyCode()

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
		vk_code = get_vk_code(key_code)
		log.debug(f"Key down: {mods=}, {key_code=}")
		if mods and vk_code:
			self._shortcut = (mods, vk_code)
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

	@property
	def shortcut(self) -> Optional[Tuple[int, int]]:
		"""Get the captured shortcut key combination."""
		return self._shortcut
