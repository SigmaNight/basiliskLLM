"""Module for the TaskBarIcon class."""

import logging

import wx
import wx.adv

from basilisk.consts import APP_NAME

log = logging.getLogger(__name__)


class TaskBarIcon(wx.adv.TaskBarIcon):
	"""Class for the taskbar icon."""

	def __init__(self, frame: wx.Frame):
		"""Initialize the taskbar icon.

		Args:
			frame: The main frame of the application.
		"""
		super(TaskBarIcon, self).__init__()
		log.debug("Initializing taskbar icon")
		self.frame = frame
		# TODO: Set a proper icon
		transparent_icon = wx.Icon()
		transparent_icon.CopyFromBitmap(wx.Bitmap(16, 16))
		self.SetIcon(transparent_icon, APP_NAME)

		self.Bind(wx.adv.EVT_TASKBAR_LEFT_DOWN, self.on_left_down)
		self.Bind(wx.adv.EVT_TASKBAR_RIGHT_DOWN, self.on_right_down)

	def on_left_down(self, event: wx.adv.TaskBarIconEvent):
		"""Handle the left mouse button being clicked.

		Args:
			event: The event object.
		"""
		self.frame.toggle_visibility(None)

	def on_right_down(self, event: wx.adv.TaskBarIconEvent):
		"""Handle the right mouse button being clicked.

		Args:
			event: The event object.
		"""
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
