import logging
import re
import socket
import threading
from basilisk.imagefile import ImageFile
from basilisk.screencapturethread import CaptureMode

log = logging.getLogger(__name__)


class ServerThread(threading.Thread):
	def __init__(self, frame, port):
		super().__init__()
		self.frame = frame
		self.port = port
		self.running = False

	def run(self):
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		if not sock:
			log.error("Failed to create socket")
			return
		sock.bind(("127.0.0.1", self.port))
		self.running = True
		log.info(f"Server started on port {self.port}")
		sock.listen(1)
		while True:
			conn, addr = sock.accept()
			with conn:
				try:
					data = conn.recv(1024 * 1024 * 20)
					if data:
						data = data.decode("utf-8")
						log.debug(f"Received data: {data}")
						if data.startswith("grab:"):
							grab_mode = data.replace(' ', '').split(":")[1]
							if grab_mode == "full":
								self.frame.screen_capture(CaptureMode.FULL)
							elif grab_mode == "window":
								self.frame.screen_capture(CaptureMode.WINDOW)
							elif re.match(r"\d+,\d+,\d+,\d+", grab_mode):
								coords = tuple(map(int, grab_mode.split(",")))
								self.frame.capture_partial_screen(coords)
						elif data.startswith("url:"):
							url = data.split(":", 1)[1]
							self.frame.current_tab.add_images(
								[
									ImageFile(
										location=url,
										name="Image",
										size=-1,
										dimensions=(0, 0),
									)
								]
							)
						else:
							log.error(f"no action for data: {data}")
						conn.sendall(b"ACK")
					else:
						log.error("No data received")
				except Exception as e:
					log.error(f"Error receiving data: {e}")
				finally:
					conn.close()

	def stop(self):
		self.running = False
