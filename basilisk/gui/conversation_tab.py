"""Implements the conversation tab interface for the BasiliskLLM chat application.

This module provides the ConversationTab class, which handles all UI and logic for individual
chat conversations. It manages message display, user input, audio recording, image attachments,
and interaction with AI providers.

Features:
- Text input/output with markdown support
- attachment handling
- Audio recording and transcription
- Message navigation and searching
- Accessible output integration
- Streaming message support
"""

from __future__ import annotations

import datetime
import logging
import os
import re
import threading
import time
import weakref
from typing import TYPE_CHECKING, Any, Optional

import wx
from httpx import HTTPError
from more_itertools import first, locate
from upath import UPath

import basilisk.config as config
from basilisk import global_vars
from basilisk.accessible_output import clear_for_speak, get_accessible_output
from basilisk.conversation import (
	PROMPT_TITLE,
	URL_PATTERN,
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	NotImageError,
	get_mime_type,
	parse_supported_attachment_formats,
)
from basilisk.decorators import ensure_no_task_running
from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.sound_manager import play_sound, stop_sound

from .base_conversation import BaseConversation
from .html_view_window import show_html_view_window
from .read_only_message_dialog import ReadOnlyMessageDialog
from .search_dialog import SearchDialog, SearchDirection

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine
	from basilisk.recording_thread import RecordingThread

	from .main_frame import MainFrame

log = logging.getLogger(__name__)
accessible_output = get_accessible_output()
COMMON_PATTERN = r"[\n;:.?!)»\"\]}]"
RE_STREAM_BUFFER = re.compile(rf".*{COMMON_PATTERN}.*")
RE_SPEECH_STREAM_BUFFER = re.compile(rf"{COMMON_PATTERN}")


