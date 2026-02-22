"""Implements OCR (Optical Character Recognition) functionality for the BasiliskLLM application.

This module provides the OCRHandler class, which encapsulates all OCR-related operations
including UI interactions, processing attachments through provider OCR capabilities,
and managing OCR task progress.
"""

from __future__ import annotations

import logging
from multiprocessing import Queue, Value
from typing import TYPE_CHECKING, Any, Optional

import wx

import basilisk.config as config
import basilisk.global_vars as global_vars
from basilisk.process_helper import run_task
from basilisk.provider_capability import ProviderCapability

from .enhanced_error_dialog import show_enhanced_error_dialog
from .progress_bar_dialog import ProgressBarDialog

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

	from .conversation_tab import ConversationTab

log = logging.getLogger(__name__)

# Time between progress checks in milliseconds
CHECK_TASK_DELAY = 100


class OCRHandler:
	"""Handles OCR operations for the BasiliskLLM application.

	This class provides functionality for performing OCR on attachments,
	managing OCR processes, and displaying progress and results to users.
	"""

	def __init__(self, parent: ConversationTab):
		"""Initialize the OCR handler.

		Args:
			parent: The parent conversation tab that owns this handler.
		"""
		self.conf = config.conf()
		self.parent = parent
		self.process: Optional[Any] = None  # multiprocessing.Process
		self.ocr_button: Optional[wx.Button] = None
		self._ocr_cleanup_done = False

	def create_ocr_widget(self, parent: wx.Window) -> wx.Button:
		"""Create and configure the OCR button widget.

		Args:
			parent: The parent window for the button.

		Returns:
			The configured OCR button.
		"""
		self.ocr_button = wx.Button(
			parent,
			# Translators: This is a label for perform OCR button in the conversation tab
			label=_("Perform OCR on Attachments"),
		)
		self.ocr_button.Bind(wx.EVT_BUTTON, self.on_ocr)
		return self.ocr_button

	def _handle_ocr_message(
		self, message_type: str, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Handle a message from the OCR result queue.

		Args:
			message_type: The type of message received
			data: The message data
			dialog: The progress dialog
		"""
		try:
			if message_type == "message":
				self._handle_ocr_info_message(data, dialog)
			elif message_type == "progress":
				self._handle_ocr_progress_message(data, dialog)
			elif message_type in ("result", "error"):
				self._handle_ocr_completion_message(message_type, data, dialog)
			else:
				log.warning(
					"Unknown message type in result queue: %s", message_type
				)
		except Exception as e:
			log.error("Error handling message: %s", e, exc_info=True)
			show_enhanced_error_dialog(
				parent=self.parent,
				message=_(
					"An error occurred while processing OCR results. Details: \n%s"
				)
				% e,
				title=_("OCR Error"),
				is_completion_error=False,
			)

	def _handle_ocr_info_message(
		self, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Handle an information message from the OCR process.

		Args:
			data: The message data
			dialog: The progress dialog
		"""
		if isinstance(data, str) and data:
			dialog.update_message(data)

	def _handle_ocr_progress_message(
		self, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Handle a progress update message from the OCR process.

		Args:
			data: The progress value
			dialog: The progress dialog
		"""
		if isinstance(data, int):
			dialog.update_progress_bar(data)

	def _handle_ocr_completion_message(
		self, message_type: str, data: Any, dialog: ProgressBarDialog
	) -> None:
		"""Handle a completion (result or error) message from the OCR process.

		Args:
			message_type: The type of message ("result" or "error")
			data: The message data
			dialog: The progress dialog
		"""
		if not dialog:
			return

		dialog_destroyed = False
		try:
			if dialog.IsShown():
				dialog.Destroy()
				dialog_destroyed = True
		except RuntimeError:
			log.debug("OCR dialog already destroyed", exc_info=True)
			dialog_destroyed = True

		if dialog_destroyed:
			self._ocr_cleanup_done = True

		if (
			not hasattr(self.parent, "_is_destroying")
			or self.parent._is_destroying
			or not hasattr(self.parent, "_is_widget_valid")
			or not self.parent._is_widget_valid()
		):
			log.debug(
				"Skipping OCR completion handling: parent tab is being destroyed"
			)
			return

		if hasattr(self, "ocr_button") and self.ocr_button:
			self.ocr_button.Enable()

		# Handle based on message type
		if message_type == "result":
			self._display_ocr_result(data)
		else:  # error case
			show_enhanced_error_dialog(
				parent=self.parent,
				message=str(data),
				title=_("OCR Error"),
				is_completion_error=False,
			)

	def _display_ocr_result(self, data: Any) -> None:
		"""Display the result of OCR processing.

		Args:
			data: The OCR result data
		"""
		if isinstance(data, list) and data:
			msg = (
				_("OCR completed successfully. Text extracted to:")
				+ "\n"
				+ "\n".join(data)
				+ "\n\n"
				+ _("Do you want to open the files?")
			)
			if (
				wx.MessageBox(msg, _("Result"), wx.YES_NO | wx.ICON_INFORMATION)
				== wx.YES
			):
				for file_path in data:
					wx.LaunchDefaultApplication(file_path)
		elif isinstance(data, str) and data:
			wx.MessageBox(data, _("Result"), wx.OK | wx.ICON_INFORMATION)
		else:
			log.warning(
				"Unexpected OCR result data type or empty result: %s - %s",
				type(data),
				data,
			)
			wx.MessageBox(
				_("OCR completed, but no text was extracted."),
				_("Result"),
				wx.OK | wx.ICON_INFORMATION,
			)

	def _process_ocr_queue(
		self, result_queue: Queue, dialog: ProgressBarDialog
	) -> None:
		"""Process all pending messages in the OCR result queue.

		Args:
			result_queue: The queue containing OCR process results
			dialog: The progress dialog to update
		"""
		try:
			while not result_queue.empty():
				message_type, data = result_queue.get(block=False)
				self._handle_ocr_message(message_type, data, dialog)
		except Exception as e:
			log.error(
				"Error processing queue messages: %s", str(e), exc_info=True
			)

	def _terminate_ocr_process_if_needed(
		self, dialog: ProgressBarDialog
	) -> None:
		"""Terminate OCR process if cancellation was requested.

		Args:
			dialog: The progress dialog containing cancel flag
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

	def _destroy_ocr_dialog(self, dialog: ProgressBarDialog) -> None:
		"""Safely destroy the OCR progress dialog.

		Args:
			dialog: The progress dialog to destroy
		"""
		try:
			if dialog and dialog.IsShown():
				dialog.Destroy()
		except RuntimeError:
			log.debug("OCR dialog already destroyed", exc_info=True)
		except Exception as e:
			log.error("Error destroying dialog: %s", e, exc_info=True)

	def _enable_ocr_button(self) -> None:
		"""Enable the OCR button if parent tab is still valid."""
		if (
			hasattr(self.parent, "_is_widget_valid")
			and self.parent._is_widget_valid("ocr_button")
			and hasattr(self, "ocr_button")
			and self.ocr_button
		):
			self.ocr_button.Enable()
		elif (
			hasattr(self.parent, "_is_destroying")
			and self.parent._is_destroying
		):
			log.debug(
				"Skipping OCR button enable: parent tab is being destroyed"
			)

	def _cleanup_ocr_process(self, dialog: ProgressBarDialog) -> None:
		"""Clean up OCR process resources when task completes or is canceled.

		Args:
			dialog: The progress dialog to manage
		"""
		if self._ocr_cleanup_done:
			self._terminate_ocr_process_if_needed(dialog)
			self.process = None
			self._ocr_cleanup_done = False
			return

		self._terminate_ocr_process_if_needed(dialog)
		self._destroy_ocr_dialog(dialog)
		self._enable_ocr_button()

		self._ocr_cleanup_done = True
		self.process = None

	def check_task_progress(
		self, dialog: ProgressBarDialog, result_queue: Queue, cancel_flag
	):
		"""Check the progress of the OCR task.

		Args:
			dialog: The progress dialog
			result_queue: The queue to store the task result
			cancel_flag: The flag to indicate if the task should be cancelled
		"""
		# Process all pending messages in the queue
		self._process_ocr_queue(result_queue, dialog)

		# Check if process is still running
		if (
			not self.process
			or not self.process.is_alive()
			or dialog.cancel_flag.value
		):
			self._cleanup_ocr_process(dialog)
		else:
			# Continue checking progress
			wx.CallLater(
				CHECK_TASK_DELAY,
				self.check_task_progress,
				dialog,
				result_queue,
				cancel_flag,
			)

	def on_ocr(self, event: wx.CommandEvent):
		"""Handle the OCR button click event.

		Args:
			event: The button click event
		"""
		engine: BaseEngine = self.parent.current_engine
		attachment_files = self.parent.prompt_panel.attachment_files

		if ProviderCapability.OCR not in engine.capabilities:
			wx.MessageBox(
				# Translators: This message is displayed when the current provider does not support OCR.
				_("The selected provider does not support OCR."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		if not attachment_files:
			wx.MessageBox(
				# Translators: This message is displayed when there are no attachments to perform OCR on.
				_("No attachments to perform OCR on."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		if not self.parent.prompt_panel.check_attachments_valid():
			return

		client = engine.client
		if not client:
			wx.MessageBox(
				# Translators: This message is displayed when the current provider does not have a client.
				_("The selected provider does not have a client."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		self.ocr_button.Disable()

		self._ocr_cleanup_done = False

		cancel_flag = Value("i", 0)
		result_queue = Queue()

		progress_bar_dialog = ProgressBarDialog(
			self.parent,
			title=_("Performing OCR..."),
			message=_("Performing OCR on attachments..."),
			cancel_flag=cancel_flag,
		)
		progress_bar_dialog.Show()

		current_account = self.parent.current_account
		log_level = (
			global_vars.args.log_level or self.conf.general.log_level.name
		)
		kwargs = {
			"api_key": current_account.api_key.get_secret_value(),
			"base_url": current_account.custom_base_url
			or current_account.provider.base_url,
			"attachments": attachment_files,
			"log_level": log_level,
		}

		self.process = run_task(
			engine.handle_ocr, result_queue, cancel_flag, **kwargs
		)

		log.debug("OCR process started: %s", self.process.pid)

		wx.CallLater(
			CHECK_TASK_DELAY,
			self.check_task_progress,
			progress_bar_dialog,
			result_queue,
			cancel_flag,
		)
