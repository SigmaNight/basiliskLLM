"""Group conversation tab view for BasiliskLLM.

Provides ``GroupConversationTab``: a wx.Panel that hosts a group chat with
multiple LLM participants. Layout is simpler than ``ConversationTab`` — it
does NOT inherit ``BaseConversation`` because account/model selection is
per-participant (frozen at creation time).
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Optional

import wx
from upath import UPath

from basilisk.conversation import Conversation, GroupParticipant
from basilisk.presenters.group_conversation_presenter import (
	GroupConversationPresenter,
)
from basilisk.services.conversation_service import ConversationService

from .history_msg_text_ctrl import HistoryMsgTextCtrl
from .prompt_attachments_panel import PromptAttachmentsPanel
from .view_mixins import ErrorDisplayMixin

if TYPE_CHECKING:
	pass

log = logging.getLogger(__name__)


class GroupConversationTab(wx.Panel, ErrorDisplayMixin):
	"""A tab panel that manages a group chat with multiple LLM participants.

	This is the *view* layer: creates widgets, handles pure-UI events, and
	delegates orchestration to ``GroupConversationPresenter``.

	Attributes:
		title: The conversation title (shown on the notebook tab).
		presenter: The GroupConversationPresenter instance.
		service: The ConversationService instance.
	"""

	_conv_db = None

	@classmethod
	def _get_conv_db(cls):
		"""Lazy-load the shared ConversationDatabase from the wx.App."""
		if cls._conv_db is None:
			cls._conv_db = wx.GetApp().conv_db
		return cls._conv_db

	# -- Protocol properties expected by MainFramePresenter --

	@property
	def conversation(self) -> Conversation:
		"""The active conversation model, owned by the presenter."""
		return self.presenter.conversation

	@property
	def bskc_path(self) -> Optional[str]:
		"""Path to the .bskc file, owned by the presenter."""
		return self.presenter.bskc_path

	@bskc_path.setter
	def bskc_path(self, value: Optional[str]):
		self.presenter.bskc_path = value

	@property
	def db_conv_id(self) -> Optional[int]:
		"""Database conversation ID, proxied from service."""
		return self.service.db_conv_id

	@db_conv_id.setter
	def db_conv_id(self, value: Optional[int]):
		self.service.db_conv_id = value

	@property
	def private(self) -> bool:
		"""Always False — group chats are not private."""
		return False

	# -- Factory methods --

	@staticmethod
	def conv_storage_path() -> UPath:
		"""Generate a unique storage path for a conversation.

		Returns:
			A memory-based URL path with a timestamp identifier.
		"""
		return UPath(
			f"memory://group_conversation_{datetime.datetime.now().isoformat(timespec='seconds')}"
		)

	@classmethod
	def open_from_conversation(
		cls,
		parent: wx.Window,
		conversation: Conversation,
		default_title: str,
		bskc_path: Optional[str] = None,
		db_conv_id: Optional[int] = None,
	) -> GroupConversationTab:
		"""Reconstruct a GroupConversationTab from a loaded Conversation.

		Used when opening a group chat from file or database.

		Args:
			parent: The parent notebook window.
			conversation: The loaded Conversation with group_participants set.
			default_title: Fallback title if the conversation has none.
			bskc_path: Path to the .bskc source file, or None.
			db_conv_id: Database conversation ID, or None.

		Returns:
			A new GroupConversationTab with the loaded conversation.
		"""
		title = conversation.title or default_title
		storage_path = cls.conv_storage_path()
		tab = cls(
			parent,
			conversation=conversation,
			title=title,
			conv_storage_path=storage_path,
			participants=conversation.group_participants,
			bskc_path=bskc_path,
		)
		if db_conv_id is not None:
			tab.db_conv_id = db_conv_id
		tab.refresh_messages()
		return tab

	# -- Initialization --

	def __init__(
		self,
		parent: wx.Window,
		participants: list[GroupParticipant],
		title: str = "",
		conversation: Optional[Conversation] = None,
		conv_storage_path: Optional[UPath] = None,
		bskc_path: Optional[str] = None,
	):
		"""Initialize the group conversation tab.

		Args:
			parent: The parent window.
			participants: List of GroupParticipant snapshots.
			title: The conversation title.
			conversation: Existing conversation to load, or None for a new one.
			conv_storage_path: Storage path for attachments.
			bskc_path: Path to a .bskc file.
		"""
		wx.Panel.__init__(self, parent)
		self.title = title or _("Group chat")
		self.SetStatusText = self.TopLevelParent.SetStatusText

		resolved_storage = conv_storage_path or self.conv_storage_path()
		resolved_conversation = conversation or Conversation(
			group_participants=participants
		)

		self.service = ConversationService(conv_db_getter=self._get_conv_db)
		self.presenter = GroupConversationPresenter(
			view=self,
			service=self.service,
			conversation=resolved_conversation,
			conv_storage_path=resolved_storage,
			participants=participants,
			bskc_path=bskc_path,
		)

		self._is_destroying = False
		self._init_ui()

	def _init_ui(self):
		"""Build and layout all UI components."""
		outer_sizer = wx.BoxSizer(wx.HORIZONTAL)

		# Left panel: participant roster
		left_panel = wx.Panel(self)
		left_sizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: Label for participant list in group chat
		roster_label = wx.StaticText(left_panel, label=_("&Participants:"))
		left_sizer.Add(roster_label, flag=wx.EXPAND | wx.ALL, border=4)
		self._participant_list = wx.ListBox(
			left_panel, choices=[p.name for p in self.presenter.participants]
		)
		self._participant_list.SetName(_("Participants"))
		left_sizer.Add(
			self._participant_list,
			proportion=1,
			flag=wx.EXPAND | wx.ALL,
			border=4,
		)
		left_panel.SetSizer(left_sizer)
		outer_sizer.Add(left_panel, proportion=0, flag=wx.EXPAND)
		outer_sizer.Add(
			wx.StaticLine(self, style=wx.LI_VERTICAL), flag=wx.EXPAND
		)

		# Right panel: messages + input
		right_sizer = wx.BoxSizer(wx.VERTICAL)
		msg_label = wx.StaticText(
			self,
			# Translators: Label for the messages area in group chat
			label=_("&Messages:"),
		)
		right_sizer.Add(msg_label, flag=wx.EXPAND)
		self.messages = HistoryMsgTextCtrl(self, size=(700, 400))
		right_sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		self.prompt_panel = PromptAttachmentsPanel(
			self, self.presenter.conv_storage_path, self._on_submit
		)
		right_sizer.Add(self.prompt_panel, proportion=1, flag=wx.EXPAND)

		# Debate controls row
		debate_row = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: Label for debate rounds spinner in group chat
		rounds_label = wx.StaticText(self, label=_("Debate &rounds:"))
		debate_row.Add(
			rounds_label, flag=wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, border=4
		)
		self._debate_rounds = wx.SpinCtrl(self, min=1, max=20, initial=3)
		debate_row.Add(self._debate_rounds, flag=wx.ALIGN_CENTER_VERTICAL)
		# Translators: Button to start a debate in group chat
		self._debate_btn = wx.Button(self, label=_("Start &debate"))
		self.Bind(wx.EVT_BUTTON, self._on_start_debate, self._debate_btn)
		debate_row.Add(self._debate_btn, flag=wx.LEFT, border=8)
		right_sizer.Add(debate_row, flag=wx.EXPAND | wx.TOP, border=4)

		# Submit / stop row
		btn_row = wx.BoxSizer(wx.HORIZONTAL)
		self._submit_btn = wx.Button(
			self,
			# Translators: Submit button label in group chat
			label=_("Submit") + " (Ctrl+Enter)",
		)
		self._submit_btn.SetDefault()
		self.Bind(wx.EVT_BUTTON, self._on_submit, self._submit_btn)
		btn_row.Add(self._submit_btn)
		self._stop_btn = wx.Button(
			self,
			# Translators: Stop button label in group chat
			label=_("Stop"),
		)
		self.Bind(wx.EVT_BUTTON, self._on_stop, self._stop_btn)
		self._stop_btn.Hide()
		btn_row.Add(self._stop_btn)
		right_sizer.Add(btn_row, flag=wx.EXPAND | wx.TOP, border=4)

		outer_sizer.Add(right_sizer, proportion=1, flag=wx.EXPAND)
		self.SetSizerAndFit(outer_sizer)
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

	# -- Pure UI event handlers --

	def _on_submit(self, event: wx.CommandEvent = None):
		"""Handle submit button / Ctrl+Enter."""
		self.presenter.on_submit()

	def _on_start_debate(self, event: wx.CommandEvent):
		"""Handle start debate button."""
		self.presenter.on_start_debate()

	def _on_stop(self, event: wx.CommandEvent):
		"""Handle stop button."""
		self.presenter.on_stop()

	def _on_char_hook(self, event: wx.KeyEvent):
		"""Handle Ctrl+Enter keyboard shortcut for submit."""
		if (
			event.GetModifiers() == wx.MOD_CONTROL
			and event.GetKeyCode() == wx.WXK_RETURN
		):
			self._on_submit()
		else:
			event.Skip()

	# -- View interface used by the presenter --

	def get_prompt_text(self) -> str:
		"""Return current prompt text."""
		return self.prompt_panel.prompt_text

	def get_attachment_files(self):
		"""Return current attachment file list."""
		return self.prompt_panel.attachment_files

	def get_debate_rounds(self) -> int:
		"""Return the debate rounds spinner value."""
		return self._debate_rounds.GetValue()

	def clear_prompt(self):
		"""Clear the prompt input and attachments."""
		self.prompt_panel.clear(refresh=True)

	def set_active_participant(self, index: Optional[int]):
		"""Highlight the currently responding participant.

		Args:
			index: Zero-based participant index, or None to clear selection.
		"""
		if index is None:
			self._participant_list.SetSelection(wx.NOT_FOUND)
		else:
			self._participant_list.SetSelection(index)

	def announce_round(self, round_number: int):
		"""Announce a new debate round (accessibility).

		Args:
			round_number: The one-based round number being announced.
		"""
		self.SetStatusText(
			# Translators: Status bar text announcing a new debate round
			_("Debate round %d") % round_number
		)

	def on_completion_start(self):
		"""Called by presenter when a completion starts."""
		self._submit_btn.Disable()
		self._debate_btn.Disable()
		self._stop_btn.Show()
		self.Layout()

	def on_chain_complete(self):
		"""Called by presenter when the full chain finishes."""
		self._submit_btn.Enable()
		self._debate_btn.Enable()
		self._stop_btn.Hide()
		self.Layout()

	def refresh_messages(self, need_clear: bool = True):
		"""Re-render all conversation messages from scratch.

		Args:
			need_clear: Whether to clear existing messages first.
		"""
		if need_clear:
			self.messages.Clear()
		for block in self.presenter.conversation.messages:
			self.messages.display_new_block(block)

	# -- Protocol methods for MainFramePresenter --

	def save_conversation(self, file_path: str) -> bool:
		"""Save the conversation to a file.

		Args:
			file_path: Target file path.

		Returns:
			True if saved successfully.
		"""
		return self.presenter.save_conversation(file_path)

	def flush_draft(self):
		"""No-op for group chats — no draft support."""
		self.presenter.flush_draft()

	def update_db_title(self, title: str | None):
		"""Update the conversation title in the database.

		Args:
			title: The new title.
		"""
		self.service.update_db_title(title)

	def generate_conversation_title(self) -> Optional[str]:
		"""Group chats do not support auto-generated titles.

		Returns:
			Always None.
		"""
		return None

	def set_private(self, private: bool):
		"""No-op: group chats don't support private mode."""

	def cleanup_resources(self):
		"""Stop all running resources before closing the tab."""
		self._is_destroying = True
		self.presenter.cleanup()
