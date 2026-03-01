"""OCR view wrapper — thin adapter between OCRPresenter and the GUI.

OCRHandler implements the IOCRView interface expected by OCRPresenter.
All orchestration logic lives in basilisk/presenters/ocr_presenter.py.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

import wx

import basilisk.config as config
import basilisk.global_vars as global_vars
from basilisk.presenters.ocr_presenter import OCRPresenter

from .enhanced_error_dialog import show_enhanced_error_dialog
from .progress_bar_dialog import ProgressBarDialog
from .view_mixins import ErrorDisplayMixin

if TYPE_CHECKING:
	from .conversation_tab import ConversationTab

log = logging.getLogger(__name__)


class OCRHandler(ErrorDisplayMixin):
	"""Thin view wrapper for OCR operations.

	Creates OCRPresenter and implements the IOCRView interface so that
	the presenter can drive all UI without depending on wx widgets.
	"""

	def __init__(self, parent: ConversationTab) -> None:
		"""Initialise the handler and create the backing presenter.

		Args:
			parent: The ConversationTab that owns this handler.
		"""
		self.conf = config.conf()
		self.parent = parent
		self.ocr_button: Optional[wx.Button] = None

		self._presenter = OCRPresenter(
			view=self,
			get_engine=lambda: self.parent.current_engine,
			get_attachments=lambda: self.parent.prompt_panel.attachment_files,
			get_account=lambda: self.parent.current_account,
			get_log_level=lambda: (
				global_vars.args.log_level or self.conf.general.log_level.name
			),
			check_attachments_valid=lambda: (
				self.parent.prompt_panel.check_attachments_valid()
			),
		)

	def create_ocr_widget(self, parent: wx.Window) -> wx.Button:
		"""Create and configure the OCR button widget.

		Args:
			parent: The parent window for the button.

		Returns:
			The configured OCR button.
		"""
		self.ocr_button = wx.Button(
			parent,
			# Translators: Label for perform OCR button in the conversation tab
			label=_("Perform OCR on Attachments"),
		)
		self.ocr_button.Bind(wx.EVT_BUTTON, self._presenter.on_ocr)
		return self.ocr_button

	# ------------------------------------------------------------------
	# IOCRView interface — called by OCRPresenter
	# ------------------------------------------------------------------

	def set_ocr_button_enabled(self, enabled: bool) -> None:
		"""Enable or disable the OCR button.

		Args:
			enabled: True to enable, False to disable.
		"""
		if self.ocr_button is not None:
			self.ocr_button.Enable(enabled)

	def create_progress_dialog(
		self, title: str, msg: str, cancel_flag
	) -> ProgressBarDialog:
		"""Create, show, and return a progress dialog.

		Args:
			title: Dialog title.
			msg: Initial status message.
			cancel_flag: Shared multiprocessing Value used by the cancel
				button.

		Returns:
			The shown ProgressBarDialog.
		"""
		dialog = ProgressBarDialog(
			self.parent, title=title, message=msg, cancel_flag=cancel_flag
		)
		dialog.Show()
		return dialog

	def destroy_progress_dialog(self, dialog: ProgressBarDialog) -> None:
		"""Safely destroy the progress dialog if it is still shown.

		Args:
			dialog: The dialog to destroy.
		"""
		try:
			if dialog and dialog.IsShown():
				dialog.Destroy()
		except Exception as e:
			log.error("Error destroying dialog: %s", e, exc_info=True)

	def show_result(self, data: Any) -> None:
		"""Display the OCR result to the user.

		Args:
			data: A list of output file paths, a plain string message,
				or any other value (shown as a generic completion notice).
		"""
		if isinstance(data, list) and data:
			# Translators: Shown when OCR succeeds; %s is replaced with the
			# output file paths, one per line
			msg = _(
				"OCR completed successfully. Text extracted to:\n%s\n\nDo you want to open the files?"
			) % "\n".join(data)
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
			# Translators: Shown when OCR completes but extracted no text
			wx.MessageBox(
				_("OCR completed, but no text was extracted."),
				_("Result"),
				wx.OK | wx.ICON_INFORMATION,
			)

	def cleanup(self) -> None:
		"""Clean up OCR resources by delegating to the presenter."""
		self._presenter.cleanup()

	def show_enhanced_error(
		self, message: str, title: str = None, is_completion_error: bool = False
	) -> None:
		"""Display the enhanced error dialog using the parent tab as window.

		Overrides ``ErrorDisplayMixin.show_enhanced_error`` to pass
		``self.parent`` (the owning ``ConversationTab``) as the wx parent
		window, since ``OCRHandler`` itself is not a ``wx.Window``.

		Args:
			message: The error message.
			title: Dialog title.
			is_completion_error: Passed through to the dialog.
		"""
		show_enhanced_error_dialog(
			self.parent, message, title, is_completion_error
		)

	def show_error(self, message: str, title: str = None) -> None:
		"""Display an enhanced error dialog for OCR errors.

		Overrides ``ErrorDisplayMixin.show_error`` to route all simple
		errors through the enhanced dialog.

		Args:
			message: The error message.
			title: The dialog title.
		"""
		self.show_enhanced_error(message, title)
