from __future__ import annotations
from enum import Enum
import datetime
import threading
import typing
from PIL import ImageGrab
import wx
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
		if self.capture_mode == CaptureMode.FULL:
			screen_image = ImageGrab.grab()
			screen_image.save(self.path, "PNG")
		elif self.capture_mode == CaptureMode.PARTIAL:
			screen_image = ImageGrab.grab(bbox=self.screen_coordinates)
			screen_image.save(self.path, "PNG")
		elif self.capture_mode == CaptureMode.WINDOW:
			screen = wx.ScreenDC()
			size = screen.GetSize()
			bmp = wx.Bitmap(size.width, size.height)
			mem = wx.MemoryDC(bmp)
			mem.Blit(0, 0, size.width, size.height, screen, 0, 0)
			del mem
			bmp.SaveFile(self.path, wx.BITMAP_TYPE_PNG)
		else:
			raise ValueError("Invalid capture mode")

		name = self.name
		if not name:
			name = " (%s)" % datetime.datetime.now().strftime("%H:%M:%S")
		if self.capture_mode == CaptureMode.FULL:
			name = _("Full screen capture") + name
		elif self.capture_mode == CaptureMode.WINDOW:
			name = _("Window capture") + name
		else:
			name = _("Partial screen capture") + name
		wx.CallAfter(
			self.parent.post_screen_capture, ImageFile(self.path, name=name)
		)
