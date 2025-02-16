"""Custom text control for displaying conversation history.

This module provides a custom text control for displaying conversation history in the Basilisk GUI. It extends the wx.TextCtrl class to provide specialized functionality for handling conversation message history, including message navigation, search capabilities, and accessibility features.
"""

from __future__ import annotations

import logging
import os
import re
import weakref
from functools import partial
from typing import TYPE_CHECKING

import wx

import basilisk.config as config
from basilisk.accessible_output import clear_for_speak, get_accessible_output
from basilisk.conversation.conversation_model import (
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.gui.search_dialog import SearchDialog, SearchDirection
from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)

if TYPE_CHECKING:
	from .conversation_tab import ConversationTab

logger = logging.getLogger(__name__)

COMMON_PATTERN = r"[\n;:.?!)»\"\]}]"
RE_STREAM_BUFFER = re.compile(rf".*{COMMON_PATTERN}.*")
RE_SPEECH_STREAM_BUFFER = re.compile(rf"{COMMON_PATTERN}")


class HistoryMsgTextCtrl(wx.TextCtrl):
	"""A custom text control for displaying conversation history.

	This class extends wx.TextCtrl to provide specialized functionality for
	handling conversation message history, including message navigation,
	search capabilities, and accessibility features.
	"""

	def __init__(
		self, parent: ConversationTab, size: tuple[int, int] = (800, 400)
	):
		"""Initialize the history message text control.

		Args:
			parent: Parent window
			size: Initial size of the control
		"""
		super().__init__(
			parent,
			size=size,
			style=wx.TE_MULTILINE
			| wx.TE_READONLY
			| wx.TE_WORDWRAP
			| wx.HSCROLL,
		)

		self.segment_manager = MessageSegmentManager()
		self._search_dialog = None
		self._speak_stream = True
		self.accessible_output = get_accessible_output()
		self.stream_buffer = ""
		self.speech_stream_buffer = ""
		self._speak_stream = True
		self.init_role_labels()
		self.init_menu_msg_info()
		self.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

	def init_role_labels(self):
		"""Initialize role labels for conversation messages.

		Uses the default role labels from the MessageRoleEnum, and optionally replaces them with custom labels from the system configuration.
		"""
		self.role_labels = MessageRoleEnum.get_labels()
		if label := config.conf().conversation.role_label_user:
			self.role_labels[MessageRoleEnum.USER] = label
		if label := config.conf().conversation.role_label_assistant:
			self.role_labels[MessageRoleEnum.ASSISTANT] = label

	def Clear(self):
		"""Clear the conversation text control."""
		super().Clear()
		self.segment_manager.clear()

	def append_text_and_segment(
		self,
		new_block_ref: weakref.ref[MessageBlock],
		absolute_length: int,
		text: str,
		segment_type: MessageSegmentType,
	) -> int:
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
		self.AppendText(text)
		last_pos = self.GetLastPosition()
		relative_length = last_pos - absolute_length
		self.segment_manager.append(
			MessageSegment(
				length=relative_length,
				kind=segment_type,
				message_block=new_block_ref,
			)
		)
		return last_pos

	append_prefix = partial(
		append_text_and_segment, segment_type=MessageSegmentType.PREFIX
	)

	append_content = partial(
		append_text_and_segment, segment_type=MessageSegmentType.CONTENT
	)

	append_suffix = partial(
		append_text_and_segment,
		text=os.linesep,
		segment_type=MessageSegmentType.SUFFIX,
	)

	def display_new_block(self, new_block: MessageBlock):
		"""Displays a new message block in the conversation text control.

		This method appends a new message block to the existing conversation, handling both request and response messages. It manages the formatting and segmentation of messages, including role labels and content.

		Notes:
		- Handles empty and non-empty message text controls
		- Supports configurable role labels from system configuration
		- Uses weak references to track message blocks
		- Preserves the original insertion point after displaying the block
		- Supports both request and optional response messages

		Args:
			new_block: The message block to be displayed in the conversation.
		"""
		absolute_length = self.GetLastPosition()
		new_block_ref = weakref.ref(new_block)
		if not self.IsEmpty():
			absolute_length = self.append_suffix(
				self, new_block_ref, absolute_length
			)
		absolute_length = self.append_prefix(
			self,
			new_block_ref,
			absolute_length,
			self.role_labels[MessageRoleEnum.USER],
		)
		absolute_length = self.append_content(
			self, new_block_ref, absolute_length, new_block.request.content
		)
		absolute_length = self.append_suffix(
			self, new_block_ref, absolute_length
		)
		pos = self.GetInsertionPoint()
		if new_block.response:
			absolute_length = self.append_prefix(
				self,
				new_block_ref,
				absolute_length,
				self.role_labels[MessageRoleEnum.ASSISTANT],
			)
			absolute_length = self.append_content(
				self, new_block_ref, absolute_length, new_block.response.content
			)
		self.SetInsertionPoint(pos)

	def update_last_segment_length(self):
		"""Update the length of the last message segment to match the current text control position."""
		last_position = self.GetLastPosition()
		self.segment_manager.absolute_position = last_position
		last_segment = self.segment_manager.segments[-1]
		last_segment.length += last_position - self.segment_manager.end

	def init_menu_msg_info(self):
		"""Initialize the message operations menu items.

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
		"""
		self.msg_menu_info = (
			(
				_("Read current message"),
				"(space)",
				self.on_read_current_message,
			),
			(
				_("Speak stream"),
				"(Shift+Space)",
				self.on_toggle_speak_stream,
				self._speak_stream,
			),
			(_("Show as HTML (from Markdown)"), "(&h)", self.on_show_as_html),
			(_("Copy current message"), "(&c)", self.on_copy_message),
			(
				_("Select current message"),
				"(&s)",
				self.on_select_current_message,
			),
			(_("Go to previous message"), "(&j)", self.go_to_previous_message),
			(_("Go to next message"), "(&k)", self.go_to_next_message),
			(
				_("Move to start of message"),
				"(&b)",
				self.move_to_start_of_message,
			),
			(_("Move to end of message"), "(&n)", self.move_to_end_of_message),
			(
				_("Remove message block"),
				"(Shift+Del)",
				self.on_remove_message_block,
			),
			(_("Find..."), "(&f)", self.on_search),
			(_("Find Next"), "(F3)", self.on_search_next),
			(_("Find Previous"), "(Shift+F3)", self.on_search_previous),
		)

	def on_context_menu(self, event: wx.ContextMenuEvent):
		"""Display the context menu.

		Args:
			event: The context menu event
		"""
		menu = wx.Menu()
		if self.GetValue():
			self._add_message_operations_menu_items(menu)
			menu.AppendSeparator()

		self._add_standard_menu_items(menu)
		self.PopupMenu(menu)
		menu.Destroy()

	def _add_message_operations_menu_items(self, menu):
		"""Add message operation items to the context menu.

		Args:
			menu: The menu to add items to
		"""
		for label, shortcut, handler, *args in self.msg_menu_info:
			is_checkable = bool(args and args[0])
			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				f"{label} {shortcut}",
				kind=wx.ITEM_CHECK if is_checkable else wx.ITEM_NORMAL,
			)
			menu.Append(item)
			if is_checkable:
				item.Check(self._speak_stream)
			self.Bind(wx.EVT_MENU, handler, item)

	def _add_standard_menu_items(self, menu):
		"""Add standard edit menu items.

		Args:
			menu: The menu to add items to
		"""
		menu.Append(wx.ID_UNDO)
		menu.Append(wx.ID_REDO)
		menu.Append(wx.ID_CUT)
		menu.Append(wx.ID_COPY)
		menu.Append(wx.ID_SELECTALL)

	# Navigation methods
	def navigate_message(self, previous: bool):
		"""Navigate to the previous or next message.

		Args:
			previous: If True, navigate to previous message, else next message
		"""
		self.segment_manager.absolute_position = self.GetInsertionPoint()
		try:
			if previous:
				self.segment_manager.previous(MessageSegmentType.CONTENT)
			else:
				self.segment_manager.next(MessageSegmentType.CONTENT)
		except IndexError:
			wx.Bell()
			return
		try:
			pos = self.segment_manager.start
		except IndexError:
			wx.Bell()
		else:
			self.SetInsertionPoint(pos)
			if config.conf().conversation.nav_msg_select:
				self.on_select_current_message()
			else:
				current_msg = self.GetRange(*self.current_msg_range)
				self.handle_accessible_output(current_msg)

	def go_to_previous_message(self, event=None):
		"""Navigate to the previous message."""
		self.navigate_message(True)

	def go_to_next_message(self, event=None):
		"""Navigate to the next message."""
		self.navigate_message(False)

	@property
	def current_msg_range(self) -> tuple[int, int]:
		"""Get the range of the current message.

		Returns:
			Tuple of (start, end) positions
		"""
		self.segment_manager.absolute_position = self.GetInsertionPoint()
		self.segment_manager.focus_content_block()
		return (self.segment_manager.start, self.segment_manager.end)

	@property
	def current_msg_content(self) -> str:
		"""Get the content of the current message.

		Returns:
			The content of the current message
		"""
		return self.GetRange(*self.current_msg_range)

	def on_select_current_message(self, event: wx.Event | None = None):
		"""Select the current message."""
		self.SetSelection(*self.current_msg_range)

	def on_copy_message(self, event=None):
		"""Copy the current message to clipboard."""
		cursor_pos = self.GetInsertionPoint()
		self.on_select_current_message()
		self.Copy()
		self.SetInsertionPoint(cursor_pos)
		self.handle_accessible_output(
			_("Message copied to clipboard"), braille=True
		)

	def move_to_start_of_message(self, event=None):
		"""Move cursor to start of current message."""
		cursor_pos = self.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		self.segment_manager.focus_content_block()
		self.SetInsertionPoint(self.segment_manager.start)
		self.handle_accessible_output(_("Start of message"))

	def move_to_end_of_message(self, event=None):
		"""Move cursor to end of current message."""
		cursor_pos = self.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		self.segment_manager.focus_content_block()
		self.SetInsertionPoint(self.segment_manager.end - 1)
		self.handle_accessible_output(_("End of message"))

	def _do_search(self, direction: SearchDirection = SearchDirection.FORWARD):
		"""Open the search dialog.

		Args:
			direction: Search direction
		"""
		if not self._search_dialog:
			self._search_dialog = SearchDialog(self.GetParent(), self)
		self._search_dialog._dir_radio_forward.SetValue(
			direction == SearchDirection.FORWARD
		)
		self._search_dialog._dir_radio_backward.SetValue(
			direction == SearchDirection.BACKWARD
		)
		self._search_dialog._search_combo.SetFocus()
		self._search_dialog._search_combo.SelectAll()
		self._search_dialog.ShowModal()

	def on_search(self, event: wx.Event | None):
		"""Handle search command."""
		self._do_search()

	def on_search_previous(self, event: wx.Event | None):
		"""Search for previous occurrence."""
		if not self._search_dialog:
			return self._do_search(SearchDirection.BACKWARD)
		self._search_dialog.search_previous()

	def on_search_next(self, event: wx.Event | None):
		"""Search for next occurrence."""
		if not self._search_dialog:
			return self._do_search()
		self._search_dialog.search_next()

	def on_toggle_speak_stream(self, event: wx.Event | None):
		"""Toggle stream speaking mode."""
		if event:
			return wx.CallLater(500, self.on_toggle_speak_stream)
		self._speak_stream = not self._speak_stream
		self.handle_accessible_output(
			_("Stream speaking %s")
			% (_("enabled") if self._speak_stream else _("disabled")),
			braille=True,
		)

	def on_read_current_message(self, event: wx.Event | None):
		"""Read the current message."""
		if event:
			return wx.CallLater(500, self.on_read_current_message)
		self.handle_accessible_output(self.current_msg_content, force=True)

	def on_show_as_html(self, event: wx.Event | None):
		"""Show current message as HTML."""
		from .html_view_window import show_html_view_window

		show_html_view_window(
			self.GetParent(), self.current_msg_content, "markdown"
		)

	def handle_accessible_output(
		self, text: str, braille: bool = False, force: bool = False
	):
		"""Handle accessible output for screen readers.

		Args:
			text: Text to output
			braille: Whether to use braille output
			force: Whether to force output
		"""
		if (
			(not force and config.conf().conversation.use_accessible_output)
			or not isinstance(text, str)
			or not text.strip()
		):
			return
		if braille:
			try:
				self.accessible_output.braille(text)
			except Exception as e:
				logger.error(
					"Failed to output text to braille display", exc_info=e
				)
		try:
			self.accessible_output.speak(clear_for_speak(text))
		except Exception as e:
			logger.error("Failed to output text to screen reader", exc_info=e)

	def handle_speech_stream_buffer(self, new_text: str = ''):
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
				self.handle_accessible_output(self.speech_stream_buffer)
				self.speech_stream_buffer = ""
			return

		try:
			# Find the last occurrence of punctuation mark or newline
			matches = list(RE_SPEECH_STREAM_BUFFER.finditer(new_text))
			if matches:
				# Use the last match
				last_match = matches[-1]
				part_to_handle = (
					self.speech_stream_buffer + new_text[: last_match.end()]
				)
				remaining_text = new_text[last_match.end() :]

				if part_to_handle:
					self.handle_accessible_output(part_to_handle)

				# Update the buffer with the remaining text
				self.speech_stream_buffer = remaining_text.lstrip()
			else:
				# Concatenate new text to the buffer if no punctuation is found
				self.speech_stream_buffer += new_text
		except re.error as e:
			logger.error(f"Regex error in _handle_speech_stream_buffer: {e}")
			# Fallback: treat the entire text as a single chunk
			self.speech_stream_buffer += new_text

	def flush_stream_buffer(self):
		"""Flush the current speech stream buffer to the messages text control and accessible output handler."""
		pos = self.GetInsertionPoint()
		text = self.stream_buffer
		if (
			self._speak_stream
			and (self.HasFocus() or self.GetParent().prompt.HasFocus())
			and self.GetTopLevelParent().IsShown()
		):
			self.handle_speech_stream_buffer(new_text=text)
		self.AppendText(text)
		self.stream_buffer = ""
		self.SetInsertionPoint(pos)

	def append_stream_chunk(self, text: str):
		"""Append a chunk of text to the speech stream buffer.

		Args:
			text: The text chunk to append
		"""
		self.stream_buffer += text
		# Flush buffer when encountering any of:
		# - newline (\n)
		# - punctuation marks (;:.?!)
		# - closing quotes/brackets (»"\]}])
		if RE_STREAM_BUFFER.match(self.stream_buffer):
			self.flush_stream_buffer()

	def on_remove_message_block(self, event: wx.CommandEvent | None = None):
		"""Remove the current message block from the conversation.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		block = self.segment_manager.current_segment.message_block()
		if block:
			self.GetParent().remove_message_block(block)
			self.SetInsertionPoint(cursor_pos)
			self.handle_accessible_output(
				_("Message block removed"), braille=True
			)
		else:
			wx.Bell()

	# goes here because with need all the methods to be defined before we can assign to the dict
	key_actions = {
		(wx.MOD_SHIFT, wx.WXK_SPACE): on_toggle_speak_stream,
		(wx.MOD_NONE, wx.WXK_SPACE): on_read_current_message,
		(wx.MOD_NONE, ord('J')): go_to_previous_message,
		(wx.MOD_NONE, ord('K')): go_to_next_message,
		(wx.MOD_NONE, ord('S')): on_select_current_message,
		(wx.MOD_NONE, ord('H')): on_show_as_html,
		(wx.MOD_NONE, ord('C')): on_copy_message,
		(wx.MOD_NONE, ord('B')): move_to_start_of_message,
		(wx.MOD_NONE, ord('N')): move_to_end_of_message,
		(wx.MOD_SHIFT, wx.WXK_DELETE): on_remove_message_block,
		(wx.MOD_NONE, wx.WXK_F3): on_search_next,
		(wx.MOD_NONE, ord('F')): on_search,
		(wx.MOD_CONTROL, ord('F')): on_search,
		(wx.MOD_SHIFT, wx.WXK_F3): on_search_previous,
	}

	def on_key_down(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts.

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
		- Shift+Delete: Remove current message block
		- F3: Search in messages (forward)
		- Shift+F3: Search in messages (backward)
		- Ctrl+F: open Search in messages dialog

		Args:
			event: The keyboard event
		"""
		if not self.GetValue():
			event.Skip()
			return
		shortcut = (event.GetModifiers(), event.GetKeyCode())
		action = self.key_actions.get(shortcut)
		if action:
			action(self, event)
		else:
			event.Skip()
