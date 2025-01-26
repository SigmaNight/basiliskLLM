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
		"""Initialize the FileWatcher with dynamic callback methods.

		Parameters:
		    callbacks (dict[str, Callable]): A dictionary mapping method names to callback functions.
		        Each key-value pair will be dynamically set as an attribute of the FileWatcher instance.

		This method allows flexible runtime configuration of event handling methods by dynamically
		adding callback functions as instance methods based on the provided dictionary.
		"""
		for name, callback in callbacks.items():
			setattr(self, name, callback)

	def on_modified(self, event: FileSystemEvent):
		"""Handle file modification events for specific files.

		This method checks the source path of the file system event and delegates
		the handling to appropriate methods based on the file type.

		Parameters:
		    event (FileSystemEvent): The file system event containing modification details.

		Behavior:
		    - If the event source is the focus file, calls `on_focus_file`
		    - If the event source is the open BSKC file, calls `on_open_bskc_file`
		    - For any other file, logs an error message

		Raises:
		    No explicit exceptions are raised, but logs an error for unrecognized events.
		"""
		if event.src_path == FOCUS_FILE:
			self.on_focus_file(event)
		elif event.src_path == OPEN_BSKC_FILE:
			self.on_open_bskc_file(event)
		else:
			logger.error(f"unknown event: {event}")

	def on_focus_file(self, event: FileSystemEvent):
		"""Handle modifications to the focus file with controlled event triggering.

		This method is called when the focus file is modified. It prevents rapid successive
		event triggers by enforcing a minimum 1-second interval between processing events
		for the same file path.

		Parameters:
		    event (FileSystemEvent): The file system event representing the file modification.

		Notes:
		    - Logs a debug message when the focus file is modified
		    - Uses a time-based throttling mechanism to prevent excessive event processing
		    - Utilizes CallAfter to schedule the send_focus method in the main thread
		"""
		logger.debug("Focus file modified")
		if event.src_path not in self.last_modified:
			self.last_modified[event.src_path] = 0
		elif time.time() - self.last_modified[event.src_path] < 1:
			logger.debug("Ignoring focus file modification")
			return
		self.last_modified[event.src_path] = time.time()
		logger.debug("Sending focus")
		CallAfter(self.send_focus)

	def on_open_bskc_file(self, event: FileSystemEvent):
		"""Handle modifications to the open basilisk conversation file.

		Logs a debug message when the bskc file is modified, reads its contents,
		and schedules the `open_bskc` method to be called in the main thread with the file contents.

		Parameters:
		    event (FileSystemEvent): The file system event triggered by the file modification.

		Side Effects:
		    - Logs a debug message about file modification
		    - Reads the contents of the modified file
		    - Schedules `open_bskc` method to be called with file contents using CallAfter
		"""
		logger.debug("Open bskc file modified")
		with open(event.src_path, 'r') as f:
			logger.debug("Opening basilisk conversation")
			CallAfter(self.open_bskc, f.read())


def init_file_watcher(**callbacks) -> BaseObserverSubclassCallable:
	"""Initialize a file watcher to monitor changes in a temporary directory.

	This function sets up a file system observer to track modifications in the specified temporary directory
	without recursively monitoring subdirectories.

	Parameters:
	    **callbacks (dict[str, Callable]): A dictionary of callback functions to handle specific file events.
	        Each key represents a specific file type or event, and the corresponding value is a callable
	        that will be invoked when that event occurs.

	Returns:
	    BaseObserverSubclassCallable: An active file system observer that can be used to monitor file changes.

	Example:
	    observer = init_file_watcher(
	        focus_file=handle_focus_change,
	        open_bskc_file=process_bskc_file
	    )
	"""
	event_handler = FileWatcher(callbacks)
	observer = Observer()
	observer.schedule(event_handler, TMP_DIR, recursive=False)
	logger.debug("Starting file watcher")
	observer.start()

	return observer
