from __future__ import annotations

import datetime
import threading
import typing
from enum import Enum

import wx
from PIL import ImageGrab

from .image_file import ImageFile

if typing.TYPE_CHECKING:
	from basilisk.gui.main_frame import MainFrame


class CaptureMode(Enum):
	FULL = "full"
	PARTIAL = "partial"
	WINDOW = "window"


class ScreenCaptureThread(threading.Thread):
	def __init__(
		self,
		parent: "MainFrame",
		path: str,
		capture_mode: CaptureMode = CaptureMode.FULL,
		screen_coordinates: tuple = None,
		name: str = "",
	):
		super().__init__()
		self.parent = parent
		self.capture_mode = capture_mode
		self.path = path
		self.screen_coordinates = screen_coordinates
		self.name = name

	def run(self):
		match self.capture_mode:
			case CaptureMode.FULL:
				screen_image = ImageGrab.grab()
				screen_image.save(self.path, "PNG")
			case CaptureMode.PARTIAL:
				screen_image = ImageGrab.grab(bbox=self.screen_coordinates)
				screen_image.save(self.path, "PNG")
			case CaptureMode.WINDOW:
				screen = wx.ScreenDC()
				size = screen.GetSize()
				bmp = wx.Bitmap(size.width, size.height)
				mem = wx.MemoryDC(bmp)
				mem.Blit(0, 0, size.width, size.height, screen, 0, 0)
				del mem
				bmp.SaveFile(self.path, wx.BITMAP_TYPE_PNG)
			case _:
				raise ValueError("Invalid capture mode")

		name = self.name
		if not name:
			name = datetime.datetime.now().strftime("%H:%M:%S")
		match self.capture_mode:
			case CaptureMode.FULL:
				name = f"%s ({name})" % _("Full screen capture")
			case CaptureMode.WINDOW:
				name = f"%s ({name})" % _("Window capture")
			case CaptureMode.PARTIAL:
				name = f"%s ({name})" % _("Partial screen capture")
			case _:
				raise ValueError("Invalid capture mode")
		wx.CallAfter(
			self.parent.post_screen_capture, ImageFile(self.path, name=name)
		)
