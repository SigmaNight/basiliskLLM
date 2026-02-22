"""Presenter for OCR operations.

Orchestrates multiprocessing OCR task lifecycle, progress polling, and
result/error handling. Delegates all UI to the IOCRView interface.
"""

from __future__ import annotations

import logging
from multiprocessing import Queue, Value
from typing import TYPE_CHECKING, Any, Callable, Optional

from basilisk.process_helper import run_task
from basilisk.provider_capability import ProviderCapability

if TYPE_CHECKING:
	from basilisk.views.progress_bar_dialog import ProgressBarDialog

log = logging.getLogger(__name__)

# Time between progress checks in milliseconds
CHECK_TASK_DELAY = 100


class OCRPresenter:
	"""Manages OCR process lifecycle and delegates UI to the view.

	Owns the subprocess, result queue, and cancel flag. All UI
	interactions (progress dialog, error/result display, button state)
	are routed through the IOCRView interface.

	Attributes:
		view: Object implementing the IOCRView interface.
		process: The running OCR subprocess, or None.
	"""

	def __init__(
		self,
		view,
		get_engine: Callable,
		get_attachments: Callable,
		get_account: Callable,
		get_log_level: Callable[[], str],
		check_attachments_valid: Callable[[], bool],
		scheduler=None,
	) -> None:
		"""Initialise the presenter.

		Args:
			view: Object implementing the IOCRView interface.
			get_engine: Callable returning the current provider engine.
			get_attachments: Callable returning the current attachment list.
			get_account: Callable returning the current account.
			get_log_level: Callable returning the effective log-level name.
			check_attachments_valid: Callable that validates attachments
				(may show its own error dialog) and returns True if valid.
			scheduler: Optional callable matching the wx.CallLater signature
				``scheduler(ms, func, *args)``; defaults to wx.CallLater.
		"""
		self.view = view
		self._get_engine = get_engine
		self._get_attachments = get_attachments
		self._get_account = get_account
		self._get_log_level = get_log_level
		self._check_attachments_valid = check_attachments_valid
		self._scheduler = scheduler
		self.process: Optional[Any] = None

	# ------------------------------------------------------------------
	# Internal helpers
	# ------------------------------------------------------------------

	def _call_later(self, ms: int, func, *args) -> None:
		"""Schedule *func* to be called after *ms* milliseconds.

		Args:
			ms: Delay in milliseconds.
			func: The callable to schedule.
			*args: Positional arguments forwarded to *func*.
		"""
		if self._scheduler is not None:
			self._scheduler(ms, func, *args)
		else:
			import wx

			wx.CallLater(ms, func, *args)

	# ------------------------------------------------------------------
	# Public interface
	# ------------------------------------------------------------------

	@property
	def is_running(self) -> bool:
		"""True if the OCR subprocess is alive.

		Returns:
			True if OCR is running.
		"""
		return self.process is not None and self.process.is_alive()

	def on_ocr(self, event=None) -> None:
		"""Handle the OCR button click.

		Validates prerequisites, disables the button, spawns the OCR
		subprocess, and schedules progress polling.

		Args:
			event: Optional wx event (ignored).
		"""
		engine = self._get_engine()
		attachment_files = self._get_attachments()

		if ProviderCapability.OCR not in engine.capabilities:
			self.view.show_error(
				# Translators: Error when provider does not support OCR
				_("The selected provider does not support OCR."),
				_("Error"),
			)
			return

		if not attachment_files:
			self.view.show_error(
				# Translators: Error when no attachments present for OCR
				_("No attachments to perform OCR on."),
				_("Error"),
			)
			return

		if not self._check_attachments_valid():
			return

		client = engine.client
		if not client:
			self.view.show_error(
				# Translators: Error when provider has no client
				_("The selected provider does not have a client."),
				_("Error"),
			)
			return

		self.view.set_ocr_button_enabled(False)

		cancel_flag = Value('i', 0)
		result_queue = Queue()

		progress_bar_dialog = self.view.create_progress_dialog(
			title=_("Performing OCR..."),
			msg=_("Performing OCR on attachments..."),
			cancel_flag=cancel_flag,
		)

		current_account = self._get_account()
		log_level = self._get_log_level()
		kwargs = {
			"api_key": current_account.api_key.get_secret_value(),
			"base_url": (
				current_account.custom_base_url
				or current_account.provider.base_url
			),
			"attachments": attachment_files,
			"log_level": log_level,
		}

		self.process = run_task(
			engine.handle_ocr, result_queue, cancel_flag, **kwargs
		)
		log.debug("OCR process started: %s", self.process.pid)

		self._call_later(
			CHECK_TASK_DELAY,
			self.check_task_progress,
			progress_bar_dialog,
			result_queue,
			cancel_flag,
		)

	def check_task_progress(
		self, dialog: ProgressBarDialog, result_queue: Queue, cancel_flag
	) -> None:
		"""Poll the OCR result queue and reschedule or clean up.

		Args:
			dialog: The progress dialog being displayed.
			result_queue: Queue receiving messages from the subprocess.
			cancel_flag: Shared flag set to 1 when user cancels.
		"""
		self._process_ocr_queue(result_queue, dialog)

		if (
			not self.process
			or not self.process.is_alive()
			or dialog.cancel_flag.value
		):
			self._cleanup_ocr_process(dialog)
		else:
			self._call_later(
				CHECK_TASK_DELAY,
				self.check_task_progress,
				dialog,
				result_queue,
				cancel_flag,
			)

	# ------------------------------------------------------------------
	# Private helpers
	# ------------------------------------------------------------------

	def _process_ocr_queue(
		self, result_queue: Queue, dialog: ProgressBarDialog
	) -> None:
		"""Drain all pending messages from the OCR result queue.

		Args:
			result_queue: The queue to drain.
			dialog: The progress dialog to update.
		"""
		try:
			while not result_queue.empty():
				message_type, data = result_queue.get(block=False)
				self._handle_ocr_message(message_type, data, dialog)
		except Exception as e:
			log.error(
				"Error processing queue messages: %s", str(e), exc_info=True
			)

	def _handle_ocr_message(
		self, message_type: str, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Dispatch a single OCR queue message.

		Args:
			message_type: One of "message", "progress", "result", "error".
			data: The message payload.
			dialog: The progress dialog to update.
		"""
		try:
			if message_type == "message":
				if isinstance(data, str) and data:
					dialog.update_message(data)
			elif message_type == "progress":
				if isinstance(data, int):
					dialog.update_progress_bar(data)
			elif message_type in ("result", "error"):
				self._handle_ocr_completion_message(message_type, data, dialog)
			else:
				log.warning(
					"Unknown message type in result queue: %s", message_type
				)
		except Exception as e:
			log.error("Error handling message: %s", e, exc_info=True)
			self.view.show_error(
				_(
					"An error occurred while processing OCR results."
					" Details: \n%s"
				)
				% e,
				_("OCR Error"),
			)

	def _handle_ocr_completion_message(
		self, message_type: str, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Handle a terminal result or error message from the subprocess.

		Args:
			message_type: "result" or "error".
			data: The result data or error description.
			dialog: The progress dialog to destroy.
		"""
		if not dialog:
			return

		self.view.destroy_progress_dialog(dialog)
		self.view.set_ocr_button_enabled(True)

		if message_type == "result":
			self.view.show_result(data)
		else:
			self.view.show_error(str(data), _("OCR Error"))

	def _cleanup_ocr_process(self, dialog: ProgressBarDialog) -> None:
		"""Terminate the subprocess (if cancelled) and update the view.

		Args:
			dialog: The progress dialog to destroy.
		"""
		if (
			self.process
			and dialog.cancel_flag.value
			and self.process.is_alive()
		):
			log.debug("Terminating OCR process due to user cancellation")
			try:
				self.process.terminate()
				self.process.join(timeout=1.0)
				if self.process.is_alive():
					log.warning("Process did not terminate, killing it")
					self.process.kill()
			except Exception as e:
				log.error("Error terminating process: %s", e, exc_info=True)

		self.view.destroy_progress_dialog(dialog)
		self.view.set_ocr_button_enabled(True)
		self.process = None
