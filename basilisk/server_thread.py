"""Server thread for receiving commands from external applications like screen readers."""

from __future__ import annotations

import logging
import re
import socket
import threading
from typing import TYPE_CHECKING

import wx

from basilisk.screen_capture_thread import CaptureMode

if TYPE_CHECKING:
	from basilisk.gui.main_frame import MainFrame

log = logging.getLogger(__name__)


class ServerThread(threading.Thread):
	"""Thread for receiving commands from external applications like screen readers."""

	def __init__(self, frame: MainFrame, port: int) -> None:
		"""Initialize the server thread.

		Args:
			frame: Application main frame instance
			port: port to listen on
		"""
		super().__init__()
		self.frame = frame
		self.port = port
		self.running = threading.Event()
		self.daemon = True

	def run(self) -> None:
		"""Start the server thread.

		Listen on localhost with the specified port for incoming connections and process the received data.
		"""
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if not sock:
			log.error("Failed to create socket")
			return
		sock.bind(("127.0.0.1", self.port))
		self.running.set()
		log.info(f"Server started on port {self.port}")
		sock.listen(1)
		while self.running.is_set():
			sock.settimeout(1.0)
			try:
				conn, addr = sock.accept()
			except socket.timeout:
				continue
			with conn:
				try:
					data = conn.recv(1024 * 1024 * 20)
					if data:
						self.manage_rcv_data(data)
						conn.sendall(b"ACK")
					else:
						log.error("No data received")
				except Exception as e:
					log.error(f"Error receiving data: {e}")
				finally:
					conn.close()
		sock.close()

	def manage_rcv_data(self, data: bytes) -> None:
		r"""Process the received data.

		Evaluate the received data and call the appropriate method on the main frame.

		Examples:
			Grab a full screenshot:
			grab:full
			Grab a screenshot of the active window:
			grab:window
			Grab a screenshot of a specific area:
			grab:0, 0, 100, 100
			Grab a screenshot of a specific area with a name:
			grab:0, 0, 100, 100\nname
			Add an image from a URL:
			url:https://example.com/image.png
			Add an image from a URL with a name:
			url:https://example.com/image.png\nname
		Args:
			data: data received from the client
		"""
		data = data.decode("utf-8")
		if data.startswith("grab:"):
			grab_mode = data.split(':', 1)[1].strip()
			if grab_mode == "full":
				wx.CallAfter(self.frame.screen_capture, CaptureMode.FULL)
			elif grab_mode == "window":
				wx.CallAfter(self.frame.screen_capture, CaptureMode.WINDOW)
			elif re.match(r"\d+, ?\d+, ?\d+, ?\d+(?:;.*+)?", grab_mode):
				name = ""
				coords = grab_mode
				if '\n' in grab_mode:
					coords, name = grab_mode.split('\n', 1)
					coords = tuple(map(int, coords.split(",")))
					if len(coords) != 4:
						log.error("Invalid coordinates")
						return
					wx.CallAfter(
						self.frame.screen_capture,
						CaptureMode.PARTIAL,
						coords,
						name,
					)
			else:
				log.error(f"Invalid grab mode: {grab_mode}")
		elif data.startswith("url:"):
			name = ""
			url = data.split(':', 1)[1].strip()
			if '\n' in url:
				url, name = url.split('\n', 1)
				wx.CallAfter(self.frame.current_tab.add_image_url_thread, url)
		else:
			log.error(f"no action for data: {data}")

	def stop(self):
		"""Stop the server thread."""
		self.running.clear()