class ConversationTab(wx.Panel, BaseConversation):
	"""A tab panel that manages a single conversation with an AI assistant.

	This class provides a complete interface for interacting with AI models, including:
	- Text input and output
	- attachment handling
	- Audio recording and transcription
	- Message history navigation
	- Accessible output integration
	- Stream mode for real-time responses

	Attributes:
		ROLE_LABELS: Labels for message roles
		title: The title of the conversation
		conversation: The conversation object
		attachment_files: List of attachment files
		message_segment_manager: Message segment manager
	"""

	ROLE_LABELS = MessageRoleEnum.get_labels()

	@staticmethod
	def conv_storage_path() -> UPath:
		"""Generate a unique storage path for a conversation based on the current timestamp.

		Returns:
			A memory-based URL path with a timestamp-specific identifier for storing conversation attachments.
		"""
		return UPath(
			f"memory://conversation_{datetime.datetime.now().isoformat(timespec='seconds')}"
		)

	@classmethod
	def open_conversation(
		cls, parent: wx.Window, file_path: str, default_title: str
	) -> ConversationTab:
		"""Open a conversation from a file and create a new ConversationTab instance.

		This class method loads a conversation from a specified file path, generates a unique storage path,
		and initializes a new ConversationTab with the loaded conversation details.

		Args:
			parent: The parent window for the conversation tab.
			file_path: The path to the conversation file to be opened.
			default_title: A fallback title to use if the conversation has no title.

		Returns:
			A new ConversationTab instance with the loaded conversation.

		Raises:
			IOError: If the conversation file cannot be read or parsed.

		Example:
			conversation_tab = ConversationTab.open_conversation(
				parent_window, "/path/to/conversation.json", "My Conversation"
			)
		"""
		log.debug(f"Opening conversation from {file_path}")
		storage_path = cls.conv_storage_path()
		conversation = Conversation.open(file_path, storage_path)
		title = conversation.title or default_title
		return cls(
			parent,
			conversation=conversation,
			title=title,
			conv_storage_path=storage_path,
			bskc_path=file_path,
		)

	def __init__(
		self,
		parent: wx.Window,
		title: str = _("Untitled conversation"),
		profile: Optional[config.ConversationProfile] = None,
		conversation: Optional[Conversation] = None,
		conv_storage_path: Optional[UPath] = None,
		bskc_path: Optional[str] = None,
	):
		"""Initialize a new conversation tab in the chat application.

		Initializes the conversation tab by:
		- Setting up the wx.Panel and BaseConversation base classes
		- Configuring conversation metadata and storage
		- Preparing UI components and data structures
		- Initializing recording and message management resources

		Args:
			parent: The parent window containing this conversation tab.
			title: The title of the conversation. Defaults to "Untitled conversation".
			profile: The conversation profile to apply. Defaults to None.
			conversation: An existing conversation to load. Defaults to a new Conversation.
			conv_storage_path: Unique storage path for the conversation. Defaults to a generated path.
			bskc_path: Path to a specific configuration file. Defaults to None.
		"""
		wx.Panel.__init__(self, parent)
		BaseConversation.__init__(self)
		self.title = title
		self.SetStatusText = self.TopLevelParent.SetStatusText
		self.bskc_path = bskc_path
		self.conv_storage_path = conv_storage_path or self.conv_storage_path()
		self.conversation = conversation or Conversation()
		self.attachment_files: list[AttachmentFile | ImageFile] = []
		self.last_time = 0
		self.message_segment_manager = MessageSegmentManager()
		self.recording_thread: Optional[RecordingThread] = None
		self.task = None
		self.stream_buffer = ""
		self.speech_stream_buffer = ""
		self._speak_stream = True
		self._stop_completion = False
		self._search_dialog = None
		self.init_ui()
		self.init_data(profile)
		self.adjust_advanced_mode_setting()

	def init_ui(self):
		"""Initialize and layout all UI components of the conversation tab.

		Creates and configures:
		- Account selection combo box
		- System prompt input
		- Message history display
		- User prompt input
		- Attachment list display
		- Model selection
		- Generation parameters
		- Control buttons
		"""
		sizer = wx.BoxSizer(wx.VERTICAL)
		label = self.create_account_widget()
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.account_combo, proportion=0, flag=wx.EXPAND)

		label = self.create_system_prompt_widget()
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.system_prompt_txt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Messages:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(
			self,
			size=(800, 400),
			style=wx.TE_MULTILINE
			| wx.TE_READONLY
			| wx.TE_WORDWRAP
			| wx.HSCROLL,
		)
		self.messages.Bind(wx.EVT_CONTEXT_MENU, self.on_messages_context_menu)
		self.messages.Bind(wx.EVT_KEY_DOWN, self.on_messages_key_down)
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Prompt:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(
			self,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		self.prompt.Bind(wx.EVT_KEY_DOWN, self.on_prompt_key_down)
		self.prompt.Bind(wx.EVT_CONTEXT_MENU, self.on_prompt_context_menu)
		self.prompt.Bind(wx.EVT_TEXT_PASTE, self.on_prompt_paste)
		sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		self.attachments_list_label = wx.StaticText(
			self,
			# Translators: This is a label for models in the main window
			label=_("&Attachments:"),
		)
		sizer.Add(self.attachments_list_label, proportion=0, flag=wx.EXPAND)
		self.attachments_list = wx.ListCtrl(
			self, size=(800, 100), style=wx.LC_REPORT
		)
		self.attachments_list.Bind(
			wx.EVT_CONTEXT_MENU, self.on_attachments_context_menu
		)
		self.attachments_list.Bind(
			wx.EVT_KEY_DOWN, self.on_attachments_key_down
		)
		self.attachments_list.InsertColumn(
			0,
			# Translators: This is a label for attachment name in the main window
			_("Name"),
		)
		self.attachments_list.InsertColumn(
			1,
			# Translators: This is a label for attachment size in the main window
			_("Size"),
		)
		self.attachments_list.InsertColumn(
			2,
			# Translators: This is a label for attachment location in the main window
			_("Location"),
		)
		self.attachments_list.SetColumnWidth(0, 200)
		self.attachments_list.SetColumnWidth(1, 100)
		self.attachments_list.SetColumnWidth(2, 500)
		sizer.Add(self.attachments_list, proportion=0, flag=wx.ALL | wx.EXPAND)
		label = self.create_model_widget()
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.model_list, proportion=0, flag=wx.ALL | wx.EXPAND)
		self.create_max_tokens_widget()
		sizer.Add(self.max_tokens_spin_label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.max_tokens_spin_ctrl, proportion=0, flag=wx.EXPAND)
		self.create_temperature_widget()
		sizer.Add(self.temperature_spinner_label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.temperature_spinner, proportion=0, flag=wx.EXPAND)
		self.create_top_p_widget()
		sizer.Add(self.top_p_spinner_label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)
		self.create_stream_widget()
		sizer.Add(self.stream_mode, proportion=0, flag=wx.EXPAND)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

		self.submit_btn = wx.Button(
			self,
			# Translators: This is a label for submit button in the main window
			label=_("Submit") + " (Ctrl+Enter)",
		)
		self.submit_btn.Bind(wx.EVT_BUTTON, self.on_submit)
		self.submit_btn.SetDefault()
		btn_sizer.Add(self.submit_btn, proportion=0, flag=wx.EXPAND)

		self.stop_completion_btn = wx.Button(
			self,
			# Translators: This is a label for stop completion button in the main window
			label=_("Stop completio&n"),
		)
		self.stop_completion_btn.Bind(wx.EVT_BUTTON, self.on_stop_completion)
		btn_sizer.Add(self.stop_completion_btn, proportion=0, flag=wx.EXPAND)
		self.stop_completion_btn.Hide()

		self.toggle_record_btn = wx.Button(
			self,
			# Translators: This is a label for record button in the main window
			label=_("Record") + " (Ctrl+R)",
		)
		btn_sizer.Add(self.toggle_record_btn, proportion=0, flag=wx.EXPAND)
		self.toggle_record_btn.Bind(wx.EVT_BUTTON, self.toggle_recording)

		self.apply_profile_btn = wx.Button(
			self,
			# Translators: This is a label for apply profile button in the main window
			label=_("Apply profile") + " (Ctrl+P)",
		)
		self.apply_profile_btn.Bind(wx.EVT_BUTTON, self.on_choose_profile)
		btn_sizer.Add(self.apply_profile_btn, proportion=0, flag=wx.EXPAND)

		sizer.Add(btn_sizer, proportion=0, flag=wx.EXPAND)

		self.SetSizerAndFit(sizer)

		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

	def init_data(self, profile: Optional[config.ConversationProfile]):
		"""Initialize the conversation data with an optional profile.

		Args:
			profile: Configuration profile to apply
		"""
		self.refresh_attachments_list()
		self.apply_profile(profile, True)
		self.refresh_messages(need_clear=False)

	def on_choose_profile(self, event: wx.KeyEvent | None):
		"""Displays a context menu for selecting a conversation profile.

		This method triggers the creation of a profile selection menu from the main application frame
		and shows it as a popup menu at the current cursor position. After the user makes a selection,
		the menu is automatically destroyed.

		Args:
			event: The event that triggered the profile selection menu.
		"""
		main_frame: MainFrame = wx.GetTopLevelParent(self)
		menu = main_frame.build_profile_menu(
			main_frame.on_apply_conversation_profile
		)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_char_hook(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the conversation tab.

		Args:
			event: The keyboard event
		"""
		modifiers = event.GetModifiers()
		key_code = event.GetKeyCode()
		actions = {(wx.MOD_CONTROL, ord('P')): self.on_choose_profile}
		action = actions.get((modifiers, key_code))
		if action:
			action(event)
		else:
			event.Skip()

	def on_account_change(self, event: wx.CommandEvent | None):
		"""Handle account selection changes in the conversation tab.

		Updates the model list based on the selected account's.
		Enables/disables the record button based on the selected account's capabilities.

		Args:
			event: The account selection event
		"""
		account = super().on_account_change(event)
		if not account:
			return
		self.set_model_list(None)
		self.toggle_record_btn.Enable(
			ProviderCapability.STT in account.provider.engine_cls.capabilities
		)

	def on_attachments_context_menu(self, event: wx.ContextMenuEvent):
		"""Display context menu for the attachments list.

		Provides options for:
		- Removing selected attachment
		- Copying attachment location
		- Pasting attachments
		- Adding files
		- Adding image URLs

		Args:
			event (wx.ContextMenuEvent): The context menu trigger event
		"""
		selected = self.attachments_list.GetFirstSelected()
		menu = wx.Menu()

		if selected != wx.NOT_FOUND:
			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for show details in the context menu
				_("Show details") + "	Enter",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_show_attachment_details, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for remove selected image in the context menu
				_("Remove selected image") + "	Shift+Del",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_attachments_remove, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for copy location in the context menu
				_("Copy location") + "	Ctrl+C",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_copy_attachment_location, item)
		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for paste in the context menu
			_("Paste (file or text)") + "	Ctrl+V",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_attachments_paste, item)

		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for add files in the context menu
			_("Add files..."),
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.add_attachments_dlg, item)

		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for add image URL in the context menu
			_("Add image URL...") + "	Ctrl+U",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.add_image_url_dlg, item)

		self.attachments_list.PopupMenu(menu)
		menu.Destroy()

	def on_attachments_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the attachments list.

		Supports:
		- Ctrl+C: Copy file location
		- Ctrl+V: Paste image
		- Delete: Remove selected image

		Args:
			event: The keyboard event
		"""
		key_code = event.GetKeyCode()
		modifiers = event.GetModifiers()
		if modifiers == wx.MOD_CONTROL and key_code == ord("C"):
			self.on_copy_attachment_location(None)
		if modifiers == wx.MOD_CONTROL and key_code == ord("V"):
			self.on_attachments_paste(None)
		if modifiers == wx.MOD_NONE and key_code == wx.WXK_DELETE:
			self.on_attachments_remove(None)
		if modifiers == wx.MOD_NONE and key_code in (
			wx.WXK_RETURN,
			wx.WXK_NUMPAD_ENTER,
		):
			self.on_show_attachment_details(None)
		event.Skip()

	def on_attachments_paste(self, event: wx.CommandEvent):
		"""Handles pasting content from the clipboard into the conversation interface.

		Supports multiple clipboard data types:
		- Files: Adds files directly to the conversation
		- Text:
			- If a valid URL is detected, adds the image URL
			- Otherwise, pastes text into the prompt input
		- Bitmap images: Saves the image to a temporary file and adds it to the conversation

		Args:
		event: The clipboard paste event
		"""
		with wx.TheClipboard as clipboard:
			if clipboard.IsSupported(wx.DataFormat(wx.DF_FILENAME)):
				log.debug("Pasting files from clipboard")
				file_data = wx.FileDataObject()
				clipboard.GetData(file_data)
				paths = file_data.GetFilenames()
				self.add_attachments(paths)
			elif clipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
				log.debug("Pasting text from clipboard")
				text_data = wx.TextDataObject()
				clipboard.GetData(text_data)
				text = text_data.GetText()
				if re.fullmatch(URL_PATTERN, text):
					log.info("Pasting URL from clipboard, adding image")
					self.add_image_url_thread(text)
				else:
					log.info("Pasting text from clipboard")
					self.prompt.WriteText(text)
					self.prompt.SetFocus()
			elif clipboard.IsSupported(wx.DataFormat(wx.DF_BITMAP)):
				log.debug("Pasting bitmap from clipboard")
				bitmap_data = wx.BitmapDataObject()
				success = clipboard.GetData(bitmap_data)
				if not success:
					log.error("Failed to get bitmap data from clipboard")
					return
				img = bitmap_data.GetBitmap().ConvertToImage()
				path = (
					self.conv_storage_path
					/ f"clipboard_{datetime.datetime.now().isoformat(timespec='seconds')}.png"
				)
				with path.open("wb") as f:
					img.SaveFile(f, wx.BITMAP_TYPE_PNG)
				self.add_attachments([ImageFile(location=path)])

			else:
				log.info("Unsupported clipboard data")

	def add_attachments_dlg(self, event: wx.CommandEvent = None):
		"""Open a file dialog to select and add files to the conversation.

		Args:
			event: Event triggered by the add files action
		"""
		wildcard = parse_supported_attachment_formats(
			self.current_engine.supported_attachment_formats
		)
		if not wildcard:
			wx.MessageBox(
				# Translators: This message is displayed when there are no supported attachment formats.
				_("This provider does not support any attachment formats."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		wildcard = _("All supported formats") + f" ({wildcard})|{wildcard}"
		file_dialog = wx.FileDialog(
			self,
			# Translators: This is a label for select files in conversation tab
			message=_("Select one or more files to attach"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
			wildcard=wildcard,
		)
		if file_dialog.ShowModal() == wx.ID_OK:
			paths = file_dialog.GetPaths()
			self.add_attachments(paths)
		file_dialog.Destroy()

	def add_image_url_dlg(self, event: wx.CommandEvent | None):
		"""Open a dialog to input an image URL and add it to the conversation.

		Args:
			event: Event triggered by the add image URL action
		"""
		url_dialog = wx.TextEntryDialog(
			self,
			# Translators: This is a label for image URL in conversation tab
			message=_("Enter the URL of the image:"),
			caption=_("Add image URL"),
		)
		if url_dialog.ShowModal() != wx.ID_OK:
			return
		url = url_dialog.GetValue()
		if not url:
			return
		if not re.fullmatch(URL_PATTERN, url):
			wx.MessageBox(
				_("Invalid URL, bad format."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		self.add_image_url_thread(url)
		url_dialog.Destroy()

	def force_image_from_url(self, url: str, content_type: str):
		"""Handle adding an image from a URL with a non-image content type.

		Displays a warning message to the user and prompts for confirmation to proceed.

		Args:
			url: The URL of the image
			content_type: The content type of the URL
		"""
		log.warning(
			f"The {url} URL seems to not point to an image. The content type is {content_type}."
		)
		force_add = wx.MessageBox(
			# Translators: This message is displayed when the image URL seems to not point to an image.
			_(
				"The URL seems to not point to an image (content type: %s). Do you want to continue?"
			)
			% content_type,
			_("Warning"),
			wx.YES_NO | wx.ICON_WARNING | wx.NO_DEFAULT,
		)
		if force_add == wx.YES:
			log.info("Forcing image addition")
			self.add_attachments([ImageFile(location=url)])

	def add_image_from_url(self, url: str):
		"""Add an image to the conversation from a URL.

		Args:
			url: The URL of the image to add
		"""
		image_file = None
		try:
			image_file = ImageFile.build_from_url(url)
		except HTTPError as err:
			wx.CallAfter(
				wx.MessageBox,
				# Translators: This message is displayed when the image URL returns an HTTP error.
				_("HTTP error %s.") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		except NotImageError as err:
			wx.CallAfter(self.force_image_from_url, url, err.content_type)
		except BaseException as err:
			log.error(err)
			wx.CallAfter(
				wx.MessageBox,
				# Translators: This message is displayed when an error occurs while getting image dimensions.
				_("Error getting image dimensions: %s") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		wx.CallAfter(self.add_attachments, [image_file])
		self.task = None

	@ensure_no_task_running
	def add_image_url_thread(self, url: str):
		"""Start a thread to add an image to the conversation from a URL.

		Args:
			url: The URL of the image to add
		"""
		self.task = threading.Thread(
			target=self.add_image_from_url, args=(url,)
		)
		self.task.start()

	def on_show_attachment_details(self, event: wx.CommandEvent):
		"""Show details of the selected attachment in a read-only dialog.

		Args:
			event: Event triggered by the show attachment details action
		"""
		selected = self.attachments_list.GetFirstSelected()
		if selected == wx.NOT_FOUND:
			return
		attachment_file = self.attachment_files[selected]
		details = {
			_("Name"): attachment_file.name,
			_("Size"): attachment_file.display_size,
			_("Location"): attachment_file.location,
		}
		mime_type = attachment_file.mime_type
		if mime_type:
			details[_("MIME type")] = mime_type
			if mime_type.startswith("image/"):
				details[_("Dimensions")] = attachment_file.display_dimensions
		details_str = "\n".join(
			_("%s: %s") % (k, v) for k, v in details.items()
		)
		ReadOnlyMessageDialog(
			self, _("Attachment details"), details_str
		).ShowModal()

	def on_attachments_remove(self, event: wx.CommandEvent):
		"""Remove the selected attachment from the conversation.

		Args:
			event: Event triggered by the remove attachment action
		"""
		selection = self.attachments_list.GetFirstSelected()
		if selection == wx.NOT_FOUND:
			return
		self.attachment_files.pop(selection)
		self.refresh_attachments_list()
		if selection >= self.attachments_list.GetItemCount():
			selection -= 1
		if selection >= 0:
			self.attachments_list.SetItemState(
				selection, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
			)
		else:
			self.prompt.SetFocus()

	def on_copy_attachment_location(self, event: wx.CommandEvent):
		"""Copy the location of the selected attachment to the clipboard.

		Args:
			event: Event triggered by the copy attachment location action
		"""
		selected = self.attachments_list.GetFirstSelected()
		if selected == wx.NOT_FOUND:
			return
		location = "\"%s\"" % str(self.attachment_files[selected].location)
		with wx.TheClipboard as clipboard:
			clipboard.SetData(wx.TextDataObject(location))

	def refresh_accounts(self):
		"""Update the account selection combo box with current accounts.

		Preserves the current selection if possible, otherwise selects the first account.
		"""
		account_index = self.account_combo.GetSelection()
		account_id = None
		if account_index != wx.NOT_FOUND:
			account_id = config.accounts()[account_index].id
		self.account_combo.Clear()
		self.account_combo.AppendItems(self.get_display_accounts(True))
		account_index = first(
			locate(config.accounts(), lambda a: a.id == account_id),
			wx.NOT_FOUND,
		)
		if account_index != wx.NOT_FOUND:
			self.account_combo.SetSelection(account_index)
		elif self.account_combo.GetCount() > 0:
			self.account_combo.SetSelection(0)
			self.account_combo.SetFocus()

	def refresh_attachments_list(self):
		"""Update the attachments list display based on the current attachment files.

		Shows/hides the attachments list based on the number of attachments.
		Updates all attachment details in the list.
		"""
		self.attachments_list.DeleteAllItems()
		if not self.attachment_files:
			self.attachments_list_label.Hide()
			self.attachments_list.Hide()
			self.Layout()
			return
		self.attachments_list_label.Show()
		self.attachments_list.Show()
		for attachment in self.attachment_files:
			self.attachments_list.Append(attachment.get_dispay_info())
		last_index = len(self.attachment_files) - 1
		self.attachments_list.SetItemState(
			last_index, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
		)
		self.attachments_list.EnsureVisible(last_index)
		self.Layout()

	def add_attachments(self, paths: list[str | AttachmentFile | ImageFile]):
		"""Add one or more attachments to the conversation.

		Args:
			paths: List of attachment file paths
		"""
		log.debug(f"Adding attachments: {paths}")
		for path in paths:
			if isinstance(path, (AttachmentFile, ImageFile)):
				self.attachment_files.append(path)
			else:
				mime_type = get_mime_type(path)
				supported_attachment_formats = (
					self.current_engine.supported_attachment_formats
				)
				if mime_type not in supported_attachment_formats:
					wx.MessageBox(
						# Translators: This message is displayed when there are no supported attachment formats.
						_(
							"This attachment format is not supported by the current provider. Source:"
						)
						+ f"\n{path}",
						_("Error"),
						wx.OK | wx.ICON_ERROR,
					)
					continue
				if mime_type.startswith("image/"):
					file = ImageFile(location=path)
				else:
					file = AttachmentFile(location=path)
				self.attachment_files.append(file)
		self.refresh_attachments_list()
		self.attachments_list.SetFocus()

	def on_config_change(self):
		"""Handle configuration changes in the conversation tab.

		Update account, model list and advanced mode settings.
		"""
		self.refresh_accounts()
		self.on_account_change(None)
		self.on_model_change(None)
		self.adjust_advanced_mode_setting()

	def add_standard_context_menu_items(
		self, menu: wx.Menu, include_paste: bool = True
	):
		"""Add standard context menu items to a menu.

		Args:
			menu: The menu to add items to
			include_paste: Whether to include the paste item
		"""
		menu.Append(wx.ID_UNDO)
		menu.Append(wx.ID_REDO)
		menu.Append(wx.ID_CUT)
		menu.Append(wx.ID_COPY)
		if include_paste:
			menu.Append(wx.ID_PASTE)
		menu.Append(wx.ID_SELECTALL)

	def _do_search_in_messages(
		self, direction: SearchDirection = SearchDirection.FORWARD
	):
		"""Open the search dialog for searching in the messages.

		Args:
			direction: The search direction (forward or backward)
		"""
		if not self._search_dialog:
			self._search_dialog = SearchDialog(self, self.messages)
		self._search_dialog._dir_radio_forward.SetValue(
			direction == SearchDirection.FORWARD
		)
		self._search_dialog._dir_radio_backward.SetValue(
			direction == SearchDirection.BACKWARD
		)

		self._search_dialog._search_combo.SetFocus()
		self._search_dialog._search_combo.SelectAll()
		self._search_dialog.ShowModal()

	def on_search_in_messages(self, event: wx.CommandEvent | None = None):
		"""Handle searching in the messages.

		Args:
			event: The event that triggered the search action
		"""
		self._do_search_in_messages()

	def on_search_in_messages_previous(
		self, event: wx.CommandEvent | None = None
	):
		"""Search for the previous occurrence in the messages.

		Args:
			event: The event that triggered the search action
		"""
		if not self._search_dialog:
			return self._do_search_in_messages(SearchDirection.BACKWARD)
		self._search_dialog.search_previous()

	def on_search_in_messages_next(self, event: wx.CommandEvent | None = None):
		"""Search for the next occurrence in the messages.

		Args:
			event: The event that triggered the search action
		"""
		if not self._search_dialog:
			return self._do_search_in_messages()
		self._search_dialog.search_next()

	def navigate_message(self, previous: bool):
		"""Navigate to the previous or next message in the conversation.

		Args:
			previous: Whether to navigate to the previous message
		"""
		self.message_segment_manager.absolute_position = (
			self.messages.GetInsertionPoint()
		)
		try:
			if previous:
				self.message_segment_manager.previous(
					MessageSegmentType.CONTENT
				)
			else:
				self.message_segment_manager.next(MessageSegmentType.CONTENT)
		except IndexError:
			wx.Bell()
			return
		try:
			pos = self.message_segment_manager.start
		except IndexError:
			wx.Bell()
		else:
			self.messages.SetInsertionPoint(pos)
			if config.conf().conversation.nav_msg_select:
				self.select_current_message()
			else:
				start, end = self.get_range_for_current_message()
				current_message = self.messages.GetRange(start, end)
				self._handle_accessible_output(current_message)
				self.report_number_of_citations()

	def _handle_citations(self, citations: list[dict[str, Any]]) -> str:
		"""Format a list of citations for display.

		Args:
			citations: The list of citations to format

		Returns:
			A formatted string containing the citations
		"""
		citations_str = []
		for i, citation in enumerate(citations):
			location_text = ""
			cited_text = citation.get("cited_text")
			document_index = citation.get("document_index")
			document_title = citation.get("document_title")
			match citation.get("type"):
				case "char_location":
					start_char_index = citation.get("start_char_index", 0)
					end_char_index = citation.get("end_char_index", 0)
					# Translators: This is a citation format for character locations
					location_text = _("C.{start} .. {end}").format(
						start=start_char_index, end=end_char_index
					)
				case "page_location":
					start_page_number = citation.get("start_page_number", 0)
					end_page_number = citation.get("end_page_number", 0)
					# Translators: This is a citation format for page locations
					location_text = _("P.{start} .. {end}").format(
						start=start_page_number, end=end_page_number
					)
				case _:
					# Translators: This is a citation format for unknown locations
					location_text = _("Unknown location")
					log.warning(f"Unknown citation type: {citation}")
			if document_index is not None:
				if document_title:
					location_text = _(
						"{document_title} / {location_text}"
					).format(
						document_title=document_title,
						location_text=location_text,
					)
				else:
					location_text = _(
						"Document {document_index} / {location_text}"
					).format(
						document_index=document_index,
						location_text=location_text,
					)
			if cited_text:
				citations_str.append(
					# Translators: This is a citation format for a cited text
					_("{location_text}: “{cited_text}”").format(
						location_text=location_text,
						cited_text=cited_text.strip(),
					)
				)
		return "\n_--_\n".join(citations_str)

	def get_current_citations(self) -> list[dict[str, Any]]:
		"""Get the citations for the current message.

		Returns:
			The list of citations for the current message
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		message_block = (
			self.message_segment_manager.current_segment.message_block()
		)
		if not message_block:
			wx.Bell()
			return []
		return message_block.response.citations

	def report_number_of_citations(self):
		"""Report the number of citations for the current message."""
		citations = self.get_current_citations()
		if not citations:
			return
		nb_citations = len(citations)
		self.SetStatusText(
			# Translators: This is a status message for the number of citations in the current message
			_("%d citations in the current message") % nb_citations
		)

	def show_citations(self, event: wx.CommandEvent | None = None):
		"""Show the citations for the current message.

		Args:
			event: The event that triggered the action
		"""
		self.report_number_of_citations()
		citations = self.get_current_citations()
		if not citations:
			self._handle_accessible_output(
				# Translators: This message is emitted when there are no citations for the current message.
				_("No citations for this message"),
				braille=True,
			)
			wx.Bell()
			return
		citations_str = self._handle_citations(citations)
		if not citations_str:
			wx.Bell()
			return
		ReadOnlyMessageDialog(
			self,
			# Translators: This is a title for message citations dialog
			_("Message citations"),
			citations_str,
		).ShowModal()

	def go_to_previous_message(self, event: wx.CommandEvent | None = None):
		"""Navigate to the previous message in the conversation.

		Args:
			event: The event that triggered the navigation action
		"""
		self.navigate_message(True)

	def go_to_next_message(self, event: wx.CommandEvent | None = None):
		"""Navigate to the next message in the conversation.

		Args:
			event: The event that triggered the navigation action
		"""
		self.navigate_message(False)

	def move_to_start_of_message(self, event: wx.CommandEvent | None = None):
		"""Move the cursor to the start of the current message.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		self.message_segment_manager.focus_content_block()
		self.messages.SetInsertionPoint(self.message_segment_manager.start)
		self._handle_accessible_output(_("Start of message"))

	def move_to_end_of_message(self, event: wx.CommandEvent = None):
		"""Move the cursor to the end of the current message.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		self.message_segment_manager.focus_content_block()
		self.messages.SetInsertionPoint(self.message_segment_manager.end - 1)
		self._handle_accessible_output(_("End of message"))

	def get_range_for_current_message(self) -> tuple[int, int]:
		"""Get the range of the current message in the messages text control.

		Returns:
			A tuple containing the start and end positions of the current message
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		self.message_segment_manager.focus_content_block()
		start = self.message_segment_manager.start
		end = self.message_segment_manager.end
		return start, end

	def select_current_message(self):
		"""Select the current message in the messages text control."""
		self.messages.SetSelection(*self.get_range_for_current_message())

	def on_select_message(self, event: wx.CommandEvent | None = None):
		"""Select the current message in the messages text control.

		Args:
			event: The event that triggered the selection action
		"""
		self.select_current_message()

	def on_toggle_speak_stream(self, event: wx.CommandEvent | None = None):
		"""Toggle the stream speaking mode.

		Args:
			event: The event that triggered the action
		"""
		if event:
			return wx.CallLater(500, self.on_toggle_speak_stream)
		self._speak_stream = not self._speak_stream
		self._handle_accessible_output(
			_("Stream speaking %s")
			% (_("enabled") if self._speak_stream else _("disabled")),
			braille=True,
		)

	def on_read_current_message(self, event: wx.CommandEvent | None = None):
		"""Read the current message in the messages text control.

		Args:
			event: The event that triggered the action
		"""
		if event:
			return wx.CallLater(500, self.on_read_current_message)
		self.report_number_of_citations()
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		self.message_segment_manager.focus_content_block()
		start = self.message_segment_manager.start
		end = self.message_segment_manager.end
		content = self.messages.GetRange(start, end)
		self._handle_accessible_output(content, force=True)

	def on_show_as_html(self, event: wx.CommandEvent | None = None):
		"""Show the current message as HTML in a new window.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		start = self.message_segment_manager.start
		end = self.message_segment_manager.end
		content = self.messages.GetRange(start, end)
		show_html_view_window(self, content, "markdown")

	def on_copy_message(self, event: wx.CommandEvent | None = None):
		"""Copy the current message to the clipboard.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.select_current_message()
		self.messages.Copy()
		self.messages.SetInsertionPoint(cursor_pos)
		self._handle_accessible_output(
			_("Message copied to clipboard"), braille=True
		)

	def on_remove_message_block(self, event: wx.CommandEvent | None = None):
		"""Remove the current message block from the conversation.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.messages.GetInsertionPoint()
		self.message_segment_manager.absolute_position = cursor_pos
		message_block = (
			self.message_segment_manager.current_segment.message_block()
		)
		if message_block:
			self.conversation.messages.remove(message_block)
			self.refresh_messages()
			self.messages.SetInsertionPoint(cursor_pos)
			self._handle_accessible_output(
				_("Message block removed"), braille=True
			)

		else:
			wx.Bell()

	def on_messages_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the messages text control.

		Supports:
		- Space: Read current message
		- Shift+Space: Toggle stream speaking mode
		- J: Go to previous message
		- K: Go to next message
		- S: Select current message
		- H: Show current message as HTML
		- C: Copy current message
		- B: Move to start of message
		- N: Move to end of message
		- Q: Show citations for current message
		- Shift+Delete: Remove current message block
		- F3: Search in messages (forward)
		- Shift+F3: Search in messages (backward)
		- Ctrl+F: open Search in messages dialog

		Args:
			event: The keyboard event
		"""
		if not self.conversation.messages:
			event.Skip()
			return
		modifiers = event.GetModifiers()
		key_code = event.GetKeyCode()

		key_actions = {
			(wx.MOD_SHIFT, wx.WXK_SPACE): self.on_toggle_speak_stream,
			(wx.MOD_NONE, wx.WXK_SPACE): self.on_read_current_message,
			(wx.MOD_NONE, ord('Q')): self.show_citations,
			(wx.MOD_NONE, ord('J')): self.go_to_previous_message,
			(wx.MOD_NONE, ord('K')): self.go_to_next_message,
			(wx.MOD_NONE, ord('S')): self.on_select_message,
			(wx.MOD_NONE, ord('H')): self.on_show_as_html,
			(wx.MOD_NONE, ord('C')): self.on_copy_message,
			(wx.MOD_NONE, ord('B')): self.move_to_start_of_message,
			(wx.MOD_NONE, ord('N')): self.move_to_end_of_message,
			(wx.MOD_SHIFT, wx.WXK_DELETE): self.on_remove_message_block,
			(wx.MOD_NONE, wx.WXK_F3): self.on_search_in_messages_next,
			(wx.MOD_NONE, ord('F')): self.on_search_in_messages,
			(wx.MOD_CONTROL, ord('F')): self.on_search_in_messages,
			(wx.MOD_SHIFT, wx.WXK_F3): self.on_search_in_messages_previous,
		}

		action = key_actions.get((modifiers, key_code))

		if action:
			action()
		else:
			event.Skip()

	def on_messages_context_menu(self, event: wx.ContextMenuEvent):
		"""Display context menu for the messages text control.

		Provides options for:
		- Reading the current message
		- Toggling stream speaking mode
		- Showing the current message as HTML
		- Copying the current message
		- Selecting the current message
		- Going to the previous message
		- Going to the next message
		- Moving to the start of the current message
		- Moving to the end of the current message
		- Removing the current message block
		- Searching in the messages
		- Searching for the next occurrence
		- Searching for the previous occurrence

		Args:
			event: The context menu trigger event
		"""
		menu = wx.Menu()

		if self.conversation.messages:
			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Read current message") + "	Space",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_read_current_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Show citations") + "	&Q",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.show_citations, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Speak stream") + "	Shift+Space",
				_("Speak stream"),
				wx.ITEM_CHECK,
			)
			menu.Append(item)
			item.Check(self._speak_stream)
			self.Bind(wx.EVT_MENU, self.on_toggle_speak_stream, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Show as HTML (from Markdown)") + "	&H",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_show_as_html, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Copy current message") + "	&C",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_copy_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Select current message") + "	&S",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_select_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Go to previous message") + "	&J",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.go_to_previous_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Go to next message") + "	&K",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.go_to_next_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Move to start of message") + "	&B",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.move_to_start_of_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Move to end of message") + "	N",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.move_to_end_of_message, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("&Remove message block") + "	Shift+Del",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_remove_message_block, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Find...") + "	F",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_search_in_messages, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for the Messages area context menu in the main window
				_("Find Next") + "	F3",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_search_in_messages_next, item)

			item = wx.MenuItem(
				menu, wx.ID_ANY, _("Find Previous") + "	Shift+F3"
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_search_in_messages_previous, item)

		self.add_standard_context_menu_items(menu)
		self.messages.PopupMenu(menu)
		menu.Destroy()

	def on_prompt_context_menu(self, event: wx.ContextMenuEvent):
		"""Display context menu for the prompt text control.

		Provides options for:
		- Inserting the previous prompt
		- Submitting the current prompt
		- Pasting content from the clipboard
		- Copying content from the prompt
		- Cutting content from the prompt
		- Selecting all content in the prompt

		Args:
			event: The context menu trigger event
		"""
		menu = wx.Menu()
		item = wx.MenuItem(
			menu, wx.ID_ANY, _("Insert previous prompt") + "	Ctrl+Up"
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.insert_previous_prompt, item)

		item = wx.MenuItem(menu, wx.ID_ANY, _("Submit") + " (Ctrl+Enter)")
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_submit, item)
		item = wx.MenuItem(
			menu, wx.ID_ANY, _("Paste (file or text)") + "	Ctrl+V"
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_prompt_paste, item)

		self.add_standard_context_menu_items(menu, include_paste=False)
		self.prompt.PopupMenu(menu)
		menu.Destroy()

	def on_prompt_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the prompt text control.

		Supports:
		- Ctrl+Up: Insert previous prompt
		- Ctrl+Enter: Submit the current prompt
		- Ctrl+V: Paste content from the clipboard
		- Ctrl+C: Copy content from the prompt
		- Ctrl+X: Cut content from the prompt
		- Ctrl+A: Select all content in the prompt

		Args:
			event: The keyboard event
		"""
		modifiers = event.GetModifiers()
		key_code = event.GetKeyCode()
		match (modifiers, key_code):
			case (wx.MOD_NONE, wx.WXK_RETURN) | (
				wx.MOD_NONE,
				wx.WXK_NUMPAD_ENTER,
			):
				if config.conf().conversation.shift_enter_mode:
					self.on_submit(event)
					event.StopPropagation()
				else:
					event.Skip()
			case (wx.MOD_CONTROL, wx.WXK_UP):
				if not self.prompt.GetValue():
					self.insert_previous_prompt()
			case (wx.MOD_CONTROL, wx.WXK_RETURN) | (
				wx.MOD_CONTROL,
				wx.WXK_NUMPAD_ENTER,
			):
				self.on_submit(event)
			case _:
				event.Skip()

	def on_prompt_paste(self, event):
		"""Handle pasting content from the clipboard into the prompt text control.

		Supports pasting text and files from the clipboard.

		Args:
			event: The paste event
		"""
		self.on_attachments_paste(event)

	def insert_previous_prompt(self, event: wx.CommandEvent = None):
		"""Insert the last user message from the conversation history into the prompt text control.

		This method retrieves the content of the most recent user message from the conversation
		and sets it as the current value of the prompt input field. If no messages exist in
		the conversation, no action is taken.

		Args:
			event: The wxPython event that triggered this method. Defaults to None and is not used in the method's logic.
		"""
		if self.conversation.messages:
			last_user_message = self.conversation.messages[-1].request.content
			self.prompt.SetValue(last_user_message)

	def extract_text_from_message(self, content: str) -> str:
		"""Extracts the text content from a message.

		Args:
		content: The message content to extract text from.

		Returns:
		The extracted text content of the message.
		"""
		if isinstance(content, str):
			return content

	def append_text_and_create_segment(
		self,
		text: str,
		segment_type: MessageSegmentType,
		new_block_ref: MessageBlock,
		absolute_length: int,
	):
		"""Appends text to the messages control and creates a corresponding message segment.

		This method performs two primary actions:
		1. Adds the specified text to the messages text control
		2. Creates a new message segment with metadata about the text's position and type

		Args:
			text: The text to be appended to the messages control
			segment_type: The type/kind of message segment being added
			new_block_ref: Reference to the message block associated with this segment
			absolute_length: The current absolute position in the text control before appending

		Returns:
			The new absolute length of text in the messages control after appending
		"""
		self.messages.AppendText(text)
		relative_length = self.messages.GetLastPosition() - absolute_length
		absolute_length = self.messages.GetLastPosition()
		self.message_segment_manager.append(
			MessageSegment(
				length=relative_length,
				kind=segment_type,
				message_block=new_block_ref,
			)
		)
		return absolute_length

	def display_new_block(self, new_block: MessageBlock):
		"""Displays a new message block in the conversation text control.

		This method appends a new message block to the existing conversation, handling both request and response messages. It manages the formatting and segmentation of messages, including role labels and content.

		Parameters:
		    new_block (MessageBlock): The message block to be displayed in the conversation.

		Notes:
		    - Handles empty and non-empty message text controls
		    - Supports configurable role labels from system configuration
		    - Uses weak references to track message blocks
		    - Preserves the original insertion point after displaying the block
		    - Supports both request and optional response messages
		"""
		absolute_length = self.messages.GetLastPosition()
		new_block_ref = weakref.ref(new_block)

		if not self.messages.IsEmpty():
			absolute_length = self.append_text_and_create_segment(
				os.linesep,
				MessageSegmentType.SUFFIX,
				new_block_ref,
				absolute_length,
			)

		role_label = (
			config.conf().conversation.role_label_user
			or self.ROLE_LABELS[new_block.request.role]
		)
		absolute_length = self.append_text_and_create_segment(
			role_label,
			MessageSegmentType.PREFIX,
			new_block_ref,
			absolute_length,
		)

		content = self.extract_text_from_message(new_block.request.content)
		absolute_length = self.append_text_and_create_segment(
			content, MessageSegmentType.CONTENT, new_block_ref, absolute_length
		)

		absolute_length = self.append_text_and_create_segment(
			os.linesep,
			MessageSegmentType.SUFFIX,
			new_block_ref,
			absolute_length,
		)

		pos = self.messages.GetInsertionPoint()

		if new_block.response:
			role_label = (
				config.conf().conversation.role_label_assistant
				or self.ROLE_LABELS[new_block.response.role]
			)
			absolute_length = self.append_text_and_create_segment(
				role_label,
				MessageSegmentType.PREFIX,
				new_block_ref,
				absolute_length,
			)

			content = self.extract_text_from_message(new_block.response.content)
			absolute_length = self.append_text_and_create_segment(
				content,
				MessageSegmentType.CONTENT,
				new_block_ref,
				absolute_length,
			)

		self.messages.SetInsertionPoint(pos)

	def refresh_messages(self, need_clear: bool = True):
		"""Refreshes the messages displayed in the conversation tab.

		This method updates the conversation display by optionally clearing existing content and then
		re-displaying all messages from the current conversation. It performs the following steps:
		- Optionally clears the messages list, message segment manager, and attachment files
		- Refreshes the attachments list display
		- Iterates through all message blocks in the conversation and displays them

		Args:
			need_clear: If True, clears existing messages, message segments, and attachments. Defaults to True.
		"""
		if need_clear:
			self.messages.Clear()
			self.message_segment_manager.clear()
			self.attachment_files.clear()
		self.refresh_attachments_list()
		for block in self.conversation.messages:
			self.display_new_block(block)

	def transcribe_audio_file(self, audio_file: str = None):
		"""Transcribe an audio file using the current provider's STT capabilities.

		Args:
			audio_file: Path to audio file. If None, starts recording. Defaults to None.
		"""
		if not self.recording_thread:
			module = __import__(
				"basilisk.recording_thread", fromlist=["RecordingThread"]
			)
			recording_thread_cls = getattr(module, "RecordingThread")
		else:
			recording_thread_cls = self.recording_thread.__class__
		self.recording_thread = recording_thread_cls(
			provider_engine=self.current_engine,
			recordings_settings=config.conf().recordings,
			conversation_tab=self,
			audio_file_path=audio_file,
		)
		self.recording_thread.start()

	def on_transcribe_audio_file(self):
		"""Transcribe an audio file using the current provider's STT capabilities."""
		cur_provider = self.current_engine
		if ProviderCapability.STT not in cur_provider.capabilities:
			wx.MessageBox(
				_("The selected provider does not support speech-to-text"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		dlg = wx.FileDialog(
			self,
			# Translators: This is a label for audio file in the main window
			message=_("Select an audio file to transcribe"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST,
			wildcard=_("Audio files")
			+ " (*.mp3;*.mp4;*.mpeg;*.mpga;*.m4a;*.wav;*.webm)|*.mp3;*.mp4;*.mpeg;*.mpga;*.m4a;*.wav;*.webm",
		)
		if dlg.ShowModal() == wx.ID_OK:
			audio_file = dlg.GetPath()
			dlg.Destroy()
			self.transcribe_audio_file(audio_file)
		else:
			dlg.Destroy()

	def on_recording_started(self):
		"""Handle the start of audio recording."""
		play_sound("recording_started")
		self.SetStatusText(_("Recording..."))

	def on_recording_stopped(self):
		"""Handle the end of audio recording."""
		play_sound("recording_stopped")
		self.SetStatusText(_("Recording stopped"))

	def on_transcription_started(self):
		"""Handle the start of audio transcription."""
		play_sound("progress", loop=True)
		self.SetStatusText(_("Transcribing..."))

	def on_transcription_received(self, transcription):
		"""Handle the receipt of a transcription result.

		Args:
			transcription: The transcription result
		"""
		stop_sound()
		self.SetStatusText(_("Ready"))
		self.prompt.AppendText(transcription.text)
		if self.prompt.HasFocus() and self.GetTopLevelParent().IsShown():
			self._handle_accessible_output(transcription.text)
		self.prompt.SetInsertionPointEnd()
		self.prompt.SetFocus()

	def on_transcription_error(self, error):
		"""Handle an error during audio transcription.

		Args:
			error: The error that occurred
		"""
		stop_sound()
		self.SetStatusText(_("Ready"))
		wx.MessageBox(
			_("An error occurred during transcription: ") + str(error),
			_("Error"),
			wx.OK | wx.ICON_ERROR,
		)

	def toggle_recording(self, event: wx.CommandEvent):
		"""Toggle audio recording on/off.

		Args:
			event: The button event
		"""
		if self.recording_thread and self.recording_thread.is_alive():
			self.stop_recording()
		else:
			self.start_recording()

	def start_recording(self):
		"""Start audio recording."""
		cur_provider = self.current_engine
		if ProviderCapability.STT not in cur_provider.capabilities:
			wx.MessageBox(
				_("The selected provider does not support speech-to-text"),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		self.toggle_record_btn.SetLabel(_("Stop recording") + " (Ctrl+R)")
		self.submit_btn.Disable()
		self.transcribe_audio_file()

	def stop_recording(self):
		"""Stop audio recording."""
		self.recording_thread.stop()
		self.toggle_record_btn.SetLabel(_("Record") + " (Ctrl+R)")
		self.submit_btn.Enable()

	def ensure_model_compatibility(self) -> ProviderAIModel | None:
		"""Check if current model is compatible with requested operations.

		Returns:
			The current model if compatible, None otherwise
		"""
		model = self.current_model
		if not model:
			wx.MessageBox(
				_("Please select a model"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return None
		if self.attachment_files and not model.vision:
			vision_models = ", ".join(
				[m.name or m.id for m in self.current_engine.models if m.vision]
			)
			wx.MessageBox(
				_(
					"The selected model does not support images. Please select a vision model instead ({})."
				).format(vision_models),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return None
		return model

	def get_system_message(self) -> Message | None:
		"""Get the system message from the system prompt input.

		Returns:
			System message if set, None otherwise
		"""
		system_prompt = self.system_prompt_txt.GetValue()
		if not system_prompt:
			return None
		return Message(role=MessageRoleEnum.SYSTEM, content=system_prompt)

	def get_new_message_block(self) -> MessageBlock | None:
		"""Constructs a new message block for the conversation based on current UI settings.

		Prepares a message block with user input, selected model, and generation parameters. If image resizing is enabled in configuration, it resizes attached images before creating the message block.

		Returns:
			A configured message block containing user prompt, images, model details, and generation parameters.
		If no compatible model is available or no user input is provided, returns None.
		"""
		model = self.ensure_model_compatibility()
		if not model:
			return None
		if config.conf().images.resize:
			for attachment in self.attachment_files:
				if not attachment.mime_type.startswith("image/"):
					continue
				attachment.resize(
					self.conv_storage_path,
					config.conf().images.max_width,
					config.conf().images.max_height,
					config.conf().images.quality,
				)
		return MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=self.prompt.GetValue(),
				attachments=self.attachment_files,
			),
			model_id=model.id,
			provider_id=self.current_account.provider.id,
			temperature=self.temperature_spinner.GetValue(),
			top_p=self.top_p_spinner.GetValue(),
			max_tokens=self.max_tokens_spin_ctrl.GetValue(),
			stream=self.stream_mode.GetValue(),
		)

	def get_completion_args(self) -> dict[str, Any] | None:
		"""Get the arguments for the completion request.

		Returns:
			A dictionary containing the arguments for the completion request.
		If no new message block is available, returns None.
		"""
		new_block = self.get_new_message_block()
		if not new_block:
			return None
		return {
			"engine": self.current_engine,
			"system_message": self.get_system_message(),
			"conversation": self.conversation,
			"new_block": new_block,
			"stream": new_block.stream,
		}

	def _check_attachments_valid(self) -> bool:
		supported_attachment_formats = (
			self.current_engine.supported_attachment_formats
		)
		invalid_found = False
		attachments_copy = self.attachment_files[:]
		for attachment in attachments_copy:
			if (
				attachment.mime_type not in supported_attachment_formats
				or not attachment.location.exists()
			):
				self.attachment_files.remove(attachment)
				msg = (
					_(
						"This attachment format is not supported by the current provider. Source:"
					)
					if attachment.mime_type not in supported_attachment_formats
					else _("The attachment file does not exist: %s")
					% attachment.location
				)
				wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
				invalid_found = True
		return not invalid_found

	@ensure_no_task_running
	def on_submit(self, event: wx.CommandEvent):
		"""Handle the submission of a new message block for completion.

		Args:
			event: The event that triggered the submission action
		"""
		if not self.submit_btn.IsEnabled():
			return
		if not self._check_attachments_valid():
			return
		if not self.prompt.GetValue() and not self.attachment_files:
			self.prompt.SetFocus()
			return
		completion_kw = self.get_completion_args()
		if not completion_kw:
			return
		self.submit_btn.Disable()
		self.stop_completion_btn.Show()
		if config.conf().conversation.focus_history_after_send:
			self.messages.SetFocus()
		self.task = threading.Thread(
			target=self._handle_completion, kwargs=completion_kw
		)
		self.task.start()
		log.debug(f"Task {self.task.ident} started")

	def on_stop_completion(self, event: wx.CommandEvent):
		"""Handle the stopping of the current completion task.

		Args:
			event: The event that triggered the stop action
		"""
		self._stop_completion = True

	def _handle_completion(self, engine: BaseEngine, **kwargs: dict[str, Any]):
		"""Handle the completion of a new message block.

		Args:
			engine: The engine to use for completion
			kwargs: The keyword arguments for the completion request
		"""
		try:
			play_sound("progress", loop=True)
			response = engine.completion(**kwargs)
		except Exception as e:
			log.error("Error during completion", exc_info=True)

			wx.CallAfter(
				wx.MessageBox,
				_("An error occurred during completion: ") + str(e),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			wx.CallAfter(self._end_task, False)
			return
		new_block = kwargs["new_block"]
		if kwargs.get("stream", False):
			new_block.response = Message(
				role=MessageRoleEnum.ASSISTANT, content=""
			)
			wx.CallAfter(self._pre_handle_completion_with_stream, new_block)
			for chunk in self.current_engine.completion_response_with_stream(
				response
			):
				if self._stop_completion or global_vars.app_should_exit:
					log.debug("Stopping completion")
					break
				if isinstance(chunk, str):
					new_block.response.content += chunk
					wx.CallAfter(self._handle_completion_with_stream, chunk)
				elif isinstance(chunk, tuple):
					chunk_type, chunk_data = chunk
					match chunk_type:
						case "citation":
							if not new_block.response.citations:
								new_block.response.citations = []
							new_block.response.citations.append(chunk_data)
						case _:
							log.warning(
								f"Unknown chunk type in streaming response: {chunk_type}"
							)
			wx.CallAfter(self._post_completion_with_stream, new_block)
		else:
			new_block = engine.completion_response_without_stream(
				response=response, **kwargs
			)
			wx.CallAfter(self._post_completion_without_stream, new_block)

	def _pre_handle_completion_with_stream(self, new_block: MessageBlock):
		"""Prepare for handling a completion response with streaming.

		Args:
			new_block: The new message block to be displayed
		"""
		self.conversation.messages.append(new_block)
		self.display_new_block(new_block)
		self.messages.SetInsertionPointEnd()
		self.prompt.Clear()
		self.attachment_files.clear()
		self.refresh_attachments_list()

	def _handle_completion_with_stream(self, chunk: str):
		"""Handle a completion response chunk for streaming.

		Args:
			chunk: The completion response chunk to be displayed
		"""
		self.stream_buffer += chunk
		# Flush buffer when encountering any of:
		# - newline (\n)
		# - punctuation marks (;:.?!)
		# - closing quotes/brackets (»"\]}])
		if re.match(RE_STREAM_BUFFER, self.stream_buffer):
			self._flush_stream_buffer()
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _handle_accessible_output(
		self, text: str, braille: bool = False, force: bool = False
	):
		if (
			(not force and not config.conf().conversation.use_accessible_output)
			or not isinstance(text, str)
			or not text.strip()
		):
			return
		if braille:
			try:
				accessible_output.braille(text)
			except Exception:
				log.error("Error during braille output", exc_info=True)
		try:
			accessible_output.speak(clear_for_speak(text))
		except Exception:
			log.error("Error during speech output", exc_info=True)

	def _handle_speech_stream_buffer(self, new_text: str = ''):
		"""Processes incoming speech stream text.

		If the input `new_text` is not a valid string or is empty, it forces flushing the current buffer to the accessible output handler.
		If `new_text` contains punctuation or newlines, it processes text up to the last
		occurrence, sends that portion to the output handler, and retains the remaining
		text in the buffer.

		Args:
			new_text (str): The new incoming text to process. If not a string or empty, the buffer is processed immediately.
		"""
		if not isinstance(new_text, str) or not new_text:
			if self.speech_stream_buffer:
				self._handle_accessible_output(self.speech_stream_buffer)
				self.speech_stream_buffer = ""
			return

		try:
			# Find the last occurrence of punctuation mark or newline
			matches = list(re.finditer(RE_SPEECH_STREAM_BUFFER, new_text))
			if matches:
				# Use the last match
				last_match = matches[-1]
				part_to_handle = (
					self.speech_stream_buffer + new_text[: last_match.end()]
				)
				remaining_text = new_text[last_match.end() :]

				if part_to_handle:
					self._handle_accessible_output(part_to_handle)

				# Update the buffer with the remaining text
				self.speech_stream_buffer = remaining_text.lstrip()
			else:
				# Concatenate new text to the buffer if no punctuation is found
				self.speech_stream_buffer += new_text
		except re.error as e:
			log.error(f"Regex error in _handle_speech_stream_buffer: {e}")
			# Fallback: treat the entire text as a single chunk
			self.speech_stream_buffer += new_text

	def _flush_stream_buffer(self):
		"""Flush the current speech stream buffer to the messages text control and accessible output handler."""
		pos = self.messages.GetInsertionPoint()
		text = self.stream_buffer
		if (
			self._speak_stream
			and (self.messages.HasFocus() or self.prompt.HasFocus())
			and self.GetTopLevelParent().IsShown()
		):
			self._handle_speech_stream_buffer(new_text=text)
		self.messages.AppendText(text)
		self.stream_buffer = ""
		self.messages.SetInsertionPoint(pos)

	def _update_last_segment_length(self):
		"""Update the length of the last message segment to match the current text control position."""
		last_position = self.messages.GetLastPosition()
		self.message_segment_manager.absolute_position = last_position
		last_segment = self.message_segment_manager.segments[-1]
		last_segment.length += last_position - self.message_segment_manager.end

	def _post_completion_with_stream(self, new_block: MessageBlock):
		"""Finalize the completion process for a streaming response.

		Args:
			new_block: The new message block to be displayed
		"""
		self._flush_stream_buffer()
		self._handle_speech_stream_buffer()
		self._update_last_segment_length()
		if config.conf().conversation.focus_history_after_send:
			self.messages.SetFocus()
		self._end_task()

	def _post_completion_without_stream(self, new_block: MessageBlock):
		"""Finalize the completion process for a non-streaming response.

		Args:
			new_block: The new message block to be displayed
		"""
		self.conversation.messages.append(new_block)
		self.display_new_block(new_block)
		self._handle_accessible_output(new_block.response.content)
		self.prompt.Clear()
		self.attachment_files.clear()
		self.refresh_attachments_list()
		if config.conf().conversation.focus_history_after_send:
			self.messages.SetFocus()
		self._end_task()

	def _end_task(self, success: bool = True):
		"""End the current completion task.

		Args:
			success: Whether the task completed successfully
		"""
		self.task.join()
		log.debug(f"Task {self.task.ident} ended")
		self.task = None
		stop_sound()
		if success:
			play_sound("chat_response_received")
		self.stop_completion_btn.Hide()
		self.submit_btn.Enable()
		self._stop_completion = False

	@ensure_no_task_running
	def generate_conversation_title(self):
		"""Generate a title for the conversation tab by using the AI model to analyze the conversation content.

		This method attempts to create a concise title by sending a predefined title generation prompt to the current AI model. It handles the title generation process, including error management and sound feedback.

		Returns:
			A generated conversation title if successful, or None if title generation fails.
		"""
		if not self.conversation.messages:
			return
		model = self.current_model
		if not model:
			return
		play_sound("progress", loop=True)
		try:
			new_block = MessageBlock(
				request=Message(
					role=MessageRoleEnum.USER, content=PROMPT_TITLE
				),
				provider_id=self.current_account.provider.id,
				model_id=model.id,
				temperature=self.temperature_spinner.GetValue(),
				top_p=self.top_p_spinner.GetValue(),
				max_tokens=self.max_tokens_spin_ctrl.GetValue(),
				stream=self.stream_mode.GetValue(),
			)
			engine = self.current_engine
			completion_kw = {
				"system_message": None,
				"conversation": self.conversation,
				"new_block": new_block,
				"stream": False,
			}
			response = engine.completion(**completion_kw)
			new_block = engine.completion_response_without_stream(
				response=response, **completion_kw
			)
			return new_block.response.content
		except Exception as e:
			wx.MessageBox(
				_("An error occurred during title generation:") + f" {e}",
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		finally:
			stop_sound()

	def save_conversation(self, file_path: str) -> bool:
		"""Save the current conversation to a specified file path.

		This method saves the current conversation to a file in JSON format. It handles the saving process, including error management and user feedback.

		Args:
			file_path: The target file path where the conversation will be saved.

		Returns:
		True if the conversation was successfully saved, False otherwise.
		"""
		log.debug(f"Saving conversation to {file_path}")
		try:
			self.conversation.save(file_path)
			return True
		except Exception as e:
			wx.MessageBox(
				_("An error occurred while saving the conversation: ") + str(e),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return False
