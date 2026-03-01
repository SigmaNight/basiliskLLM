"""Screen capture functionality for the Basilisk application.

This module provides thread-based screen capture capabilities, supporting full screen,
partial screen, and window capture modes. It uses PIL for image capture and wx for
window-specific operations.
"""

from __future__ import annotations

import datetime
import enum
import threading
import typing

import wx
from PIL import ImageGrab

from basilisk.conversation import ImageFile

if typing.TYPE_CHECKING:
	from io import BufferedWriter

	from upath import UPath

	from basilisk.views.main_frame import MainFrame


class CaptureMode(enum.StrEnum):
	"""Enumeration of available screen capture modes."""

	# Capture the entire screen
	FULL = enum.auto()
	# Capture a specific region of the screen
	PARTIAL = enum.auto()
	# Capture the active window
	WINDOW = enum.auto()


class ScreenCaptureThread(threading.Thread):
	"""Thread class for handling screen capture operations.

	This class extends threading.Thread to perform screen captures asynchronously,
	supporting different capture modes and saving the results to a specified path.
	"""

	def __init__(
		self,
		parent: MainFrame,
		path: UPath,
		capture_mode: CaptureMode = CaptureMode.FULL,
		screen_coordinates: tuple | None = None,
		name: str = "",
	):
		"""Initialize the screen capture thread.

		Args:
			parent: The parent window that initiated the capture
			path: The path where the captured image will be saved
			capture_mode: The mode of capture. Defaults to CaptureMode.FULL
			screen_coordinates: Coordinates for partial capture (left, top, right, bottom). Defaults to None
			name: Custom name for the capture. Defaults to ""

		Raises:
			NotImplementedError: If the specified capture mode is not implemented
			ValueError: If screen_coordinates is provided but not in the correct format
		"""
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
		"""Execute the screen capture operation in a separate thread.

		Captures the screen according to the specified mode and saves the image
		to the designated path. Notifies the parent window when complete.
		"""
		image_name = self.name or datetime.datetime.now().strftime("%H:%M:%S")
		with self.path.open("wb") as f:
			image_file = self.capture_method(f, image_name)
		wx.CallAfter(self.parent.post_screen_capture, image_file)

	def capture_full_screen(
		self, file: BufferedWriter, base_img_name: str
	) -> ImageFile:
		"""Capture the entire screen.

		Args:
			file: The file object where the image will be saved
			base_img_name: Base name for the captured image

		Returns:
			Object containing metadata about the captured image
		"""
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
		"""Capture a specific region of the screen.

		Args:
			file: The file object where the image will be saved
			base_img_name: Base name for the captured image

		Returns:
			Object containing metadata about the captured image
		"""
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
		"""Capture the current window.

		Args:
			file: The file object where the image will be saved
			base_img_name: Base name for the captured image

		Returns:
			Object containing metadata about the captured image
		"""
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
