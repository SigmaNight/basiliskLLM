from __future__ import annotations
from typing import Callable, TYPE_CHECKING
import os
import tempfile
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

if TYPE_CHECKING:
	from watchdog.observers import BaseObserverSubclassCallable
	from watchdog.events import FileSystemEvent

TMP_DIR = os.path.join(tempfile.gettempdir(), "basilisk")


class FileWatcher(FileSystemEventHandler):
	def __init__(self, callback: Callable):
		self.callback = callback

	def on_modified(self, event: FileSystemEvent):
		if event.src_path == os.path.join(TMP_DIR, "focus_file"):
			self.callback()


def send_focus_signal():
	with open(os.path.join(TMP_DIR, "focus_file"), 'w') as f:
		f.write(str(time.time()))


def watch_focus_signal(callback: Callable) -> BaseObserverSubclassCallable:
	event_handler = FileWatcher(callback)
	observer = Observer()
	observer.schedule(event_handler, TMP_DIR, recursive=False)
	observer.start()
	return observer
