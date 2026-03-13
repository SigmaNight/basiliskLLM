"""Custom text control for displaying conversation history.

This module provides a custom text control for displaying conversation history in the Basilisk GUI. It extends the wx.TextCtrl class to provide specialized functionality for handling conversation message history, including message navigation, search capabilities, and accessibility features.
"""

from __future__ import annotations

import logging
import os
import weakref
from collections import namedtuple
from functools import partialmethod
from typing import TYPE_CHECKING

import wx

import basilisk.config as config
from basilisk.conversation.conversation_model import (
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.message_segment_manager import MessageSegment, MessageSegmentType
from basilisk.presenters.history_presenter import HistoryPresenter
from basilisk.services.search_service import SearchDirection

from .edit_block_dialog import EditBlockDialog

if TYPE_CHECKING:
	from .conversation_tab import ConversationTab

logger = logging.getLogger(__name__)


MenuItemInfo = namedtuple(
	"MenuItemInfo", ["label", "shortcut", "handler", "args"]
)


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

		self.presenter = HistoryPresenter(self)
		self.init_role_labels()
		self.Bind(wx.EVT_CONTEXT_MENU, self.on_context_menu)
		self.Bind(wx.EVT_KEY_DOWN, self.on_key_down)

	# ------------------------------------------------------------------
	# Proxy properties — delegate to presenter
	# ------------------------------------------------------------------

	@property
	def segment_manager(self):
		"""Proxy to presenter.segment_manager."""
		return self.presenter.segment_manager

	@property
	def a_output(self):
		"""Proxy to presenter.a_output."""
		return self.presenter.a_output

	@property
	def speak_response(self) -> bool:
		"""Proxy to presenter.speak_response."""
		return self.presenter.speak_response

	@property
	def should_speak_response(self) -> bool:
		"""Proxy to presenter.should_speak_response."""
		return self.presenter.should_speak_response

	@property
	def current_msg_range(self) -> tuple[int, int]:
		"""Proxy to presenter.current_msg_range."""
		return self.presenter.current_msg_range

	@property
	def current_msg_block(self) -> MessageBlock | None:
		"""Proxy to presenter.current_msg_block."""
		return self.presenter.current_msg_block

	@property
	def current_msg_content(self) -> str:
		"""Proxy to presenter.current_msg_content."""
		return self.presenter.current_msg_content

	# ------------------------------------------------------------------
	# View interface method used by the presenter
	# ------------------------------------------------------------------

	def bell(self) -> None:
		"""Ring the system bell."""
		wx.Bell()

	# ------------------------------------------------------------------
	# Role labels
	# ------------------------------------------------------------------

	def init_role_labels(self):
		"""Initialize role labels for conversation messages.

		Uses the default role labels from the MessageRoleEnum, and optionally replaces them with custom labels from the system configuration.
		"""
		self.role_labels = MessageRoleEnum.get_labels()
		if label := config.conf().conversation.role_label_user:
			self.role_labels[MessageRoleEnum.USER] = label
		if label := config.conf().conversation.role_label_assistant:
			self.role_labels[MessageRoleEnum.ASSISTANT] = label

	# ------------------------------------------------------------------
	# Text / segment operations
	# ------------------------------------------------------------------

	def Clear(self):
		"""Clear the conversation text control."""
		super().Clear()
		self.presenter.clear()

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

	append_prefix = partialmethod(
		append_text_and_segment, segment_type=MessageSegmentType.PREFIX
	)

	append_content = partialmethod(
		append_text_and_segment, segment_type=MessageSegmentType.CONTENT
	)

	append_suffix = partialmethod(
		append_text_and_segment,
		text=os.linesep,
		segment_type=MessageSegmentType.SUFFIX,
	)

	def display_new_block(
		self, new_block: MessageBlock, streaming: bool = False
	):
		"""Displays a new message block in the conversation text control.

		This method appends a new message block to the existing conversation, handling both request and response messages. It manages the formatting and segmentation of messages, including role labels and content.

		Notes:
		- Handles empty and non-empty message text controls
		- Supports configurable role labels from system configuration
		- Uses weak references to track message blocks
		- Preserves the original insertion point after displaying the block
		- Supports both request and optional response messages
		- In streaming mode, only displays the assistant label, not the content

		Args:
			new_block: The message block to be displayed in the conversation.
			streaming: If True, indicates that the response content will be streamed
				and should not be displayed here. Defaults to False.
		"""
		absolute_length = self.GetLastPosition()
		new_block_ref = weakref.ref(new_block)
		if not self.IsEmpty():
			absolute_length = self.append_suffix(new_block_ref, absolute_length)
		absolute_length = self.append_prefix(
			new_block_ref,
			absolute_length,
			self.role_labels[MessageRoleEnum.USER],
		)
		absolute_length = self.append_content(
			new_block_ref, absolute_length, new_block.request.content
		)
		absolute_length = self.append_suffix(new_block_ref, absolute_length)
		pos = self.GetInsertionPoint()
		if new_block.response:
			absolute_length = self.append_prefix(
				new_block_ref,
				absolute_length,
				self.role_labels[MessageRoleEnum.ASSISTANT],
			)
			# Only display response content if not streaming (streaming content
			# is displayed incrementally via append_stream_chunk)
			if not streaming:
				absolute_length = self.append_content(
					new_block_ref, absolute_length, new_block.response.content
				)
				# Don't add suffix here - next block will add one when it starts
			else:
				# Create an empty content segment for streaming response
				# This will be updated as chunks are appended
				# Don't add suffix here - next block will add one when it starts
				absolute_length = self.append_content(
					new_block_ref, absolute_length, ""
				)
		self.SetInsertionPoint(pos)

	def update_last_segment_length(self):
		"""Update the length of the last content segment to match the current text control position."""
		self.presenter.update_last_segment_length(self.GetLastPosition())

	# ------------------------------------------------------------------
	# Context menu
	# ------------------------------------------------------------------

	def menu_msg_info(self) -> list[MenuItemInfo]:
		"""Initialize the message operations menu items.

		Initializes self.msg_menu_info with menu items for various message operations.

		Provides options for:
		- Reading the current message
		- Toggling stream speaking mode
		- Showing the current message as HTML
		- Showing the citations for the current message
		- Copying the current message
		- Selecting the current message
		- Going to the previous message
		- Going to the next message
		- Moving to the start of the current message
		- Moving to the end of the current message
			- Editing the current message block
		- Removing the current message block
		- Searching in the messages
		- Searching for the next occurrence
		- Searching for the previous occurrence
		"""
		return (
			MenuItemInfo(
				_("Read current message"),
				"(space)",
				self.on_read_current_message,
				[],
			),
			MenuItemInfo(
				_("Speak response"),
				"(Shift+Space)",
				self.on_toggle_speak_response,
				[self.speak_response],
			),
			MenuItemInfo(
				_("Show as HTML (from Markdown)"),
				"(&h)",
				self.on_show_as_html,
				[],
			),
			MenuItemInfo(_("Show citations"), "(&q)", self.show_citations, []),
			MenuItemInfo(
				_("Copy current message"), "(&c)", self.on_copy_message, []
			),
			MenuItemInfo(
				_("Select current message"),
				"(&s)",
				self.on_select_current_message,
				[],
			),
			MenuItemInfo(
				_("Go to previous message"),
				"(&j)",
				self.go_to_previous_message,
				[],
			),
			MenuItemInfo(
				_("Go to next message"), "(&k)", self.go_to_next_message, []
			),
			MenuItemInfo(
				_("Move to start of message"),
				"(&b)",
				self.move_to_start_of_message,
				[],
			),
			MenuItemInfo(
				_("Move to end of message"),
				"(&n)",
				self.move_to_end_of_message,
				[],
			),
			MenuItemInfo(
				_("Edit message block"), "(&e)", self.on_edit_message_block, []
			),
			MenuItemInfo(
				_("Remove message block"),
				"(Shift+Del)",
				self.on_remove_message_block,
				[],
			),
			MenuItemInfo(_("Find..."), "(&f)", self.on_search, []),
			MenuItemInfo(_("Find Next"), "(F3)", self.on_search_next, []),
			MenuItemInfo(
				_("Find Previous"), "(Shift+F3)", self.on_search_previous, []
			),
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

	def _add_message_operations_menu_items(self, menu: wx.Menu):
		"""Add message operation items to the context menu.

		Args:
			menu: The menu to add items to
		"""
		for item_info in self.menu_msg_info():
			is_checkable = bool(item_info.args and item_info.args[0])
			item = wx.MenuItem(
				menu,
				wx.ID_ANY,
				f"{item_info.label} {item_info.shortcut}",
				kind=wx.ITEM_CHECK if is_checkable else wx.ITEM_NORMAL,
			)
			menu.Append(item)
			if is_checkable:
				item.Check(item_info.args[0])
			self.Bind(wx.EVT_MENU, item_info.handler, item)

	def _add_standard_menu_items(self, menu: wx.Menu):
		"""Add standard edit menu items.

		Args:
			menu: The menu to add items to
		"""
		menu.Append(wx.ID_UNDO)
		menu.Append(wx.ID_REDO)
		menu.Append(wx.ID_CUT)
		menu.Append(wx.ID_COPY)
		menu.Append(wx.ID_SELECTALL)

	# ------------------------------------------------------------------
	# Navigation — delegate to presenter
	# ------------------------------------------------------------------

	def navigate_message(self, previous: bool):
		"""Navigate to the previous or next message.

		Args:
			previous: If True, navigate to previous message, else next message
		"""
		self.presenter.navigate_message(previous)

	def go_to_previous_message(self, event=None):
		"""Navigate to the previous message."""
		self.presenter.go_to_previous_message()

	def go_to_next_message(self, event=None):
		"""Navigate to the next message."""
		self.presenter.go_to_next_message()

	def on_select_current_message(self, event: wx.Event | None = None):
		"""Select the current message range."""
		self.SetSelection(*self.current_msg_range)

	def on_copy_message(self, event=None):
		"""Copy the current message to clipboard."""
		cursor_pos = self.GetInsertionPoint()
		self.on_select_current_message()
		self.Copy()
		self.SetInsertionPoint(cursor_pos)
		self.a_output.handle(
			_("Message copied to clipboard"),
			braille=True,
			clear_for_speak=False,
		)

	def move_to_start_of_message(self, event=None):
		"""Move cursor to start of current message."""
		cursor_pos = self.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		self.segment_manager.focus_content_block()
		self.SetInsertionPoint(self.segment_manager.start)
		self.a_output.handle(_("Start of message"), clear_for_speak=False)

	def move_to_end_of_message(self, event=None):
		"""Move cursor to end of current message."""
		cursor_pos = self.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		self.segment_manager.focus_content_block()
		self.SetInsertionPoint(self.segment_manager.end - 1)
		self.a_output.handle(_("End of message"), clear_for_speak=False)

	# ------------------------------------------------------------------
	# Search — delegate to presenter
	# ------------------------------------------------------------------

	def _do_search(self, direction: SearchDirection = SearchDirection.FORWARD):
		"""Open the search dialog.

		Args:
			direction: Search direction
		"""
		self.presenter.open_search(direction)

	def on_search(self, event: wx.Event | None):
		"""Handle search command."""
		self.presenter.open_search(SearchDirection.FORWARD)

	def on_search_previous(self, event: wx.Event | None):
		"""Search for previous occurrence."""
		self.presenter.search_previous()

	def on_search_next(self, event: wx.Event | None):
		"""Search for next occurrence."""
		self.presenter.search_next()

	# ------------------------------------------------------------------
	# Speak response — delegate to presenter
	# ------------------------------------------------------------------

	def on_toggle_speak_response(self, event: wx.Event | None = None):
		"""Toggle response speaking mode."""
		if event:
			return wx.CallLater(500, self.on_toggle_speak_response)
		self.presenter.toggle_speak_response()

	def on_read_current_message(self, event: wx.Event | None = None):
		"""Read the current message."""
		if event:
			return wx.CallLater(500, self.on_read_current_message)
		self.a_output.handle(self.current_msg_content, force=True)

	# ------------------------------------------------------------------
	# Streaming — delegate to presenter
	# ------------------------------------------------------------------

	def append_stream_chunk(self, text: str):
		"""Append a chunk of text to the speech stream buffer.

		Args:
			text: The text chunk to append
		"""
		self.presenter.handle_stream_chunk(text)

	# ------------------------------------------------------------------
	# HTML view
	# ------------------------------------------------------------------

	def on_show_as_html(self, event: wx.Event | None):
		"""Show current message as HTML.

		Args:
			event: The event that triggered the
		"""
		from .html_view_window import show_html_view_window

		show_html_view_window(
			self.GetParent(), self.current_msg_content, "markdown"
		)

	# ------------------------------------------------------------------
	# Citations — delegate to presenter
	# ------------------------------------------------------------------

	def report_number_of_citations(self):
		"""Report the number of citations for the current message."""
		self.presenter.report_number_of_citations()

	def show_citations(self, event: wx.CommandEvent | None = None):
		"""Show the citations for the current message.

		Args:
			event: The event that triggered the action
		"""
		self.presenter.show_citations()

	# ------------------------------------------------------------------
	# Message block operations
	# ------------------------------------------------------------------

	def on_remove_message_block(self, event: wx.CommandEvent | None = None):
		"""Remove the current message block from the conversation.

		Args:
			event: The event that triggered the action
		"""
		cursor_pos = self.GetInsertionPoint()
		block = self.current_msg_block
		if block:
			self.GetParent().remove_message_block(block)
			self.SetInsertionPoint(cursor_pos)
			self.a_output.handle(_("Message block removed"), braille=True)
		else:
			wx.Bell()

	def on_edit_message_block(self, event: wx.CommandEvent | None = None):
		"""Edit the current message block.

		Opens a dialog to edit the message block at the current cursor position.

		Args:
			event: The event that triggered the action
		"""
		block = self.current_msg_block
		if not block:
			wx.Bell()
			return
		block_index = self.GetParent().get_conversation_block_index(block)
		if block_index is None:
			wx.Bell()
			return
		dlg = EditBlockDialog(self.GetParent(), block_index)
		if dlg.ShowModal() == wx.ID_OK:
			self.GetParent().refresh_messages()
			self.a_output.handle(_("Message block updated"), braille=True)
		dlg.Destroy()

	# goes here because we need all the methods to be defined before we can assign to the dict
	key_actions = {
		(wx.MOD_SHIFT, wx.WXK_SPACE): on_toggle_speak_response,
		(wx.MOD_NONE, wx.WXK_SPACE): on_read_current_message,
		(wx.MOD_NONE, ord("J")): go_to_previous_message,
		(wx.MOD_NONE, ord("K")): go_to_next_message,
		(wx.MOD_NONE, ord("S")): on_select_current_message,
		(wx.MOD_NONE, ord("H")): on_show_as_html,
		(wx.MOD_NONE, ord("Q")): show_citations,
		(wx.MOD_NONE, ord("C")): on_copy_message,
		(wx.MOD_NONE, ord("B")): move_to_start_of_message,
		(wx.MOD_NONE, ord("N")): move_to_end_of_message,
		(wx.MOD_NONE, ord("E")): on_edit_message_block,
		(wx.MOD_SHIFT, wx.WXK_DELETE): on_remove_message_block,
		(wx.MOD_NONE, wx.WXK_F3): on_search_next,
		(wx.MOD_NONE, ord("F")): on_search,
		(wx.MOD_CONTROL, ord("F")): on_search,
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
		- Q: Show citations for current message
		- E: Edit current message block
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
