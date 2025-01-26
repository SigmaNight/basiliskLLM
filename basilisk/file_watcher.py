from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Callable

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from wx import CallAfter

if TYPE_CHECKING:
	from watchdog.events import FileSystemEvent
	from watchdog.observers import BaseObserverSubclassCallable
from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE, TMP_DIR

logger = logging.getLogger(__name__)


class FileWatcher(FileSystemEventHandler):
	last_modified = {}

	def __init__(self, callbacks: dict[str, Callable]):
		for name, callback in callbacks.items():
			setattr(self, name, callback)

	def on_modified(self, event: FileSystemEvent):
		if event.src_path == FOCUS_FILE:
			logger.debug("Focus file modified")
			if event.src_path not in self.last_modified:
				self.last_modified[event.src_path] = 0
			elif time.time() - self.last_modified[event.src_path] > 1:
				self.last_modified[event.src_path] = time.time()
				logger.debug("Sending focus")
				CallAfter(self.send_focus)
		elif event.src_path == OPEN_BSKC_FILE:
			logger.debug("Open bskc file modified")
			with open(event.src_path, 'r') as f:
				logger.debug("Opening basilisk conversation")
				CallAfter(self.open_bskc, f.read())


def init_file_watcher(**callbacks) -> BaseObserverSubclassCallable:
	event_handler = FileWatcher(callbacks)
	observer = Observer()
	observer.schedule(event_handler, TMP_DIR, recursive=False)
	logger.debug("Starting file watcher")
	observer.start()

	return observer
