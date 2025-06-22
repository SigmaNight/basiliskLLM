"""Panel component for managing prompt input and attachments.

This module provides a reusable panel component that combines prompt input functionality
with attachment management. It can be used in different parts of the application
where these features are needed, such as conversation tabs and edit dialogs.
"""

from __future__ import annotations

import datetime
import logging
import re
import threading
from typing import TYPE_CHECKING, Callable, Optional

import wx
from httpx import HTTPError
from upath import UPath

import basilisk.config as config
from basilisk.conversation import (
	URL_PATTERN,
	AttachmentFile,
	ImageFile,
	build_from_url,
	get_mime_type,
	parse_supported_attachment_formats,
)
from basilisk.decorators import ensure_no_task_running

from .read_only_message_dialog import ReadOnlyMessageDialog

if TYPE_CHECKING:
	from basilisk.provider_ai_model import ProviderAIModel
	from basilisk.provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


class PromptAttachmentsPanel(wx.Panel):
	"""Panel component for managing prompt input and attachments.

	This panel combines a text input area for user prompts with attachment management
	functionality. It provides methods for adding, removing, and displaying attachments,
	as well as handling user input in the prompt area.

	Attributes:
		attachment_files: List of attachment files
		conv_storage_path: Path for storing conversation attachments
	"""

	def __init__(
		self,
		parent: wx.Window,
		conv_storage_path: UPath,
		on_submit_callback: Optional[Callable[[wx.CommandEvent], None]] = None,
	):
		"""Initialize the prompt and attachments panel.

		Args:
			parent: Parent window
			conv_storage_path: Path for storing conversation attachments
			on_submit_callback: Callback function for submit action (Ctrl+Enter)
		"""
		super().__init__(parent)

		self.attachment_files: list[AttachmentFile | ImageFile] = []
		self.conv_storage_path = conv_storage_path
		self.on_submit_callback = on_submit_callback
		self.task = None
		self.current_engine = None  # Will be set by the parent component
		self.init_ui()
		self.init_prompt_shortcuts()

	def init_ui(self):
		"""Initialize the user interface components."""
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Prompt input area
		prompt_label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt
			label=_("&Prompt:"),
		)
		sizer.Add(prompt_label, proportion=0, flag=wx.EXPAND)

		self.prompt = wx.TextCtrl(
			self,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		self.prompt.Bind(wx.EVT_KEY_DOWN, self.on_prompt_key_down)
		self.prompt.Bind(wx.EVT_CONTEXT_MENU, self.on_prompt_context_menu)
		self.prompt.Bind(wx.EVT_TEXT_PASTE, self.on_paste)
		sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		# Attachments list
		self.attachments_list_label = wx.StaticText(
			self,
			# Translators: This is a label for attachments
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
			# Translators: This is a label for attachment name
			_("Name"),
		)
		self.attachments_list.InsertColumn(
			1,
			# Translators: This is a label for attachment size
			_("Size"),
		)
		self.attachments_list.InsertColumn(
			2,
			# Translators: This is a label for attachment location
			_("Location"),
		)
		self.attachments_list.SetColumnWidth(0, 200)
		self.attachments_list.SetColumnWidth(1, 100)
		self.attachments_list.SetColumnWidth(2, 500)
		sizer.Add(self.attachments_list, proportion=0, flag=wx.ALL | wx.EXPAND)

		self.SetSizer(sizer)

		# Initially hide attachments section
		self.attachments_list_label.Hide()
		self.attachments_list.Hide()

	@property
	def selected_attachment_file(self) -> Optional[AttachmentFile | ImageFile]:
		"""Get the currently selected attachment file.

		Returns:
			The selected attachment file or None if no selection
		"""
		selected = self.attachments_list.GetFirstSelected()
		if selected == wx.NOT_FOUND:
			return None
		return self.attachment_files[selected]

	def set_engine(self, engine: BaseEngine):
		"""Set the current engine to use for attachment validation.

		Args:
			engine: The engine to use
		"""
		self.current_engine = engine

	def init_prompt_shortcuts(self):
		"""Initialize keyboard shortcuts for the prompt text control."""
		self.prompt_shortcuts = {
			(wx.MOD_CONTROL, wx.WXK_RETURN): self.on_submit_callback,
			(wx.MOD_CONTROL, wx.WXK_NUMPAD_ENTER): self.on_submit_callback,
		}
		if config.conf().conversation.shift_enter_mode:
			self.prompt_shortcuts.update(
				{
					(wx.MOD_NONE, wx.WXK_RETURN): self.on_submit_callback,
					(wx.MOD_NONE, wx.WXK_NUMPAD_ENTER): self.on_submit_callback,
				}
			)
		previous_prompt = getattr(
			self.GetParent(), "insert_previous_prompt", None
		)
		if previous_prompt:
			self.prompt_shortcuts[(wx.MOD_CONTROL, wx.WXK_UP)] = previous_prompt

	def on_prompt_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the prompt text control.

		Args:
			event: The keyboard event
		"""
		shortcut = (event.GetModifiers(), event.GetKeyCode())
		action = self.prompt_shortcuts.get(shortcut, lambda e: e.Skip())
		action(event)

	def on_prompt_context_menu(self, event: wx.ContextMenuEvent):
		"""Display context menu for the prompt text control.

		Args:
			event: The context menu trigger event
		"""
		menu = wx.Menu()

		if self.on_submit_callback:
			item = wx.MenuItem(menu, wx.ID_ANY, _("Submit") + " (Ctrl+Enter)")
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_submit_callback, item)

		item = wx.MenuItem(
			menu, wx.ID_ANY, _("Paste (file or text)") + "	Ctrl+V"
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_paste, item)

		# Add standard edit items
		self.add_standard_context_menu_items(menu, include_paste=False)
		self.prompt.PopupMenu(menu)
		menu.Destroy()

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

	def on_attachments_context_menu(self, event: wx.ContextMenuEvent):
		"""Display context menu for the attachments list.

		Args:
			event: The context menu trigger event
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
				# Translators: This is a label for remove selected attachment in the context menu
				_("Remove selected attachment") + "	Shift+Del",
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
		self.Bind(wx.EVT_MENU, self.on_paste, item)

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
			# Translators: This is a label for add attachment URL in the context menu
			_("Add attachment URL...") + "	Ctrl+U",
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.add_attachment_url_dlg, item)

		self.attachments_list.PopupMenu(menu)
		menu.Destroy()

	def on_attachments_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts for the attachments list.

		Args:
			event: The keyboard event
		"""
		shortcut = (event.GetModifiers(), event.GetKeyCode())
		shortcuts_map = {
			(wx.MOD_CONTROL, ord("C")): self.on_copy_attachment_location,
			(wx.MOD_CONTROL, ord("V")): self.on_paste,
			(wx.MOD_NONE, wx.WXK_DELETE): self.on_attachments_remove,
			(wx.MOD_NONE, wx.WXK_RETURN): self.on_show_attachment_details,
			(wx.MOD_NONE, wx.WXK_NUMPAD_ENTER): self.on_show_attachment_details,
		}

		action = shortcuts_map.get(shortcut, lambda e: e.Skip())
		action(event)

	def on_paste(self, event: wx.CommandEvent):
		"""Handle pasting content from the clipboard.

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
					log.info("Pasting URL from clipboard, adding attachment")
					self.add_attachment_url_thread(text)
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
		"""Open a file dialog to select and add files.

		Args:
			event: Event triggered by the add files action
		"""
		if not self.current_engine:
			wx.MessageBox(
				_("No engine available. Please select an account."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

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
			# Translators: This is a label for select files dialog
			message=_("Select one or more files to attach"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
			wildcard=wildcard,
		)

		if file_dialog.ShowModal() == wx.ID_OK:
			paths = file_dialog.GetPaths()
			self.add_attachments(paths)

		file_dialog.Destroy()

	def add_attachment_url_dlg(self, event: wx.CommandEvent = None):
		"""Open a dialog to input an attachment URL.

		Args:
			event: Event triggered by the add attachment URL action
		"""
		url_dialog = wx.TextEntryDialog(
			self,
			# Translators: This is a label for enter URL in add attachment dialog
			message=_("Enter the URL of the file to attach:"),
			caption=_("Add attachment from URL"),
		)

		if url_dialog.ShowModal() != wx.ID_OK:
			url_dialog.Destroy()
			return

		url = url_dialog.GetValue()
		url_dialog.Destroy()

		if not url:
			return

		if not re.fullmatch(URL_PATTERN, url):
			wx.MessageBox(
				_("Invalid URL format."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return

		self.add_attachment_url_thread(url)

	def add_attachment_from_url(self, url: str):
		"""Add an attachment from a URL.

		Args:
			url: The URL of the file to attach
		"""
		attachment_file = None
		try:
			attachment_file = build_from_url(url)
		except HTTPError as err:
			wx.CallAfter(
				wx.MessageBox,
				# Translators: This message is displayed when an HTTP error occurs while adding a file from a URL.
				_("HTTP error %s.") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		except Exception as err:
			if isinstance(err, (KeyboardInterrupt, SystemExit)):
				raise
			log.error(err, exc_info=True)
			wx.CallAfter(
				wx.MessageBox,
				# Translators: This message is displayed when an error occurs while adding a file from a URL.
				_("Error adding attachment from URL: %s") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		wx.CallAfter(self.add_attachments, [attachment_file])
		self.task = None

	@ensure_no_task_running
	def add_attachment_url_thread(self, url: str):
		"""Start a thread to add an attachment from a URL.

		Args:
			url: The URL of the file to attach
		"""
		self.task = threading.Thread(
			target=self.add_attachment_from_url, args=(url,)
		)
		self.task.start()

	def on_show_attachment_details(self, event: wx.CommandEvent):
		"""Show details of the selected attachment.

		Args:
			event: Event triggered by the show attachment details action
		"""
		current_attachment = self.selected_attachment_file
		if not current_attachment:
			return

		details = {
			_("Name"): current_attachment.name,
			_("Size"): current_attachment.display_size,
			_("Location"): str(current_attachment.location),
		}

		mime_type = current_attachment.mime_type
		if mime_type:
			details[_("MIME type")] = mime_type
			if mime_type.startswith("image/"):
				details[_("Dimensions")] = current_attachment.display_dimensions

		details_str = "\n".join(
			_("%s: %s") % (k, v) for k, v in details.items()
		)

		ReadOnlyMessageDialog(
			self, _("Attachment details"), details_str
		).ShowModal()

	def on_attachments_remove(self, event: wx.CommandEvent):
		"""Remove the selected attachment.

		Args:
			event: Event triggered by the remove attachment action
		"""
		selection = self.attachments_list.GetFirstSelected()
		current_attachment = self.selected_attachment_file
		if not current_attachment:
			return

		self.attachment_files.remove(current_attachment)
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
		current_attachment = self.selected_attachment_file
		if not current_attachment:
			return

		location = f'"{current_attachment.location}"'
		with wx.TheClipboard as clipboard:
			clipboard.SetData(wx.TextDataObject(location))

	def refresh_attachments_list(self):
		"""Update the attachments list display."""
		self.attachments_list.DeleteAllItems()

		if not self.attachment_files:
			self.attachments_list_label.Hide()
			self.attachments_list.Hide()
			if getattr(self.Parent, "ocr_button", None):
				self.Parent.ocr_button.Hide()
			self.Parent.Layout()
			return

		self.attachments_list_label.Show()
		self.attachments_list.Show()
		if getattr(self.Parent, "ocr_button", None):
			self.Parent.ocr_button.Show()
		for attachment in self.attachment_files:
			self.attachments_list.Append(attachment.get_display_info())

		last_index = len(self.attachment_files) - 1
		self.attachments_list.SetItemState(
			last_index, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
		)
		self.attachments_list.EnsureVisible(last_index)
		self.Parent.Layout()

	def add_attachments(self, paths: list[str | AttachmentFile | ImageFile]):
		"""Add one or more attachments.

		Args:
			paths: List of attachment file paths or attachment objects
		"""
		log.debug("Adding attachments: %s", paths)

		if not self.current_engine:
			wx.MessageBox(
				_("No engine available. Please select an account."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

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

	@property
	def prompt_text(self) -> str:
		"""Get the prompt text.

		Returns:
			The text from the prompt input control
		"""
		return self.prompt.GetValue()

	@prompt_text.setter
	def prompt_text(self, text: str):
		"""Set the prompt text.

		Args:
			text: The text to set in the prompt input control
		"""
		self.prompt.SetValue(text)

	def set_prompt(self, text: str):
		"""Set the prompt text.

		Args:
			text: The text to set in the prompt input control
		"""
		self.prompt.SetValue(text)

	def clear(self, refresh: bool = False):
		"""Clear the prompt text and remove all attachments.

		Args:
			refresh: Whether to refresh the attachments list after clearing the prompt.
		"""
		self.prompt.Clear()
		self.attachment_files = list()
		if not refresh:
			return
		self.refresh_attachments_list()

	def has_image_attachments(self) -> bool:
		"""Check if there are image attachments.

		Returns:
			True if there are image attachments, False otherwise
		"""
		return any(
			attachment.mime_type.startswith("image/")
			for attachment in self.attachment_files
		)

	def check_attachments_valid(self) -> bool:
		"""Check if all attachments are valid for the current engine.

		Returns:
			True if all attachments are valid, False otherwise
		"""
		if not self.current_engine:
			return False

		supported_attachment_formats = (
			self.current_engine.supported_attachment_formats
		)

		invalid_found = False
		attachments_copy = self.attachment_files[:]

		for attachment in attachments_copy:
			if attachment.mime_type not in supported_attachment_formats:
				msg = (
					_(
						"This attachment format is not supported by the current provider. Source: %s"
					)
					% attachment.location
					if attachment.mime_type not in supported_attachment_formats
					else _("The attachment file does not exist: %s")
					% attachment.location
				)
				wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)
				invalid_found = True

		return not invalid_found

	def set_prompt_focus(self):
		"""Set focus to the prompt input control."""
		self.prompt.SetFocus()

	def set_attachments_focus(self):
		"""Set focus to the attachments list control."""
		if not self.attachment_files:
			self.prompt.SetFocus()
			return
		self.attachments_list.SetFocus()

	def resize_all_attachments(self):
		"""Resize all image attachments if configured to do so."""
		if not config.conf().images.resize:
			return
		for attachment in self.attachment_files:
			if not attachment.mime_type.startswith("image/"):
				continue
			try:
				attachment.resize(
					self.conv_storage_path,
					config.conf().images.max_width,
					config.conf().images.max_height,
					config.conf().images.quality,
				)
			except Exception as e:
				log.error(
					"Error resizing image attachment %s: %s",
					attachment.location,
					e,
					exc_info=True,
				)
				continue

	def ensure_model_compatibility(
		self, current_model: ProviderAIModel | None
	) -> ProviderAIModel | None:
		"""Check if current model is compatible with requested operations.

		Returns:
			The current model if compatible, None otherwise
		"""
		if not current_model:
			wx.MessageBox(
				_("Please select a model"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return None
		if self.has_image_attachments() and not current_model.vision:
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
		return current_model
