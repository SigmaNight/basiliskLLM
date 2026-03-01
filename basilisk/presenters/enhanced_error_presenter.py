"""Presenter for enhanced error dialog logic.

Handles URL detection, clipboard operations, and browser opening,
keeping business logic out of the EnhancedErrorDialog view.
"""

from __future__ import annotations

import logging
import re
import webbrowser

import wx

log = logging.getLogger(__name__)


class EnhancedErrorPresenter:
	"""Presenter for the EnhancedErrorDialog view.

	Handles URL detection, clipboard operations, and browser opening.

	Attributes:
		view: The EnhancedErrorDialog view instance.
	"""

	URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)

	def __init__(self, view) -> None:
		"""Initialize the presenter.

		Args:
			view: The EnhancedErrorDialog view instance.
		"""
		self.view = view

	@staticmethod
	def find_urls_in_text(text: str) -> list[str]:
		"""Find all URLs in the given text.

		Args:
			text: The text to search for URLs.

		Returns:
			A list of URLs found in the text.
		"""
		return EnhancedErrorPresenter.URL_PATTERN.findall(text)

	def copy_to_clipboard(self, message: str) -> None:
		"""Copy the message to the clipboard.

		Updates view button state to reflect success or failure.

		Args:
			message: The message text to copy.
		"""
		try:
			opened = wx.TheClipboard.Open()
			try:
				if opened:
					if not wx.TheClipboard.SetData(wx.TextDataObject(message)):
						raise RuntimeError("SetData returned False")
					self.view.set_copy_state(_("Copied!"), False)
				else:
					log.warning("Failed to access clipboard")
					self.view.bell()
					self.view.set_copy_state(_("Copy failed"), False)
			finally:
				if opened:
					wx.TheClipboard.Close()
		except Exception as e:
			log.error("Failed to copy to clipboard: %s", e)
			self.view.bell()
			self.view.set_copy_state(_("Copy failed: %s") % e, False)

	def open_url(self, url: str) -> None:
		"""Open a URL in the default browser.

		Updates view button state if opening fails.

		Args:
			url: The URL to open.
		"""
		log.info("Opening URL in browser: %s", url)
		try:
			if not webbrowser.open(url):
				self.fail_open_browser(url)
		except Exception:
			self.fail_open_browser(url, True)

	def fail_open_browser(self, url: str, exc_info: bool = False):
		"""Display user info when open browser fail.

		Args:
			url: The URL to open
			exc_info: show exception traceback
		"""
		log.error("Failed to open URL %s", url, exc_info=exc_info)
		self.view.bell()
		self.view.set_open_url_state(_("Open failed"))
