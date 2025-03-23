"""Global hotkey handling for Windows using wxPython.

This module provides functionality to register and unregister global hotkeys
and handle their events in a wxPython application.
It uses the Windows API to register hotkeys and handle events.
"""

import ctypes
import logging
from ctypes import wintypes
from typing import Callable, Dict, Optional, Tuple

import win32api
import win32con
import wx

log = logging.getLogger(__name__)

# Windows API setup
user32 = ctypes.WinDLL('user32', use_last_error=True)
user32.GetKeyNameTextW.argtypes = [wintypes.LONG, wintypes.LPWSTR, ctypes.c_int]
user32.GetKeyNameTextW.restype = ctypes.c_int

# Define hotkey event
wxEVT_HOTKEY = wx.NewEventType()
EVT_HOTKEY = wx.PyEventBinder(wxEVT_HOTKEY, 1)


MODIFIER_MAP: Dict[int, str] = {
	win32con.MOD_ALT: 'Alt',
	win32con.MOD_CONTROL: 'Ctrl',
	win32con.MOD_WIN: 'Win',
	win32con.MOD_SHIFT: 'Shift',
}

DISPLAY_NAME_KEY_MAP: Dict[int, str] = {
	win32con.VK_SNAPSHOT: 'PrintScreen',
	win32con.VK_SPACE: 'Space',
	win32con.VK_TAB: 'Tab',
	win32con.VK_RETURN: 'Enter',
	win32con.VK_ESCAPE: 'Esc',
}


class HotkeyEvent(wx.PyCommandEvent):
	"""Custom event for hotkey notifications."""

	def __init__(self, win_id: int, modifiers: int, vk_code: int):
		"""Initialize the hotkey event.

		Args:
			win_id: The window ID for the event.
			modifiers: The modifiers associated with the hotkey.
			vk_code: The virtual key code for the hotkey.
		"""
		super().__init__(wxEVT_HOTKEY, win_id)
		self._modifiers = modifiers
		self._vk_code = vk_code

	def GetModifiers(self) -> int:
		"""Get the modifiers associated with the hotkey."""
		return self._modifiers

	def GetKeyCode(self) -> int:
		"""Get the virtual key code."""
		return self._vk_code


def get_key_name(vk_code: int) -> Optional[str]:
	"""Get the name of a key using Windows API."""
	scan_code = win32api.MapVirtualKey(vk_code, 0) << 16

	buf = ctypes.create_unicode_buffer(32)
	if user32.GetKeyNameTextW(scan_code, buf, len(buf)) > 0:
		return buf.value
	return None


def get_vk_code_display_name(key_code: int) -> Optional[str]:
	"""Get display name for a virtual key code."""
	# Try predefined names first
	if key_code in DISPLAY_NAME_KEY_MAP:
		return DISPLAY_NAME_KEY_MAP[key_code]

	# Try to get localized key name
	key_name = get_key_name(key_code)
	if key_name:
		return key_name

	# Fallback to basic character for printable ASCII
	if ord('0') <= key_code <= ord('9') or ord('A') <= key_code <= ord('Z'):
		return chr(key_code)

	# Last resort - try to get name from virtual key code
	try:
		scan_code = win32api.MapVirtualKey(key_code, 0)
		if scan_code:
			return chr(scan_code)
	except Exception:
		pass

	return None


def shortcut_to_string(shortcut: Tuple[int, int]) -> str:
	"""Convert shortcut tuple to readable string."""
	modifiers, vk_code = shortcut
	mod_parts = [name for mod, name in MODIFIER_MAP.items() if modifiers & mod]
	key_name = get_vk_code_display_name(vk_code)
	if not key_name:
		return "Unknown"
	return '+'.join(mod_parts + [key_name])


def get_base_vk_code(shortcut: Tuple[int, int]) -> Tuple[int, int]:
	"""Convert a shortcut with special chars to its base form.

	Args:
		shortcut: A tuple containing the modifiers and virtual key code
	Returns:
		A tuple containing the base modifiers and virtual key code
	"""
	modifiers, vk_code = shortcut

	keyboard_state = (ctypes.c_byte * 256)()

	try:
		scan_code = win32api.MapVirtualKey(vk_code, 0)
		if scan_code:
			buf = ctypes.create_unicode_buffer(5)
			result = user32.ToUnicode(
				vk_code, scan_code, keyboard_state, buf, len(buf), 0
			)

			if result > 0:
				base_char = buf.value[0]
				vk_scan = win32api.VkKeyScan(base_char)
				if vk_scan != -1:
					base_vk = vk_scan & 0xFF
					shift_state = (vk_scan >> 8) & 0xFF

					new_mods = modifiers
					if shift_state & 1:  # SHIFT
						new_mods |= win32con.MOD_SHIFT
					if shift_state & 2:  # CTRL
						new_mods |= win32con.MOD_CONTROL
					if shift_state & 4:  # ALT
						new_mods |= win32con.MOD_ALT

					log.debug(
						f'Converted {shortcut_to_string(shortcut)} to {shortcut_to_string((new_mods, base_vk))}'
					)
					return (new_mods, base_vk)
	except Exception as e:
		log.debug(f'Error converting special char: {e}')

	return shortcut


