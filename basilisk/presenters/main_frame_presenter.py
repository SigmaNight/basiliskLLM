"""Presenter for main frame orchestration logic.

Coordinates conversation lifecycle (create, open, save, close),
startup/shutdown sequencing, screen capture, and account/settings
management. Delegates all pure-UI operations back to the MainFrame view.
"""

from __future__ import annotations

import datetime
import logging
import os
import sys
import tempfile
from typing import TYPE_CHECKING, Optional

import wx

import basilisk.config as config
from basilisk.conversation import ImageFile
from basilisk.screen_capture_thread import CaptureMode, ScreenCaptureThread

if TYPE_CHECKING:
	from basilisk.views.main_frame import MainFrame

log = logging.getLogger(__name__)


class MainFramePresenter:
	"""Orchestrates conversation lifecycle and application-level logic.

	The presenter owns the conversation ID counter and coordinates
	startup, shutdown, save, and open flows. It reads view state via
	``self.view`` and delegates pure-UI operations back to the view.

	Attributes:
		view: The MainFrame view this presenter drives.
		last_conversation_id: Incrementing counter for default titles.
	"""

	def __init__(self, view: MainFrame) -> None:
		"""Initialize the main frame presenter.

		Args:
			view: The MainFrame view instance.
		"""
		self.view = view
		self.last_conversation_id: int = 0

	# -- Title counter --

	def get_default_conv_title(self) -> str:
		"""Generate a default title for a new conversation.

		Increments an internal counter and returns a localized title.

		Returns:
			A localized conversation title like "Conversation 1".
		"""
		self.last_conversation_id += 1
		# Translators: A default title for a conversation
		return _("Conversation %d") % self.last_conversation_id

	# -- Startup / shutdown --

	def try_reopen_last_conversation(self) -> bool:
		"""Try to reopen the last active conversation from the database.

		Returns:
			True if the conversation was successfully reopened.
		"""
		from basilisk.views.conversation_tab import ConversationTab

		if not self.view.conf.conversation.reopen_last_conversation:
			return False
		conv_id = self.view.conf.conversation.last_active_conversation_id
		if conv_id is None:
			return False
		try:
			tab = ConversationTab.open_from_db(
				self.view.notebook, conv_id, self.get_default_conv_title()
			)
			self.view.add_conversation_tab(tab)
			return True
		except Exception:
			log.warning(
				"Failed to reopen last conversation %d", conv_id, exc_info=True
			)
			self.view.conf.conversation.last_active_conversation_id = None
			self.view.conf.save()
			return False

	def flush_and_save_on_quit(self):
		"""Clean up all tabs and save the last active conversation ID.

		Called by MainFrame.on_quit() before wx cleanup. Stops all
		active completion handlers, flushes pending drafts, and cleans
		up OCR and recording resources.
		"""
		for index, tab in enumerate(self.view.tabs_panels):
			try:
				tab.cleanup_resources()
			except Exception as e:
				log.error(
					"Error cleaning up tab %d: %s", index, e, exc_info=True
				)
		if self.view.conf.conversation.reopen_last_conversation:
			current = self.view.current_tab
			if current and current.db_conv_id is not None:
				self.view.conf.conversation.last_active_conversation_id = (
					current.db_conv_id
				)
			else:
				self.view.conf.conversation.last_active_conversation_id = None
			self.view.conf.save()

	# -- Conversation lifecycle --

	def on_new_default_conversation(self):
		"""Create a new conversation with the default profile."""
		self.handle_no_account_configured()
		profile = config.conversation_profiles().default_profile
		if profile:
			log.info(
				"Creating a new conversation with default profile (%s)",
				profile.name,
			)
		self.new_conversation(profile)

	def on_new_private_conversation(self):
		"""Create a new private conversation with the default profile."""
		self.handle_no_account_configured()
		profile = config.conversation_profiles().default_profile
		if profile:
			log.info(
				"Creating a new private conversation with default profile (%s)",
				profile.name,
			)
		self.new_conversation(profile, private=True)

	def new_conversation(
		self, profile: config.ConversationProfile | None, private: bool = False
	):
		"""Create a new conversation tab with the specified profile.

		Args:
			profile: The conversation profile to use, or None for default.
			private: If True, mark the conversation as private.
		"""
		from basilisk.views.conversation_tab import ConversationTab

		new_tab = ConversationTab(
			self.view.notebook,
			title=self.get_default_conv_title(),
			profile=profile,
		)
		if private:
			new_tab.set_private(True)
		self.view.add_conversation_tab(new_tab)

	def open_conversation(self, file_path: str):
		"""Open a conversation from a file path.

		Args:
			file_path: The path to the conversation file.
		"""
		from basilisk.views.conversation_tab import ConversationTab

		try:
			new_tab = ConversationTab.open_conversation(
				self.view.notebook, file_path, self.get_default_conv_title()
			)
			if new_tab:
				self.view.add_conversation_tab(new_tab)
		except Exception as e:
			wx.MessageBox(
				# Translators: An error message when a conversation file cannot be opened
				_("Failed to open conversation file: '%s', error: %s")
				% (file_path, e),
				style=wx.OK | wx.ICON_ERROR,
			)
			log.error(
				"Failed to open conversation file: %s, error: %s",
				file_path,
				e,
				exc_info=e,
			)

	def open_from_db(self, conv_id: int):
		"""Open a conversation from the database.

		Args:
			conv_id: The database conversation ID.
		"""
		from basilisk.views.conversation_tab import ConversationTab

		try:
			tab = ConversationTab.open_from_db(
				self.view.notebook, conv_id, self.get_default_conv_title()
			)
			self.view.add_conversation_tab(tab)
		except Exception as e:
			log.error(
				"Failed to open conversation from database: %s",
				e,
				exc_info=True,
			)
			wx.MessageBox(
				_("Failed to open conversation: %s") % str(e),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)

	def close_conversation(self):
		"""Close the currently selected conversation tab.

		If no tabs remain, creates a new default conversation.
		"""
		current_tab_index = self.view.notebook.GetSelection()
		if current_tab_index == wx.NOT_FOUND:
			return
		tab = self.view.tabs_panels[current_tab_index]
		try:
			tab.cleanup_resources()
		except Exception as e:
			log.error(
				"Error cleaning up tab before close: %s", e, exc_info=True
			)
		self.view.notebook.DeletePage(current_tab_index)
		self.view.tabs_panels.pop(current_tab_index)
		current_tab_count = self.view.notebook.GetPageCount()
		if current_tab_count == 0:
			self.on_new_default_conversation()
		else:
			self.view.notebook.SetSelection(current_tab_count - 1)
			self.view.refresh_frame_title()

	# -- Save flow --

	def save_current_conversation(self):
		"""Save the current conversation to its associated file path.

		If no file path is set, triggers save-as via the view.
		"""
		current_tab = self.view.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if not current_tab.bskc_path:
			self.view.on_save_as_conversation(None)
			return
		current_tab.save_conversation(current_tab.bskc_path)

	def save_conversation_as(self, file_path: str) -> bool:
		"""Save the current conversation to a specified file path.

		Args:
			file_path: The target file path.

		Returns:
			True if saved successfully.
		"""
		current_tab = self.view.current_tab
		if not current_tab:
			return False
		success = current_tab.save_conversation(file_path)
		if success:
			current_tab.bskc_path = file_path
		return success

	# -- Name conversation --

	def name_conversation(self, auto: bool = False):
		"""Name the current conversation, either manually or automatically.

		Shows a dialog for the user to enter or confirm the title.

		Args:
			auto: If True, generates a title automatically before showing the dialog.
		"""
		from basilisk.views.name_conversation_dialog import (
			NameConversationDialog,
		)

		current_tab = self.view.current_tab
		if not current_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		title = current_tab.conversation.title or current_tab.title
		if auto:
			generated = current_tab.generate_conversation_title()
			if not generated:
				return
			title = generated.strip().replace("\n", " ")
		dialog = NameConversationDialog(
			self.view,
			title=title,
			generate_fn=current_tab.generate_conversation_title,
		)
		if dialog.ShowModal() != wx.ID_OK or not dialog.get_name():
			dialog.Destroy()
			return
		current_tab.conversation.title = dialog.get_name()
		current_tab.update_db_title(dialog.get_name())
		self.view.refresh_tab_title(True)
		dialog.Destroy()

	# -- Screen capture --

	def screen_capture(
		self,
		capture_mode: CaptureMode,
		screen_coordinates: Optional[tuple[int, int, int, int]] = None,
		name: str = "",
	):
		"""Capture a screenshot and add it to the current conversation.

		Args:
			capture_mode: The type of screen capture to perform.
			screen_coordinates: Coordinates for partial capture.
			name: Custom name for the captured image.
		"""
		log.debug("Capturing %s screen", capture_mode.value)
		conv_tab = self.view.current_tab
		if not conv_tab:
			wx.MessageBox(
				_("No conversation selected"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if capture_mode == CaptureMode.PARTIAL and not screen_coordinates:
			wx.MessageBox(
				_("No screen coordinates provided"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		now = datetime.datetime.now()
		capture_name = f"capture_{now.isoformat(timespec='seconds')}.png"
		capture_path = (
			conv_tab.conv_storage_path / f"attachments/{capture_name}"
		)
		name = name or capture_name
		log.debug("Capture file URL: %s", capture_path)
		thread = ScreenCaptureThread(
			self.view,
			capture_path,
			capture_mode,
			name=name,
			screen_coordinates=screen_coordinates,
		)
		thread.start()

	def post_screen_capture(self, image_file: ImageFile | str):
		"""Handle a completed screen capture.

		Args:
			image_file: The captured image file or path.
		"""
		log.debug("Screen capture received")
		self.view.current_tab.prompt_panel.add_attachments([image_file])
		if not self.view.IsShown():
			self.view.Show()
			self.view.Restore()
			self.view.Layout()
		self.view.Raise()

	# -- Account / settings management --

	def handle_no_account_configured(self):
		"""Check if any accounts are configured and prompt the user if not."""
		if config.accounts():
			return
		first_account_msg = wx.MessageBox(
			# translators: This message is displayed when no account is configured and the user tries to use the conversation tab.
			_(
				"Please add an account first. Do you want to add an account now?"
			),
			# translators: This is a title for the message box
			_("No account configured"),
			wx.YES_NO | wx.ICON_QUESTION,
		)
		if first_account_msg == wx.YES:
			self.manage_accounts()

	def manage_accounts(self):
		"""Open the account management dialog."""
		from basilisk.views.account_dialog import AccountDialog

		log.debug("Opening account management dialog")
		account_dialog = AccountDialog(self.view, _("Manage accounts"))
		if account_dialog.ShowModal() == wx.ID_OK:
			if not config.accounts():
				self.handle_no_account_configured()
			else:
				self.view.refresh_tabs()
		account_dialog.Destroy()

	def manage_preferences(self):
		"""Open the preferences dialog."""
		from basilisk.views.preferences_dialog import PreferencesDialog

		log.debug("Opening preferences dialog")
		preferences_dialog = PreferencesDialog(self.view, title=_("Settings"))
		if preferences_dialog.ShowModal() == wx.ID_OK:
			self.view.refresh_tabs()
		preferences_dialog.Destroy()

	def manage_conversation_profiles(self):
		"""Open the conversation profile management dialog.

		Returns:
			True if profiles were changed and the menu needs rebuilding.
		"""
		from basilisk.views.conversation_profile_dialog import (
			ConversationProfileDialog,
		)

		profile_dialog = ConversationProfileDialog(
			self.view, _("Manage conversation profiles")
		)
		profile_dialog.ShowModal()
		menu_update = profile_dialog.menu_update
		profile_dialog.Destroy()
		return menu_update

	def apply_conversation_profile(self, profile: config.ConversationProfile):
		"""Apply a conversation profile to the current tab.

		Args:
			profile: The profile to apply.
		"""
		log.info("Applying profile: %s to conversation", profile.name)
		self.view.current_tab.apply_profile(profile)

	def toggle_privacy(self):
		"""Toggle the private flag on the current conversation tab."""
		tab = self.view.current_tab
		if not tab:
			return
		tab.set_private(not tab.private)

	# -- NVDA addon --

	def install_nvda_addon(self):
		"""Install the NVDA addon for BasiliskLLM.

		Creates a temporary .nvda-addon file from the resource folder
		and opens it with the system default handler.
		"""
		import zipfile

		from basilisk import global_vars

		res_nvda_addon_path = os.path.join(
			global_vars.resource_path, "connectors", "nvda"
		)
		try:
			if not os.path.isdir(res_nvda_addon_path):
				raise ValueError(
					f"NVDA addon folder not found: {res_nvda_addon_path}"
				)
			tmp_nvda_addon_path = os.path.join(
				tempfile.gettempdir(), "basiliskllm.nvda-addon"
			)
			log.debug("Creating NVDA addon: %s", tmp_nvda_addon_path)
			with zipfile.ZipFile(
				tmp_nvda_addon_path, "w", zipfile.ZIP_DEFLATED
			) as zipf:
				for root, _, files in os.walk(res_nvda_addon_path):
					for file in files:
						file_path = os.path.join(root, file)
						arcname = os.path.relpath(
							file_path, start=res_nvda_addon_path
						)
						zipf.write(file_path, arcname)
			log.debug("NVDA addon created")
			if sys.platform == "win32":
				os.startfile(tmp_nvda_addon_path)
		except Exception as e:
			log.error("Failed to create NVDA addon: %s", e)
			wx.MessageBox(
				_("Failed to create NVDA addon"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
