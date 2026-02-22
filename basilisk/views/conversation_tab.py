"""Implements the conversation tab view for the BasiliskLLM chat application.

This module provides the ConversationTab class — the view layer of the MVP
pattern. It creates widgets, handles pure-UI events, and delegates all
orchestration and persistence logic to ConversationPresenter and
ConversationService respectively.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING, Any, Optional

import wx
from more_itertools import first, locate
from upath import UPath

import basilisk.config as config
from basilisk.conversation import Conversation, MessageBlock, SystemMessage
from basilisk.presenters.conversation_presenter import ConversationPresenter
from basilisk.provider_capability import ProviderCapability
from basilisk.services.account_model_service import AccountModelService
from basilisk.services.conversation_service import ConversationService

from .base_conversation import BaseConversation
from .history_msg_text_ctrl import HistoryMsgTextCtrl
from .ocr_handler import OCRHandler
from .prompt_attachments_panel import PromptAttachmentsPanel

if TYPE_CHECKING:
	from basilisk.recording_thread import RecordingThread

	from .main_frame import MainFrame

log = logging.getLogger(__name__)

CHECK_TASK_DELAY = 100  # ms


class ConversationTab(wx.Panel, BaseConversation):
	"""A tab panel that manages a single conversation with an AI assistant.

	This is the *view* layer: it creates widgets, handles pure-UI events,
	and delegates orchestration to the ConversationPresenter and persistence
	to the ConversationService.

	Attributes:
		title: The title of the conversation.
		presenter: The ConversationPresenter instance.
		service: The ConversationService instance.
	"""

	_conv_db = None

	@classmethod
	def _get_conv_db(cls):
		if cls._conv_db is None:
			cls._conv_db = wx.GetApp().conv_db
		return cls._conv_db

	# -- Properties proxying to presenter / service --

	@property
	def conversation(self) -> Conversation:
		"""The active conversation model, owned by the presenter."""
		return self.presenter.conversation

	@conversation.setter
	def conversation(self, value: Conversation):
		self.presenter.conversation = value

	@property
	def bskc_path(self) -> Optional[str]:
		"""Path to the .bskc file, owned by the presenter."""
		return self.presenter.bskc_path

	@bskc_path.setter
	def bskc_path(self, value: Optional[str]):
		self.presenter.bskc_path = value

	@property
	def recording_thread(self) -> Optional[RecordingThread]:
		"""Active recording thread, owned by the presenter."""
		return self.presenter.recording_thread

	@recording_thread.setter
	def recording_thread(self, value):
		self.presenter.recording_thread = value

	@property
	def completion_handler(self):
		"""CompletionHandler instance, owned by the presenter."""
		return self.presenter.completion_handler

	@property
	def db_conv_id(self) -> Optional[int]:
		"""Database conversation ID, proxied from service."""
		return self.service.db_conv_id

	@db_conv_id.setter
	def db_conv_id(self, value: Optional[int]):
		self.service.db_conv_id = value

	@property
	def private(self) -> bool:
		"""Private mode flag, proxied from service."""
		return self.service.private

	@private.setter
	def private(self, value: bool):
		self.service.private = value

	# -- Factory methods --

	@staticmethod
	def conv_storage_path() -> UPath:
		"""Generate a unique storage path for a conversation.

		Returns:
			A memory-based URL path with a timestamp identifier.
		"""
		return UPath(
			f"memory://conversation_{datetime.datetime.now().isoformat(timespec='seconds')}"
		)

	@classmethod
	def open_conversation(
		cls, parent: wx.Window, file_path: str, default_title: str
	) -> ConversationTab:
		"""Open a conversation from a file.

		Args:
			parent: The parent window for the conversation tab.
			file_path: The path to the conversation file.
			default_title: Fallback title if the conversation has none.

		Returns:
			A new ConversationTab with the loaded conversation.
		"""
		log.debug("Opening conversation from %s", file_path)
		storage_path = cls.conv_storage_path()
		conversation = Conversation.open(file_path, storage_path)
		title = conversation.title or default_title

		draft_block = None
		if conversation.messages and conversation.messages[-1].response is None:
			draft_block = conversation.messages.pop()

		tab = cls(
			parent,
			conversation=conversation,
			title=title,
			conv_storage_path=storage_path,
			bskc_path=file_path,
		)

		if draft_block is not None:
			tab._restore_draft_block(draft_block)

		return tab

	@classmethod
	def open_from_db(
		cls, parent: wx.Window, conv_id: int, default_title: str
	) -> ConversationTab:
		"""Open a conversation from the database.

		Args:
			parent: The parent window for the conversation tab.
			conv_id: The database conversation ID.
			default_title: Fallback title if the conversation has none.

		Returns:
			A new ConversationTab with the loaded conversation.
		"""
		conversation = cls._get_conv_db().load_conversation(conv_id)
		title = conversation.title or default_title
		storage_path = cls.conv_storage_path()

		draft_block = None
		if conversation.messages and conversation.messages[-1].response is None:
			draft_block = conversation.messages.pop()

		tab = cls(
			parent,
			conversation=conversation,
			title=title,
			conv_storage_path=storage_path,
		)
		tab.db_conv_id = conv_id

		if draft_block is not None:
			tab._restore_draft_block(draft_block)

		return tab

	# -- Initialization --

	def __init__(
		self,
		parent: wx.Window,
		title: str = _("Untitled conversation"),
		profile: Optional[config.ConversationProfile] = None,
		conversation: Optional[Conversation] = None,
		conv_storage_path: Optional[UPath] = None,
		bskc_path: Optional[str] = None,
	):
		"""Initialize a new conversation tab.

		Args:
			parent: The parent window.
			title: The conversation title.
			profile: Conversation profile to apply.
			conversation: Existing conversation to load.
			conv_storage_path: Storage path for attachments.
			bskc_path: Path to a .bskc file.
		"""
		wx.Panel.__init__(self, parent)
		self.account_model_service = AccountModelService()
		BaseConversation.__init__(
			self, account_model_service=self.account_model_service
		)
		self.title = title
		self.SetStatusText = self.TopLevelParent.SetStatusText

		resolved_storage = conv_storage_path or self.conv_storage_path()
		resolved_conversation = conversation or Conversation()

		self.service = ConversationService(conv_db_getter=self._get_conv_db)
		self.presenter = ConversationPresenter(
			view=self,
			service=self.service,
			conversation=resolved_conversation,
			conv_storage_path=resolved_storage,
			bskc_path=bskc_path,
		)

		self._is_destroying = False
		self.process: Optional[Any] = None  # multiprocessing.Process
		self.ocr_handler = OCRHandler(self)
		self._draft_timer = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, self._on_draft_timer, self._draft_timer)

		self.init_ui()
		self.init_data(profile)
		self.adjust_advanced_mode_setting()

	def init_ui(self):
		"""Initialize and layout all UI components."""
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
		self.messages = HistoryMsgTextCtrl(self, size=(800, 400))
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)
		self.prompt_panel = PromptAttachmentsPanel(
			self, self.presenter.conv_storage_path, self.on_submit
		)
		sizer.Add(self.prompt_panel, proportion=1, flag=wx.EXPAND)
		self.prompt_panel.prompt.Bind(wx.EVT_TEXT, self._on_prompt_text_changed)
		self.prompt_panel.set_prompt_focus()
		self.ocr_button = self.ocr_handler.create_ocr_widget(self)
		sizer.Add(self.ocr_button, proportion=0, flag=wx.EXPAND)
		label = self.create_model_widget()
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.model_list, proportion=0, flag=wx.ALL | wx.EXPAND)
		self.create_web_search_widget()
		sizer.Add(self.web_search_mode, proportion=0, flag=wx.EXPAND)
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
		self.Bind(wx.EVT_BUTTON, self.on_submit, self.submit_btn)
		self.submit_btn.SetDefault()
		btn_sizer.Add(self.submit_btn, proportion=0, flag=wx.EXPAND)

		self.stop_completion_btn = wx.Button(
			self,
			# Translators: This is a label for stop completion button in the main window
			label=_("Stop completio&n"),
		)
		self.Bind(
			wx.EVT_BUTTON, self.on_stop_completion, self.stop_completion_btn
		)
		btn_sizer.Add(self.stop_completion_btn, proportion=0, flag=wx.EXPAND)
		self.stop_completion_btn.Hide()

		self.toggle_record_btn = wx.Button(
			self,
			# Translators: This is a label for record button in the main window
			label=_("Record") + " (Ctrl+R)",
		)
		btn_sizer.Add(self.toggle_record_btn, proportion=0, flag=wx.EXPAND)
		self.Bind(wx.EVT_BUTTON, self.toggle_recording, self.toggle_record_btn)

		self.apply_profile_btn = wx.Button(
			self,
			# Translators: This is a label for apply profile button in the main window
			label=_("Apply profile") + " (Ctrl+P)",
		)
		self.Bind(wx.EVT_BUTTON, self.on_choose_profile, self.apply_profile_btn)
		btn_sizer.Add(self.apply_profile_btn, proportion=0, flag=wx.EXPAND)

		sizer.Add(btn_sizer, proportion=0, flag=wx.EXPAND)

		self.SetSizerAndFit(sizer)

		self.Bind(wx.EVT_CHAR_HOOK, self.on_char_hook)

	def init_data(self, profile: Optional[config.ConversationProfile]):
		"""Initialize the conversation data with an optional profile.

		Args:
			profile: Configuration profile to apply.
		"""
		self.prompt_panel.refresh_attachments_list()
		self.apply_profile(profile, True)
		self.refresh_messages(need_clear=False)

	# -- Pure UI event handlers --

	def on_choose_profile(self, event: wx.KeyEvent | None):
		"""Display profile selection menu.

		Args:
			event: The event that triggered profile selection.
		"""
		main_frame: MainFrame = wx.GetTopLevelParent(self)
		menu = main_frame.build_profile_menu(
			main_frame.on_apply_conversation_profile
		)
		self.PopupMenu(menu)
		menu.Destroy()

	def on_char_hook(self, event: wx.KeyEvent):
		"""Handle keyboard shortcuts.

		Args:
			event: The keyboard event.
		"""
		shortcut = (event.GetModifiers(), event.GetKeyCode())
		actions = {(wx.MOD_CONTROL, ord("P")): self.on_choose_profile}
		action = actions.get(shortcut)
		if action:
			action(event)
		else:
			event.Skip()

	# -- Widget update handlers --

	def on_account_change(self, event: wx.CommandEvent | None):
		"""Handle account selection changes.

		Args:
			event: The account selection event.
		"""
		account = super().on_account_change(event)
		if not account:
			return
		self.set_model_list(None)
		self.toggle_record_btn.Enable(
			ProviderCapability.STT in account.provider.engine_cls.capabilities
		)
		self.ocr_button.Enable(
			ProviderCapability.OCR in account.provider.engine_cls.capabilities
		)
		self.web_search_mode.Enable(
			ProviderCapability.WEB_SEARCH
			in account.provider.engine_cls.capabilities
		)
		self.prompt_panel.set_engine(self.current_engine)

	def refresh_accounts(self):
		"""Update the account combo box with current accounts."""
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
		self.Layout()

	def on_config_change(self):
		"""Handle configuration changes."""
		self.refresh_accounts()
		self.on_account_change(None)
		self.on_model_change(None)
		self.adjust_advanced_mode_setting()

	# -- Display helpers --

	def add_standard_context_menu_items(
		self, menu: wx.Menu, include_paste: bool = True
	):
		"""Add standard context menu items to a menu.

		Args:
			menu: The menu to add items to.
			include_paste: Whether to include the paste item.
		"""
		menu.Append(wx.ID_UNDO)
		menu.Append(wx.ID_REDO)
		menu.Append(wx.ID_CUT)
		menu.Append(wx.ID_COPY)
		if include_paste:
			menu.Append(wx.ID_PASTE)
		menu.Append(wx.ID_SELECTALL)

	def insert_previous_prompt(self, event: wx.CommandEvent = None):
		"""Insert the last user message into the prompt.

		Args:
			event: The triggering event (unused).
		"""
		if self.conversation.messages:
			last_user_message = self.conversation.messages[-1].request
			self.prompt_panel.prompt_text = last_user_message.content
			if last_user_message.attachments:
				self.prompt_panel.attachment_files = (
					last_user_message.attachments.copy()
				)
			else:
				self.prompt_panel.attachment_files = []
			self.prompt_panel.refresh_attachments_list()

	def extract_text_from_message(self, content: str) -> str:
		"""Extract text content from a message.

		Args:
			content: The message content.

		Returns:
			The extracted text content.
		"""
		if isinstance(content, str):
			return content

	def refresh_messages(
		self, need_clear: bool = True, preserve_prompt: bool = False
	):
		"""Refresh the messages displayed.

		Args:
			need_clear: Whether to clear existing messages.
			preserve_prompt: Whether to preserve the current prompt.
		"""
		if need_clear:
			self.messages.Clear()
			if not preserve_prompt:
				self.prompt_panel.clear(False)
		self.prompt_panel.refresh_attachments_list()
		for block in self.conversation.messages:
			self.messages.display_new_block(block)

	def _restore_draft_block(self, draft_block: MessageBlock):
		"""Restore a draft block's content to UI controls.

		Args:
			draft_block: The draft MessageBlock to restore.
		"""
		self.prompt_panel.prompt_text = draft_block.request.content
		if draft_block.request.attachments:
			self.prompt_panel.attachment_files = draft_block.request.attachments
			self.prompt_panel.refresh_attachments_list()

		self.temperature_spinner.SetValue(draft_block.temperature)
		self.max_tokens_spin_ctrl.SetValue(draft_block.max_tokens)
		self.top_p_spinner.SetValue(draft_block.top_p)
		self.stream_mode.SetValue(draft_block.stream)

		try:
			provider_id = draft_block.model.provider_id
			model_id = draft_block.model.model_id
			account = next(
				config.accounts().get_accounts_by_provider(provider_id), None
			)
			if account:
				self.set_account_combo(account)
			engine = self.current_engine
			if engine:
				model = engine.get_model(model_id)
				if model:
					self.set_model_list(model)
		except Exception:
			log.debug("Could not restore draft model selection", exc_info=True)

	def get_conversation_block_index(self, block: MessageBlock) -> int | None:
		"""Get the index of a message block in the conversation.

		Args:
			block: The message block to find.

		Returns:
			The index, or None if not found.
		"""
		try:
			return self.conversation.messages.index(block)
		except ValueError:
			return None

	# -- Delegating event handlers (one-line delegations to presenter) --

	def on_submit(self, event: wx.CommandEvent):
		"""Handle submission of a new message.

		Args:
			event: The triggering event.
		"""
		self.presenter.on_submit()

	def on_stop_completion(self, event: wx.CommandEvent):
		"""Handle stopping the current completion.

		Args:
			event: The triggering event.
		"""
		self.presenter.on_stop_completion()

	def toggle_recording(self, event: wx.CommandEvent):
		"""Toggle audio recording on/off.

		Args:
			event: The button event.
		"""
		self.presenter.toggle_recording()

	def _on_prompt_text_changed(self, event):
		"""Handle prompt text changes for draft auto-save debouncing."""
		event.Skip()
		self.presenter.on_prompt_text_changed()

	def _on_draft_timer(self, event):
		"""Handle draft timer expiration."""
		self.presenter.on_draft_timer()

	# -- Delegating methods for external callers --

	def get_system_message(self) -> SystemMessage | None:
		"""Get the system message from the system prompt input."""
		return self.presenter.get_system_message()

	def get_new_message_block(self) -> MessageBlock | None:
		"""Construct a new message block from current UI state."""
		return self.presenter.get_new_message_block()

	def get_completion_args(self) -> dict[str, Any] | None:
		"""Get the arguments for the completion request."""
		return self.presenter.get_completion_args()

	def generate_conversation_title(self):
		"""Generate a conversation title using the AI model."""
		return self.presenter.generate_conversation_title()

	def save_conversation(self, file_path: str) -> bool:
		"""Save the current conversation to a file.

		Args:
			file_path: The target file path.

		Returns:
			True if saved successfully.
		"""
		return self.presenter.save_conversation(file_path)

	def remove_message_block(self, message_block: MessageBlock):
		"""Remove a message block from the conversation.

		Args:
			message_block: The message block to remove.
		"""
		self.presenter.remove_message_block(message_block)

	def update_db_title(self, title: str | None):
		"""Update the conversation title in the database.

		Args:
			title: The new title.
		"""
		self.service.update_db_title(title)

	def start_draft_timer(self, ms: int = 2000) -> None:
		"""Start the draft auto-save timer.

		Args:
			ms: Delay in milliseconds before the timer fires.
		"""
		self._draft_timer.StartOnce(ms)

	def stop_draft_timer(self) -> None:
		"""Stop the draft auto-save timer."""
		self._draft_timer.Stop()

	def set_private(self, private: bool):
		"""Set the private flag.

		Args:
			private: Whether the conversation should be private.
		"""
		if self.service.set_private(private):
			self.stop_draft_timer()

	def _is_widget_valid(self, widget_name: str | None = None) -> bool:
		"""Check if the tab and its widgets are still valid.

		Args:
			widget_name: Optional specific widget name to check. If None,
				only checks if the tab itself is valid.

		Returns:
			True if widgets are valid, False otherwise.
		"""
		if self._is_destroying:
			return False
		if widget_name and not hasattr(self, widget_name):
			return False
		try:
			self.GetParent()
			if widget_name:
				getattr(self, widget_name).GetParent()
			return True
		except RuntimeError:
			return False

	def cleanup_resources(self):
		"""Clean up all running resources before closing the conversation tab."""
		self._is_destroying = True
		self.presenter.cleanup()
		self.ocr_handler.cleanup()

	def flush_draft(self):
		"""Immediately save any pending draft to the database."""
		self.presenter.flush_draft()

	def transcribe_audio_file(self, audio_file: str = None):
		"""Transcribe an audio file.

		Args:
			audio_file: Path to audio file, or None to record.
		"""
		self.presenter.transcribe_audio_file(audio_file)

	def on_transcribe_audio_file(self):
		"""Open file dialog and transcribe selected audio file."""
		self.presenter.on_transcribe_audio_file()