def generate_hotkey_id(shortcut: Tuple[int, int]) -> int:
	"""Generate a unique ID for a hotkey combination.

	Args:
		shortcut: A tuple containing the modifiers and virtual key code
	Returns:
		A unique integer ID for the hotkey
	"""
	modifiers, vk_code = shortcut
	# Combine modifiers and vk_code into a unique 32-bit integer
	return ((modifiers & 0xFFFF) << 16) | (vk_code & 0xFFFF)


def register_hotkey(hwnd: int, shortcut: Tuple[int, int]) -> bool:
	"""Register a global hotkey with Windows.

	Args:
		hwnd: The handle of the window to receive the hotkey messages
		shortcut: The shortcut to register
	Returns:
		True if registered successfully, False otherwise
	"""
	modifiers, vk_code = shortcut
	hotkey_id = generate_hotkey_id(shortcut)

	try:
		user32.UnregisterHotKey(hwnd, hotkey_id)
	except Exception:
		pass

	try:
		success = user32.RegisterHotKey(hwnd, hotkey_id, modifiers, vk_code)
		if not success:
			error = ctypes.get_last_error()
			log.error(
				f'Failed to register hotkey {shortcut_to_string(shortcut)}: error {error}'
			)
			return False
		return True
	except Exception as e:
		log.error(f'Error registering hotkey: {e}')
		return False


def unregister_hotkey(hwnd: int, shortcut: Tuple[int, int]) -> bool:
	"""Unregister a global hotkey.

	Args:
		hwnd: The handle of the window to unregister the hotkey from
		shortcut: The shortcut to unregister
	Returns:
		True if unregistered successfully, False otherwise
	"""
	try:
		hotkey_id = generate_hotkey_id(shortcut)
		return bool(user32.UnregisterHotKey(hwnd, hotkey_id))
	except Exception as e:
		log.error(f'Error unregistering hotkey: {e}')
		return False


class HotkeyHandler(wx.Frame):
	"""Frame to handle global hotkeys."""

	def __init__(self):
		"""Initialize the HotkeyHandler."""
		super().__init__(None, title='Hidden Hotkey Handler')
		self.registered_shortcuts: Dict[
			int, Tuple[Tuple[int, int], Callable]
		] = {}

		# Bind Windows message handler
		self.Bind(wx.EVT_WINDOW_CREATE, self.on_create)

	def on_create(self, event: wx.WindowCreateEvent) -> None:
		"""Setup message handler after window is created.

		Args:
			event: The event object.
		"""
		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)
		event.Skip()

	def on_char_hook(self, event: wx.KeyEvent) -> None:
		"""Handle Windows messages including WM_HOTKEY.

		Args:
			event: The event object.
		"""
		msg = event.GetEventObject().GetHandle()
		if msg == win32con.WM_HOTKEY:
			wparam = event.GetWParam()
			if wparam in self.registered_shortcuts:
				shortcut, callback = self.registered_shortcuts[wparam]
				wx.PostEvent(
					self, HotkeyEvent(self.GetId(), shortcut[0], shortcut[1])
				)
		event.Skip()

	def register_shortcut(
		self, shortcut: Tuple[int, int], callback: Callable
	) -> bool:
		"""Register a global shortcut with callback.

		Args:
			shortcut: The shortcut to register
			callback: The callback function to call when the shortcut is pressed
		Returns:
			True if registered successfully, False otherwise
		"""
		base_shortcut = get_base_vk_code(shortcut)
		hotkey_id = generate_hotkey_id(base_shortcut)

		if register_hotkey(self.GetHandle(), base_shortcut):
			self.registered_shortcuts[hotkey_id] = (base_shortcut, callback)
			self.Bind(EVT_HOTKEY, lambda evt: wx.CallAfter(callback))
			return True
		return False

	def unregister_shortcut(self, shortcut: Tuple[int, int]) -> bool:
		"""Unregister a global shortcut.

		Args:
			shortcut: The shortcut to unregister
		Returns:
			True if unregistered successfully, False otherwise
		"""
		base_shortcut = get_base_vk_code(shortcut)
		hotkey_id = generate_hotkey_id(base_shortcut)

		if unregister_hotkey(self.GetHandle(), base_shortcut):
			self.registered_shortcuts.pop(hotkey_id, None)
			return True
		return False

	def __del__(self) -> None:
		"""Cleanup registered hotkeys on deletion."""
		for hotkey_id, (shortcut, _) in list(self.registered_shortcuts.items()):
			unregister_hotkey(self.GetHandle(), shortcut)


class HotkeyHandlerMixin:
	"""Mixin to add hotkey handling capabilities to wx.App."""

	def init_hotkeys(self) -> None:
		"""Initialize the hotkey handler."""
		self.hotkey_handler = HotkeyHandler()

	def register_hotkey(
		self, shortcut: Tuple[int, int], callback: Callable
	) -> bool:
		"""Register a global hotkey.

		Args:
			shortcut: The shortcut to register
			callback: The callback function to call when the shortcut is pressed
		Returns:
			True if registered successfully, False otherwise
		"""
		return self.hotkey_handler.register_shortcut(shortcut, callback)

	def unregister_hotkey(self, shortcut: Tuple[int, int]) -> bool:
		"""Unregister a global hotkey.

		Args:
			shortcut: The shortcut to unregister
		Returns:
			True if unregistered successfully, False otherwise
		"""
		return self.hotkey_handler.unregister_shortcut(shortcut)
