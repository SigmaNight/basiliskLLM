import os
import tempfile
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

TMP_DIR = tempfile.gettempdir() + '/basilisk'


class FocusEventHandler(FileSystemEventHandler):
	def __init__(self, callback):
		self.callback = callback

	def on_modified(self, event):
		if event.src_path == os.path.join(TMP_DIR, "focus_file"):
			self.callback()


def send_focus_signal():
	with open(os.path.join(TMP_DIR, "focus_file"), 'w') as f:
		f.write(str(time.time()))


def watch_focus_signal(callback):
	event_handler = FocusEventHandler(callback)
	observer = Observer()
	observer.schedule(event_handler, TMP_DIR, recursive=False)
	observer.start()
	return observer
