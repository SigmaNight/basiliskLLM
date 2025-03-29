"""Global Shortcuts Dialog for managing global keyboard shortcuts.

This module provides a dialog for users to set and manage global
keyboard shortcuts for various actions in the application.
"""

import logging
from typing import Dict, Optional, Tuple

import win32api
import win32con
import wx

from basilisk.hotkeys import MODIFIER_MAP, get_base_vk_code, shortcut_to_string

log = logging.getLogger(__name__)


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
	wx.WXK_SPACE: win32con.VK_SPACE,
	wx.WXK_PAGEUP: win32con.VK_PRIOR,
	wx.WXK_PAGEDOWN: win32con.VK_NEXT,
	wx.WXK_END: win32con.VK_END,
	wx.WXK_HOME: win32con.VK_HOME,
	wx.WXK_LEFT: win32con.VK_LEFT,
	wx.WXK_UP: win32con.VK_UP,
	wx.WXK_RIGHT: win32con.VK_RIGHT,
	wx.WXK_DOWN: win32con.VK_DOWN,
	wx.WXK_INSERT: win32con.VK_INSERT,
	wx.WXK_DELETE: win32con.VK_DELETE,
}


def get_vk_code(event: wx.KeyEvent) -> Optional[int]:
	"""Converts a WX key code to a VK code.

	Args:
		event: The wxPython key event object.

	Returns:
		The corresponding VK code, or None if not found.
	"""
	# Try raw key code first
	raw_key = event.GetRawKeyCode()
	if raw_key:
		return raw_key

	# Then try standard wx key code mapping
	wx_key = event.GetKeyCode()
	if wx_key in WXK_TO_VK_CODE_MAP:
		return WXK_TO_VK_CODE_MAP[wx_key]

	# For normal characters, try to map unicode to VK
	if 32 <= wx_key <= 255:
		try:
			vk_code = win32api.VkKeyScan(chr(wx_key))
			if vk_code != -1:
				return vk_code & 0xFF
		except Exception:
			pass

	# For special characters, use the raw key flags
	raw_flags = event.GetRawKeyFlags()
	if raw_flags:
		return raw_flags & 0xFF

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
			# Translators: A dialog title for global shortcuts configuration.
			title=_("Global Shortcuts"),
			size=(350, 250),
		)
		self.current_shortcuts = {
			# Translators: An action name for toggling the visibility of the main window.
			_("Minimize/Restore"): (
				win32con.MOD_WIN | win32con.MOD_ALT,
				win32con.VK_SPACE,
			),
			# Translators: An action name for capturing the entire screen.
			_("Capture Fullscreen"): (
				win32con.MOD_WIN | win32con.MOD_CONTROL,
				ord('U'),
			),
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
		self.action_list.InsertColumn(0, _("Action"), width=180)
		self.action_list.InsertColumn(1, _("Shortcut"), width=140)
		self.action_list.Bind(wx.EVT_KEY_DOWN, self.on_action_list)

		assign_btn = wx.Button(panel, label=_("Assign"))
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
				_("Please select an action to assign a new shortcut."),
				_("Error"),
				wx.ICON_ERROR | wx.OK,
			)
			return

		action = self.action_list.GetItemText(selected_index)
		dlg = ShortcutCaptureDialog(self)

		if dlg.ShowModal() == wx.ID_OK:
			new_shortcut = dlg.shortcut
			if new_shortcut:
				# Unregister old shortcut
				old_shortcut = self.current_shortcuts[action]
				wx.GetApp().unregister_hotkey(old_shortcut)

				# Register new shortcut
				if wx.GetApp().register_hotkey(
					new_shortcut, self.get_callback_for_action(action)
				):
					self.current_shortcuts[action] = new_shortcut
					wx.MessageBox(
						_(
							"Captured shortcut for {action}: {new_shortcut}"
						).format(
							action=action,
							new_shortcut=shortcut_to_string(new_shortcut),
						),
						_("Shortcut Captured"),
						wx.OK | wx.ICON_INFORMATION,
					)
					self.populate_shortcut_list()
					self.action_list.Select(selected_index, on=True)
					self.action_list.Focus(selected_index)
				else:
					wx.MessageBox(
						_(
							"Failed to register the shortcut. It may be already in use."
						),
						_("Error"),
						wx.ICON_ERROR | wx.OK,
					)

	def get_callback_for_action(self, action: str) -> callable:
		"""Return the appropriate callback for an action."""
		pass

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
		# Translators: A dialog title for capturing a global shortcut key combination.
		super().__init__(parent, title=_("Press the Shortcu"), size=(250, 100))
		self._shortcut: Optional[Tuple[int, int]] = None
		self._init_ui()

	def _init_ui(self) -> None:
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		instruction = wx.StaticText(
			panel,
			# Translators: Instruction text for capturing a global shortcut key combination.
			label=_("Press the desired shortcut key combination."),
		)
		sizer.Add(instruction, flag=wx.EXPAND | wx.ALL, border=5)

		panel.SetSizer(sizer)
		panel.Bind(wx.EVT_KEY_UP, self.on_key_up)

	def on_key_up(self, event: wx.KeyEvent) -> None:
		"""Handle key up events to capture the shortcut.

		Args:
			event: The key event object.
		"""
		vk_code = get_vk_code(event)

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

		log.debug(f'Key up: mods={mods}, vk_code={vk_code}')

		if mods and vk_code:
			# Convert special chars to base form
			shortcut = get_base_vk_code((mods, vk_code))
			self._shortcut = shortcut
			self.EndModal(wx.ID_OK)
		else:
			log.debug('Invalid shortcut key combination.')
			wx.MessageBox(
				_(
					"Please press a valid key with at least one modifier ({modifiers})."
				).format(modifiers=', '.join(MODIFIER_MAP.values())),
				_("Invalid Shortcut"),
				wx.OK | wx.ICON_WARNING,
			)

	@property
	def shortcut(self) -> Optional[Tuple[int, int]]:
		"""Get the captured shortcut key combination."""
		return self._shortcut
