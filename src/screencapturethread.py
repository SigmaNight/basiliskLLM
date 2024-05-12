from enum import Enum
import datetime
import threading
from PIL import ImageGrab
import wx
from imagefile import ImageFile


class CaptureMode(Enum):
	FULL = 'full'
	WINDOW = 'window'


class ScreenCaptureThread(threading.Thread):
	def __init__(
		self,
		parent: wx.Frame,
		filename: str,
		capture_mode: CaptureMode = CaptureMode.FULL,
	):
		super().__init__()
		self.filename = filename
		self.parent = parent
		self.capture_mode = capture_mode

	def run(self):
		if self.capture_mode == CaptureMode.FULL:
			screen_image = ImageGrab.grab()
			screen_image.save(self.filename, "PNG")
		elif self.capture_mode == CaptureMode.WINDOW:
			screen = wx.ScreenDC()
			size = screen.GetSize()
			bmp = wx.Bitmap(size.width, size.height)
			mem = wx.MemoryDC(bmp)
			mem.Blit(0, 0, size.width, size.height, screen, 0, 0)
			del mem
			bmp.SaveFile(self.filename, wx.BITMAP_TYPE_PNG)
		else:
			raise ValueError("Invalid capture mode")

		description = " (%s)" % datetime.datetime.now().strftime("%H:%M:%S")
		if self.capture_mode == CaptureMode.FULL:
			description = _("Full screen capture") + description
		elif self.capture_mode == CaptureMode.WINDOW:
			description = _("Window capture") + description
		wx.CallAfter(
			self.parent.post_screen_capture,
			ImageFile(self.filename, description),
		)
