"""Presenter for conversation orchestration logic.

Coordinates between the ConversationTab view, CompletionHandler,
RecordingThread, and ConversationService. Owns the completion handler,
recording thread, error-recovery state, and conversation model.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

import basilisk.config as config
from basilisk.completion_handler import CompletionHandler
from basilisk.conversation import (
	AttachmentFile,
	Conversation,
	ImageFile,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.presenters.presenter_mixins import (
	DestroyGuardMixin,
	_guard_destroying,
)
from basilisk.provider_ai_model import AIModelInfo
from basilisk.provider_capability import ProviderCapability
from basilisk.services.conversation_service import ConversationService
from basilisk.sound_manager import play_sound, stop_sound

if TYPE_CHECKING:
	from basilisk.recording_thread import RecordingThread
	from basilisk.views.conversation_tab import ConversationTab

log = logging.getLogger(__name__)


class ConversationPresenter(DestroyGuardMixin):
	"""Orchestrates completion, recording, and submission flows.

	The presenter holds the completion handler, recording thread, error
	recovery state, and the conversation model. It reads widget values
	directly from the view (MVP pattern) and delegates persistence to the
	ConversationService.

	Attributes:
		view: The ConversationTab view this presenter drives.
		service: The ConversationService for persistence.
		conversation: The active conversation model.
		completion_handler: Handler for AI completions.
		recording_thread: Active recording thread, or None.
		conv_storage_path: Storage path for conversation attachments.
		bskc_path: Path to the .bskc file, or None.
	"""

	def __init__(
		self,
		view: ConversationTab,
		service: ConversationService,
		conversation: Conversation,
		conv_storage_path,
		bskc_path: Optional[str] = None,
	):
		"""Initialize the conversation presenter.

		Args:
			view: The ConversationTab view instance.
			service: The ConversationService instance.
			conversation: The conversation model.
			conv_storage_path: Storage path for attachments.
			bskc_path: Path to .bskc file.
		"""
		self.view = view
		self.service = service
		self.conversation = conversation
		self.conv_storage_path = conv_storage_path
		self.bskc_path = bskc_path
		self.recording_thread: Optional[RecordingThread] = None

		# Error recovery state
		self._stored_prompt_text: Optional[str] = None
		self._stored_attachments: Optional[list[AttachmentFile | ImageFile]] = (
			None
		)

		self.completion_handler = CompletionHandler(
			on_completion_start=self._on_completion_start,
			on_completion_end=self._on_completion_end,
			on_stream_chunk=self._on_stream_chunk,
			on_stream_start=self._on_stream_start,
			on_stream_finish=self._on_stream_finish,
			on_non_stream_finish=self._on_non_stream_finish,
			on_error=self._on_completion_error,
		)

	# -- Submission flow --

	def on_submit(self):
		"""Handle submission of a new message for completion."""
		view = self.view
		view.stop_draft_timer()
		if not view.submit_btn.IsEnabled():
			return
		if (
			not view.prompt_panel.prompt_text
			and not view.prompt_panel.attachment_files
		):
			view.prompt_panel.set_prompt_focus()
			return

		if not view.prompt_panel.check_attachments_valid():
			view.prompt_panel.set_attachments_focus()
			return

		new_block = self.get_new_message_block()
		if not new_block:
			return

		self._store_prompt_content()
		view.prompt_panel.clear(refresh=True)

		completion_kwargs = {}
		if (
			ProviderCapability.WEB_SEARCH
			in view.current_account.provider.engine_cls.capabilities
		):
			completion_kwargs["web_search_mode"] = (
				view.web_search_mode.GetValue()
			)

		self.completion_handler.start_completion(
			engine=view.current_engine,
			system_message=self.get_system_message(),
			conversation=self.conversation,
			new_block=new_block,
			stream=new_block.stream,
			**completion_kwargs,
		)

	def on_stop_completion(self):
		"""Stop the current completion."""
		self.completion_handler.stop_completion()

	def get_system_message(self) -> SystemMessage | None:
		"""Get the system message from the view's system prompt input."""
		system_prompt = self.view.system_prompt_txt.GetValue()
		if not system_prompt:
			return None
		return SystemMessage(content=system_prompt)

	def get_new_message_block(self) -> MessageBlock | None:
		"""Construct a new message block from current view state."""
		view = self.view
		model = view.prompt_panel.ensure_model_compatibility(view.current_model)
		if not model:
			return None
		view.prompt_panel.resize_all_attachments()
		return MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=view.prompt_panel.prompt_text,
				attachments=view.prompt_panel.attachment_files,
			),
			model=AIModelInfo(
				provider_id=view.current_account.provider.id, model_id=model.id
			),
			temperature=view.temperature_spinner.GetValue(),
			top_p=view.top_p_spinner.GetValue(),
			max_tokens=view.max_tokens_spin_ctrl.GetValue(),
			stream=view.stream_mode.GetValue(),
		)

	def get_completion_args(self) -> dict[str, Any] | None:
		"""Get the arguments for the completion request."""
		new_block = self.get_new_message_block()
		if not new_block:
			return None
		view = self.view
		completion_args = {}
		if (
			ProviderCapability.WEB_SEARCH
			in view.current_account.provider.engine_cls.capabilities
		):
			completion_args["web_search_mode"] = view.web_search_mode.GetValue()

		return completion_args | {
			"engine": view.current_engine,
			"system_message": self.get_system_message(),
			"conversation": self.conversation,
			"new_block": new_block,
			"stream": new_block.stream,
		}

	# -- Completion callbacks --

	def cleanup(self):
		"""Stop all active resources before destroying the tab."""
		if self.completion_handler.is_running():
			log.debug("Stopping completion handler before closing tab")
			self.completion_handler.stop_completion(skip_callbacks=True)
		if self.recording_thread and self.recording_thread.is_alive():
			log.debug("Aborting recording thread before closing tab")
			try:
				self.recording_thread.abort()
				self.recording_thread.join(timeout=0.5)
			except Exception as e:
				log.error(
					"Error aborting recording thread: %s", e, exc_info=True
				)
			self.recording_thread = None
		stop_sound()
		self.flush_draft()

	@_guard_destroying
	def _on_completion_start(self):
		"""Called when completion starts."""
		self.view.submit_btn.Disable()
		self.view.stop_completion_btn.Show()
		if config.conf().conversation.focus_history_after_send:
			self.view.messages.SetFocus()

	@_guard_destroying
	def _on_completion_end(self, success: bool):
		"""Called when completion ends."""
		self.view.stop_completion_btn.Hide()
		self.view.submit_btn.Enable()

		if success:
			self._clear_stored_content()

		if success and config.conf().conversation.focus_history_after_send:
			self.view.messages.SetFocus()

	@_guard_destroying
	def _on_stream_chunk(self, chunk: str):
		"""Called for each streaming chunk."""
		self.view.messages.append_stream_chunk(chunk)

	@_guard_destroying
	def _on_stream_start(
		self, new_block: MessageBlock, system_message: Optional[SystemMessage]
	):
		"""Called when streaming starts."""
		self.conversation.add_block(new_block, system_message)
		self.view.messages.display_new_block(new_block, streaming=True)
		self.view.messages.SetInsertionPointEnd()

	@_guard_destroying
	def _on_stream_finish(self, new_block: MessageBlock):
		"""Called when streaming finishes."""
		self.view.messages.a_output.handle_stream_buffer()
		self.view.messages.update_last_segment_length()
		self.service.auto_save_to_db(self.conversation, new_block)

	@_guard_destroying
	def _on_non_stream_finish(
		self, new_block: MessageBlock, system_message: Optional[SystemMessage]
	):
		"""Called when non-streaming completion finishes."""
		self.conversation.add_block(new_block, system_message)
		self.view.messages.display_new_block(new_block)
		if self.view.messages.should_speak_response:
			self.view.messages.a_output.handle(new_block.response.content)
		self.service.auto_save_to_db(self.conversation, new_block)

	# -- Error recovery --

	def _store_prompt_content(self):
		"""Store current prompt content for error recovery."""
		self._stored_prompt_text = self.view.prompt_panel.prompt_text
		self._stored_attachments = (
			self.view.prompt_panel.attachment_files.copy()
		)

	def _restore_prompt_content(self):
		"""Restore previously stored prompt content."""
		if (
			self._stored_prompt_text is not None
			and self._stored_attachments is not None
		):
			self.view.prompt_panel.prompt_text = self._stored_prompt_text
			self.view.prompt_panel.attachment_files = self._stored_attachments
			self.view.prompt_panel.refresh_attachments_list()

	def _clear_stored_content(self):
		"""Clear stored prompt content."""
		self._stored_prompt_text = None
		self._stored_attachments = None

	@_guard_destroying
	def _on_completion_error(self, error_message: str):
		"""Called when a completion error occurs."""
		self._restore_prompt_content()
		self._clear_stored_content()
		self.view.show_enhanced_error(
			_("An error occurred during completion: %s") % error_message,
			_("Completion Error"),
			is_completion_error=True,
		)

	# -- Recording coordination --

	def toggle_recording(self):
		"""Toggle audio recording on/off."""
		if self.recording_thread and self.recording_thread.is_alive():
			self.stop_recording()
		else:
			self.start_recording()

	def start_recording(self):
		"""Start audio recording."""
		cur_provider = self.view.current_engine
		if cur_provider is None:
			return
		if ProviderCapability.STT not in cur_provider.capabilities:
			self.view.show_error(
				_("The selected provider does not support speech-to-text"),
				_("Error"),
			)
			return
		self.view.toggle_record_btn.SetLabel(_("Stop recording") + " (Ctrl+R)")
		self.view.submit_btn.Disable()
		self.transcribe_audio_file()

	def stop_recording(self, abort: bool = False):
		"""Stop audio recording.

		Args:
			abort: If True, abort the recording and transcription process
				entirely instead of stopping normally.
		"""
		if not self.recording_thread:
			return
		if abort:
			self.recording_thread.abort()
		else:
			self.recording_thread.stop()
		if not self.view._is_destroying:
			self.view.toggle_record_btn.SetLabel(_("Record") + " (Ctrl+R)")
			self.view.submit_btn.Enable()

	def transcribe_audio_file(self, audio_file: str = None):
		"""Transcribe an audio file using the current provider's STT.

		Args:
			audio_file: Path to audio file. If None, starts recording.
		"""
		engine = self.view.current_engine
		if engine is None:
			return
		if not self.recording_thread:
			from basilisk.recording_thread import (
				RecordingThread as recording_thread_cls,
			)
		else:
			recording_thread_cls = self.recording_thread.__class__
		self.recording_thread = recording_thread_cls(
			provider_engine=engine,
			recordings_settings=config.conf().recordings,
			callbacks=self,
			audio_file_path=audio_file,
		)
		self.recording_thread.start()

	def on_transcribe_audio_file(self):
		"""Open file dialog and transcribe selected audio file."""
		cur_provider = self.view.current_engine
		if cur_provider is None:
			return
		if ProviderCapability.STT not in cur_provider.capabilities:
			self.view.show_error(
				_("The selected provider does not support speech-to-text"),
				_("Error"),
			)
			return
		audio_file = self.view.ask_audio_file()
		if audio_file:
			self.transcribe_audio_file(audio_file)

	# Recording callbacks (called by RecordingThread)

	@_guard_destroying
	def on_recording_started(self):
		"""Handle the start of audio recording."""
		play_sound("recording_started")
		self.view.SetStatusText(_("Recording..."))

	@_guard_destroying
	def on_recording_stopped(self):
		"""Handle the end of audio recording."""
		play_sound("recording_stopped")
		self.view.SetStatusText(_("Recording stopped"))

	@_guard_destroying
	def on_transcription_started(self):
		"""Handle the start of audio transcription."""
		play_sound("progress", loop=True)
		self.view.SetStatusText(_("Transcribing..."))

	@_guard_destroying
	def on_transcription_received(self, transcription):
		"""Handle a transcription result.

		Args:
			transcription: The transcription result.
		"""
		stop_sound()
		self.view.SetStatusText(_("Ready"))
		self.view.prompt_panel.prompt.AppendText(transcription.text)
		if (
			self.view.prompt_panel.prompt.HasFocus()
			and self.view.GetTopLevelParent().IsShown()
		):
			self.view._handle_accessible_output(transcription.text)
		self.view.prompt_panel.prompt.SetInsertionPointEnd()
		self.view.prompt_panel.set_prompt_focus()

	@_guard_destroying
	def on_transcription_error(self, error):
		"""Handle an error during audio transcription.

		Args:
			error: The error that occurred.
		"""
		stop_sound()
		self.view.SetStatusText(_("Ready"))
		self.view.show_enhanced_error(
			_("An error occurred during transcription: %s") % error,
			_("Transcription Error"),
		)

	# -- Service delegations --

	def generate_conversation_title(self):
		"""Generate a conversation title using the AI model.

		Returns:
			The generated title, or None on failure.
		"""
		if self.completion_handler.is_running():
			self.view.show_error(
				_(
					"A completion is already in progress. Please wait until it finishes."
				),
				_("Error"),
			)
			return
		if not self.conversation.messages:
			return
		model = self.view.current_model
		if not model:
			return
		title = self.service.generate_title(
			engine=self.view.current_engine,
			conversation=self.conversation,
			provider_id=self.view.current_account.provider.id,
			model_id=model.id,
			temperature=self.view.temperature_spinner.GetValue(),
			top_p=self.view.top_p_spinner.GetValue(),
			max_tokens=self.view.max_tokens_spin_ctrl.GetValue(),
			stream=True,  # Required for Anthropic: long requests must use streaming
		)
		if title is None and self.conversation.messages:
			self.view.show_enhanced_error(
				_("An error occurred during title generation"),
				_("Title Generation Error"),
				is_completion_error=True,
			)
		return title

	def save_conversation(self, file_path: str) -> bool:
		"""Save the conversation to a file.

		Args:
			file_path: The target file path.

		Returns:
			True if saved successfully.
		"""
		draft_block = self._build_draft_block()
		success, error = self.service.save_conversation(
			self.conversation, file_path, draft_block
		)
		if not success and error is not None:
			self.view.show_enhanced_error(
				_("An error occurred while saving the conversation: %s")
				% error,
				_("Save Error"),
			)
		return success

	def remove_message_block(self, message_block: MessageBlock):
		"""Remove a message block and refresh the view.

		Args:
			message_block: The message block to remove.
		"""
		self.conversation.remove_block(message_block)
		self.view.refresh_messages(preserve_prompt=True)

	# -- Draft management --

	def on_prompt_text_changed(self):
		"""Handle prompt text changes for draft auto-save debouncing."""
		if self.service.should_auto_save_draft():
			self.view.start_draft_timer(2000)

	def on_draft_timer(self):
		"""Handle draft timer expiration to save draft to DB."""
		if not self.service.should_auto_save_draft():
			return
		self._save_draft_to_db()

	def flush_draft(self):
		"""Immediately save any pending draft to the database."""
		self.view.stop_draft_timer()
		if not self.service.should_auto_save_draft():
			return
		self._save_draft_to_db()

	def _build_draft_block(self) -> MessageBlock | None:
		"""Build a draft MessageBlock from current view state.

		Returns:
			A MessageBlock with no response, or None if empty.
		"""
		view = self.view
		if not view.current_account or not view.current_model:
			return None
		prompt_text = view.prompt_panel.prompt_text
		attachments = view.prompt_panel.attachment_files
		if not prompt_text and not attachments:
			return None
		block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=prompt_text or "",
				attachments=attachments or None,
			),
			model=AIModelInfo(
				provider_id=view.current_account.provider.id,
				model_id=view.current_model.id,
			),
			temperature=view.temperature_spinner.GetValue(),
			max_tokens=view.max_tokens_spin_ctrl.GetValue(),
			top_p=view.top_p_spinner.GetValue(),
			stream=view.stream_mode.GetValue(),
		)
		system_msg = self.get_system_message()
		if system_msg and system_msg in self.conversation.systems:
			block.system_index = list(self.conversation.systems).index(
				system_msg
			)
		return block

	def _save_draft_to_db(self):
		"""Save the current draft to the database."""
		draft_block = self._build_draft_block()
		system_msg = self.get_system_message()
		self.service.save_draft_to_db(
			self.conversation, draft_block, system_msg
		)
