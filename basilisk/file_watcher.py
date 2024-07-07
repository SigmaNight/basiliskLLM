from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING, Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

if TYPE_CHECKING:
	from watchdog.events import FileSystemEvent
	from watchdog.observers import BaseObserverSubclassCallable
from basilisk.consts import TMP_DIR


class FileWatcher(FileSystemEventHandler):
	last_modified = {}

	def __init__(self, callback: Callable):
		self.callback = callback

	def on_modified(self, event: FileSystemEvent):
		if event.src_path == os.path.join(TMP_DIR, "focus_file"):
			if event.src_path not in self.last_modified:
				self.last_modified[event.src_path] = 0
			elif time.time() - self.last_modified[event.src_path] > 1:
				self.last_modified[event.src_path] = time.time()
				self.callback()


def send_focus_signal():
	with open(os.path.join(TMP_DIR, "focus_file"), 'w') as f:
		f.write(str(time.time()))


def init_file_watcher(callback: Callable) -> BaseObserverSubclassCallable:
	event_handler = FileWatcher(callback)
	observer = Observer()
	observer.schedule(event_handler, TMP_DIR, recursive=False)
	observer.start()
	return observer
