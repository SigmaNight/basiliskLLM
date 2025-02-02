from __future__ import annotations

import datetime
import threading
import typing

import wx
from PIL import ImageGrab

from basilisk.conversation import ImageFile
from basilisk.enums import CaptureMode

if typing.TYPE_CHECKING:
	from io import BufferedWriter

	from upath import UPath

	from basilisk.gui.main_frame import MainFrame


class ScreenCaptureThread(threading.Thread):
	def __init__(
		self,
		parent: MainFrame,
		path: UPath,
		capture_mode: CaptureMode = CaptureMode.FULL,
		screen_coordinates: tuple | None = None,
		name: str = "",
	):
		super().__init__()
		self.parent = parent
		self.capture_method = getattr(
			self, f"capture_{capture_mode.value}_screen", None
		)
		if not self.capture_method:
			raise NotImplementedError(
				f"Capture mode {capture_mode} not implemented"
			)
		self.path = path
		self.screen_coordinates = screen_coordinates
		if self.screen_coordinates and len(self.screen_coordinates) != 4:
			raise ValueError("Screen coordinates must be a tuple of 4 integers")
		self.name = name

	def run(self):
		image_name = self.name or datetime.datetime.now().strftime("%H:%M:%S")
		with self.path.open("wb") as f:
			image_file = self.capture_method(f, image_name)
		wx.CallAfter(self.parent.post_screen_capture, image_file)

	def capture_full_screen(
		self, file: BufferedWriter, base_img_name: str
	) -> ImageFile:
		screen_image = ImageGrab.grab()
		screen_image.save(file, "PNG")
		return ImageFile(
			location=self.path,
			name=_("Full screen capture (%s)") % base_img_name,
			dimensions=screen_image.size,
			size=file.tell(),
		)

	def capture_partial_screen(
		self, file: BufferedWriter, base_img_name: str
	) -> ImageFile:
		screen_image = ImageGrab.grab(bbox=self.screen_coordinates)
		screen_image.save(file, "PNG")
		return ImageFile(
			location=self.path,
			name=_("Partial screen capture (%s)") % base_img_name,
			dimensions=screen_image.size,
			size=file.tell(),
		)

	def capture_window_screen(
		self, file: BufferedWriter, base_img_name: str
	) -> ImageFile:
		screen = wx.ScreenDC()
		size = screen.GetSize()
		bmp = wx.Bitmap(size.width, size.height)
		mem = wx.MemoryDC(bmp)
		mem.Blit(0, 0, size.width, size.height, screen, 0, 0)
		del mem
		img: wx.Image = bmp.ConvertToImage()
		img.SaveFile(stream=file, type=wx.BITMAP_TYPE_PNG)
		return ImageFile(
			location=self.path,
			name=_("Window screen capture (%s)") % base_img_name,
			dimensions=(size.width, size.height),
			size=file.tell(),
		)
