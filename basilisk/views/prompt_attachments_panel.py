"""Panel component for managing prompt input and attachments.

This module provides a reusable panel component that combines prompt input functionality
with attachment management. It can be used in different parts of the application
where these features are needed, such as conversation tabs and edit dialogs.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Callable, Optional

import wx
from upath import UPath

import basilisk.config as config
from basilisk.conversation import AttachmentFile, ImageFile
from basilisk.presenters.attachment_panel_presenter import (
	PromptAttachmentPresenter,
)

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

	The panel is a thin view: business logic lives in
	:class:`~basilisk.presenters.attachment_panel_presenter.PromptAttachmentPresenter`.
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
		self.on_submit_callback = on_submit_callback
		self.presenter = PromptAttachmentPresenter(
			view=self, conv_storage_path=conv_storage_path
		)
		self.init_ui()
		self.init_prompt_shortcuts()

	# ------------------------------------------------------------------
	# UI setup
	# ------------------------------------------------------------------

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

	# ------------------------------------------------------------------
	# Delegation to presenter (public API used by ConversationPresenter)
	# ------------------------------------------------------------------

	@property
	def attachment_files(self) -> list[AttachmentFile | ImageFile]:
		"""Get the attachment list from the presenter.

		Returns:
			The list of current attachments.
		"""
		return self.presenter.attachment_files

	@attachment_files.setter
	def attachment_files(self, value: list[AttachmentFile | ImageFile]) -> None:
		"""Set the attachment list on the presenter.

		Args:
			value: New list of attachments.
		"""
		self.presenter.attachment_files = value

	def set_engine(self, engine: BaseEngine) -> None:
		"""Set the current engine on the presenter.

		Args:
			engine: The engine to use.
		"""
		self.presenter.set_engine(engine)

	def check_attachments_valid(self) -> bool:
		"""Delegate to presenter.

		Returns:
			True if all attachments are valid.
		"""
		return self.presenter.check_attachments_valid()

	def ensure_model_compatibility(
		self, current_model: ProviderAIModel | None
	) -> ProviderAIModel | None:
		"""Delegate to presenter.

		Args:
			current_model: The selected AI model.

		Returns:
			The model if compatible, None otherwise.
		"""
		return self.presenter.ensure_model_compatibility(current_model)

	def resize_all_attachments(self) -> None:
		"""Delegate to presenter."""
		self.presenter.resize_all_attachments()

	def has_image_attachments(self) -> bool:
		"""Delegate to presenter.

		Returns:
			True if any attachment is an image.
		"""
		return self.presenter.has_image_attachments()

	def add_attachments(
		self, paths: list[str | AttachmentFile | ImageFile]
	) -> None:
		"""Add one or more attachments via the presenter.

		Args:
			paths: List of file paths (str) or attachment objects.
		"""
		self.presenter.add_attachments(paths)

	def refresh_attachments_list(self) -> None:
		"""Push current presenter state to the list widget."""
		self.presenter.refresh_view()

	def clear(self, refresh: bool = False) -> None:
		"""Clear the prompt text and remove all attachments.

		Args:
			refresh: Whether to refresh the attachments display after clearing.
		"""
		self.prompt.Clear()
		self.presenter.clear()
		if refresh:
			self.refresh_attachments_display(self.presenter.attachment_files)

	# ------------------------------------------------------------------
	# View interface (called by the presenter)
	# ------------------------------------------------------------------

	def show_error(self, msg: str) -> None:
		"""Show an error message box.

		Args:
			msg: The error message to display.
		"""
		wx.MessageBox(msg, _("Error"), wx.OK | wx.ICON_ERROR)

	def show_file_dialog(self, wildcard: str) -> list[str] | None:
		"""Show a file-picker dialog and return selected paths.

		Args:
			wildcard: File type filter string.

		Returns:
			List of selected file paths, or None if cancelled.
		"""
		file_dialog = wx.FileDialog(
			self,
			# Translators: This is a label for select files dialog
			message=_("Select one or more files to attach"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
			wildcard=wildcard,
		)
		paths = None
		if file_dialog.ShowModal() == wx.ID_OK:
			paths = file_dialog.GetPaths()
		file_dialog.Destroy()
		return paths

	def show_url_dialog(self) -> str | None:
		"""Show a URL entry dialog and return the entered URL.

		Returns:
			The URL string entered by the user, or None if cancelled/empty.
		"""
		url_dialog = wx.TextEntryDialog(
			self,
			# Translators: This is a label for enter URL in add attachment dialog
			message=_("Enter the URL of the file to attach:"),
			caption=_("Add attachment from URL"),
		)
		url = None
		if url_dialog.ShowModal() == wx.ID_OK:
			url = url_dialog.GetValue() or None
		url_dialog.Destroy()
		return url

	def refresh_attachments_display(
		self, files: list[AttachmentFile | ImageFile]
	) -> None:
		"""Update the attachments list widget and show/hide it.

		Args:
			files: The current list of attachment objects.
		"""
		self.attachments_list.DeleteAllItems()

		if not files:
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
		for attachment in files:
			self.attachments_list.Append(attachment.get_display_info())

		last_index = len(files) - 1
		self.attachments_list.SetItemState(
			last_index, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
		)
		self.attachments_list.EnsureVisible(last_index)
		self.Parent.Layout()

	def write_prompt_text(self, text: str) -> None:
		"""Insert text at the current position and focus the prompt.

		Args:
			text: The text to insert.
		"""
		self.prompt.WriteText(text)
		self.prompt.SetFocus()

	def get_prompt_text(self) -> str:
		"""Return the current prompt text.

		Returns:
			The text in the prompt control.
		"""
		return self.prompt.GetValue()

	def focus_attachments(self) -> None:
		"""Set focus to the attachments list."""
		self.attachments_list.SetFocus()

	def get_clipboard_bitmap_image(self):
		"""Read a bitmap from the clipboard and return it as a wx.Image.

		Returns:
			A wx.Image if the clipboard contains a bitmap, None otherwise.
		"""
		with wx.TheClipboard as clipboard:
			if not clipboard.IsSupported(wx.DataFormat(wx.DF_BITMAP)):
				return None
			bitmap_data = wx.BitmapDataObject()
			success = clipboard.GetData(bitmap_data)
			if not success:
				return None
			return bitmap_data.GetBitmap().ConvertToImage()

	# ------------------------------------------------------------------
	# Prompt properties
	# ------------------------------------------------------------------

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

	def set_prompt_focus(self):
		"""Set focus to the prompt input control."""
		self.prompt.SetFocus()

	def set_attachments_focus(self):
		"""Set focus to the attachments list control."""
		if not self.presenter.attachment_files:
			self.prompt.SetFocus()
			return
		self.attachments_list.SetFocus()

	# ------------------------------------------------------------------
	# Selected attachment helper
	# ------------------------------------------------------------------

	@property
	def selected_attachment_file(self) -> Optional[AttachmentFile | ImageFile]:
		"""Get the currently selected attachment file.

		Returns:
			The selected attachment file or None if no selection
		"""
		selected = self.attachments_list.GetFirstSelected()
		if selected == wx.NOT_FOUND:
			return None
		return self.presenter.attachment_files[selected]

	# ------------------------------------------------------------------
	# Event handlers — prompt area
	# ------------------------------------------------------------------

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
			menu, wx.ID_ANY, _("Paste (file or text)") + "\tCtrl+V"
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

	# ------------------------------------------------------------------
	# Event handlers — attachments list
	# ------------------------------------------------------------------

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
				_("Show details") + "\tEnter",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_show_attachment_details, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for remove selected attachment in the context menu
				_("Remove selected attachment") + "\tShift+Del",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_attachments_remove, item)

			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				# Translators: This is a label for copy location in the context menu
				_("Copy location") + "\tCtrl+C",
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_copy_attachment_location, item)

		item = wx.MenuItem(
			menu,
			wx.ID_ANY,
			# Translators: This is a label for paste in the context menu
			_("Paste (file or text)") + "\tCtrl+V",
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
			_("Add attachment URL...") + "\tCtrl+U",
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

		Reads clipboard data and routes to the appropriate presenter
		handler based on data format.

		Args:
			event: The clipboard paste event
		"""
		with wx.TheClipboard as clipboard:
			if clipboard.IsSupported(wx.DataFormat(wx.DF_FILENAME)):
				log.debug("Pasting files from clipboard")
				file_data = wx.FileDataObject()
				clipboard.GetData(file_data)
				paths = file_data.GetFilenames()
				self.presenter.on_paste_files(paths)
			elif clipboard.IsSupported(wx.DataFormat(wx.DF_TEXT)):
				log.debug("Pasting text from clipboard")
				text_data = wx.TextDataObject()
				clipboard.GetData(text_data)
				text = text_data.GetText()
				self.presenter.on_paste_text(text)
			elif clipboard.IsSupported(wx.DataFormat(wx.DF_BITMAP)):
				log.debug("Pasting bitmap from clipboard")
				bitmap_data = wx.BitmapDataObject()
				success = clipboard.GetData(bitmap_data)
				if not success:
					log.error("Failed to get bitmap data from clipboard")
					return
				img = bitmap_data.GetBitmap().ConvertToImage()
				self.presenter.on_paste_bitmap(img)
			else:
				log.info("Unsupported clipboard data")

	def add_attachments_dlg(self, event: wx.CommandEvent = None):
		"""Open a file dialog to select and add files.

		Args:
			event: Event triggered by the add files action
		"""
		self.presenter.on_add_files()

	def add_attachment_url_dlg(self, event: wx.CommandEvent = None):
		"""Open a dialog to input an attachment URL.

		Args:
			event: Event triggered by the add attachment URL action
		"""
		self.presenter.on_add_url()

	# ------------------------------------------------------------------
	# Attachment item actions
	# ------------------------------------------------------------------

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

		self.presenter.attachment_files.remove(current_attachment)
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
