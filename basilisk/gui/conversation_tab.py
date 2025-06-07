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
import threading
import time
from typing import TYPE_CHECKING, Any, Optional

import wx
from more_itertools import first, locate
from upath import UPath

import basilisk.config as config
from basilisk import global_vars
from basilisk.accessible_output import get_accessible_output
from basilisk.conversation import (
	PROMPT_TITLE,
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.decorators import ensure_no_task_running
from basilisk.provider_ai_model import ProviderAIModel
from basilisk.provider_capability import ProviderCapability
from basilisk.sound_manager import play_sound, stop_sound

from .base_conversation import BaseConversation
from .history_msg_text_ctrl import HistoryMsgTextCtrl
from .prompt_attachments_panel import PromptAttachmentsPanel

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine
	from basilisk.recording_thread import RecordingThread

	from .main_frame import MainFrame

log = logging.getLogger(__name__)
accessible_output = get_accessible_output()


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
		title: The title of the conversation
		conversation: The conversation object
		attachment_files: List of attachment files
	"""

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
		self.recording_thread: Optional[RecordingThread] = None
		self.task = None
		self._stop_completion = False
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
		self.messages = HistoryMsgTextCtrl(self, size=(800, 400))
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)
		self.prompt_panel = PromptAttachmentsPanel(
			self, self.conv_storage_path, self.on_submit
		)
		sizer.Add(self.prompt_panel, proportion=1, flag=wx.EXPAND)
		self.prompt_panel.set_prompt_focus()
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
		self.prompt_panel.refresh_attachments_list()
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
		shortcut = (event.GetModifiers(), event.GetKeyCode())
		actions = {(wx.MOD_CONTROL, ord('P')): self.on_choose_profile}
		action = actions.get(shortcut, wx.KeyEvent.Skip)
		action(event)

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
		self.web_search_mode.Enable(
			ProviderCapability.WEB_SEARCH
			in account.provider.engine_cls.capabilities
		)
		self.prompt_panel.set_engine(self.current_engine)

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

		self.Layout()

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

		menu.Destroy()

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
			self.prompt_panel.prompt_text = last_user_message

	def extract_text_from_message(self, content: str) -> str:
		"""Extracts the text content from a message.

		Args:
		content: The message content to extract text from.

		Returns:
		The extracted text content of the message.
		"""
		if isinstance(content, str):
			return content

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
			self.prompt_panel.clear()
		self.prompt_panel.refresh_attachments_list()
		for block in self.conversation.messages:
			self.messages.display_new_block(block)

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
		self.prompt_panel.prompt.AppendText(transcription.text)
		if (
			self.prompt_panel.prompt.HasFocus()
			and self.GetTopLevelParent().IsShown()
		):
			self._handle_accessible_output(transcription.text)
		self.prompt_panel.SetInsertionPointEnd()
		self.prompt_panel.set_prompt_focus()

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
		if self.prompt_panel.has_image_attachments() and not model.vision:
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

	def get_system_message(self) -> SystemMessage | None:
		"""Get the system message from the system prompt input.

		Returns:
			System message if set, None otherwise
		"""
		system_prompt = self.system_prompt_txt.GetValue()
		if not system_prompt:
			return None
		return SystemMessage(content=system_prompt)

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
		self.prompt_panel.resize_all_attachments()
		return MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=self.prompt_panel.prompt_text,
				attachments=self.prompt_panel.attachment_files,
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
		completion_args = {}
		if (
			ProviderCapability.WEB_SEARCH
			in self.current_account.provider.engine_cls.capabilities
		):
			completion_args["web_search_mode"] = self.web_search_mode.GetValue()

		return completion_args | {
			"engine": self.current_engine,
			"system_message": self.get_system_message(),
			"conversation": self.conversation,
			"new_block": new_block,
			"stream": new_block.stream,
		}

	@ensure_no_task_running
	def on_submit(self, event: wx.CommandEvent):
		"""Handle the submission of a new message block for completion.

		Args:
			event: The event that triggered the submission action
		"""
		if not self.submit_btn.IsEnabled():
			return
		if not self.prompt_panel.check_attachments_valid():
			self.prompt_panel.set_attachments_focus()
			return
		if (
			not self.prompt_panel.prompt_text
			and not self.prompt_panel.attachments_list
		):
			self.prompt_panel.set_prompt_focus()
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
		system_message = kwargs.get("system_message")
		if kwargs.get("stream", False):
			new_block.response = Message(
				role=MessageRoleEnum.ASSISTANT, content=""
			)
			wx.CallAfter(
				self._pre_handle_completion_with_stream,
				new_block,
				system_message,
			)
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
			wx.CallAfter(
				self._post_completion_without_stream, new_block, system_message
			)

	def _pre_handle_completion_with_stream(
		self, new_block: MessageBlock, system_message: Message | None
	):
		"""Prepare for handling a completion response with streaming.

		Args:
			new_block: The new message block to be displayed
			system_message: An optional system message to be used
		"""
		self.conversation.add_block(new_block, system_message)
		self.messages.display_new_block(new_block)
		self.messages.SetInsertionPointEnd()
		self.prompt_panel.clear()
		self.prompt_panel.refresh_attachments_list()

	def _handle_completion_with_stream(self, chunk: str):
		"""Handle a completion response chunk for streaming.

		Args:
			chunk: The completion response chunk to be displayed
		"""
		self.messages.append_stream_chunk(chunk)
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _handle_accessible_output(
		self, text: str, braille: bool = False, force: bool = False
	):
		self.messages.handle_accessible_output(text, braille, force)

	def _post_completion_with_stream(self, new_block: MessageBlock):
		"""Finalize the completion process for a streaming response.

		Args:
			new_block: The new message block to be displayed
		"""
		self.messages.flush_stream_buffer()
		self.messages.handle_speech_stream_buffer()
		self.messages.update_last_segment_length()
		if config.conf().conversation.focus_history_after_send:
			self.messages.SetFocus()
		self._end_task()

	def _post_completion_without_stream(
		self, new_block: MessageBlock, system_message: Message | None
	):
		"""Finalize the completion process for a non-streaming response.

		Args:
			new_block: The new message block to be displayed
			system_message: The system message to be used
		"""
		self.conversation.add_block(new_block, system_message)
		self.messages.display_new_block(new_block)
		self.messages.handle_accessible_output(new_block.response.content)
		self.prompt_panel.clear()
		self.prompt_panel.refresh_attachments_list()
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

	def remove_message_block(self, message_block: MessageBlock):
		"""Remove a message block from the conversation.

		Args:
			message_block: The message block to remove
		"""
		self.conversation.remove_block(message_block)
		self.refresh_messages()

	def get_conversation_block_index(self, block: MessageBlock) -> int | None:
		"""Get the index of a message block in the conversation.

		Args:
			block: The message block to find

		Returns:
			The index of the message block in the conversation, or None if not found
		"""
		if block not in self.conversation.messages:
			return None
		return self.conversation.messages.index(block)
