"""Presenter for group conversation orchestration logic.

Coordinates sequential LLM responses across multiple ConversationProfile
participants in both normal (user-driven) and debate (autonomous rounds) modes.
Each participant sees the full prior context including all previous responses.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Literal, Optional
from uuid import uuid4

import basilisk.config as config
from basilisk.completion_handler import CompletionHandler
from basilisk.conversation import (
	Conversation,
	GroupParticipant,
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
from basilisk.services.conversation_service import ConversationService
from basilisk.sound_manager import stop_sound

if TYPE_CHECKING:
	from basilisk.views.group_conversation_tab import GroupConversationTab

log = logging.getLogger(__name__)


class GroupConversationPresenter(DestroyGuardMixin):
	"""Orchestrates sequential completions across multiple LLM participants.

	Two operating modes:
	- **normal**: user submits a message → each participant responds in order.
	- **debate**: autonomous rounds where participants respond to each other.

	Attributes:
		view: The GroupConversationTab view this presenter drives.
		service: The ConversationService for persistence.
		conversation: The active conversation model.
		participants: Ordered list of group participants (snapshots).
		bskc_path: Path to the .bskc file, or None.
	"""

	def __init__(
		self,
		view: GroupConversationTab,
		service: ConversationService,
		conversation: Conversation,
		conv_storage_path,
		participants: list[GroupParticipant],
		bskc_path: Optional[str] = None,
	):
		"""Initialize the group conversation presenter.

		Args:
			view: The GroupConversationTab view instance.
			service: The ConversationService instance.
			conversation: The conversation model.
			conv_storage_path: Storage path for attachments.
			participants: Ordered list of GroupParticipant snapshots.
			bskc_path: Path to .bskc file.
		"""
		self.view = view
		self.service = service
		self.conversation = conversation
		self.conv_storage_path = conv_storage_path
		self.participants = participants
		self.bskc_path = bskc_path

		# Chain state
		self._mode: Literal["normal", "debate"] = "normal"
		self._pending_request: Optional[Message] = None
		self._current_participant_index: int = 0
		self._current_group_id: Optional[str] = None
		self._current_round: int = 0
		self._total_rounds: int = 1
		self._is_running_chain: bool = False

		self.completion_handler = CompletionHandler(
			on_completion_start=self._on_completion_start,
			on_completion_end=self._on_completion_end,
			on_stream_chunk=self._on_stream_chunk,
			on_stream_start=self._on_stream_start,
			on_stream_finish=self._on_stream_finish,
			on_non_stream_finish=self._on_non_stream_finish,
			on_error=self._on_completion_error,
		)

	# -- Public API --

	def on_submit(self):
		"""Handle user message submission in normal mode."""
		prompt = self.view.get_prompt_text()
		if not prompt and not self.view.get_attachment_files():
			return
		self._pending_request = Message(
			role=MessageRoleEnum.USER,
			content=prompt,
			attachments=self.view.get_attachment_files() or None,
		)
		self.view.clear_prompt()
		self._mode = "normal"
		self._current_round = 0
		self._total_rounds = 1
		self._current_group_id = str(uuid4())
		self._current_participant_index = 0
		self._is_running_chain = True
		self._submit_next_participant()

	def on_start_debate(self):
		"""Handle debate mode start."""
		prompt = self.view.get_prompt_text()
		if not prompt:
			return
		rounds = self.view.get_debate_rounds()
		self._pending_request = Message(
			role=MessageRoleEnum.USER,
			content=prompt,
			attachments=self.view.get_attachment_files() or None,
		)
		self.view.clear_prompt()
		self._mode = "debate"
		self._current_round = 0
		self._total_rounds = rounds
		self._current_group_id = str(uuid4())
		self._current_participant_index = 0
		self._is_running_chain = True
		self._submit_next_participant()

	def on_stop(self):
		"""Stop the running chain."""
		self.completion_handler.stop_completion()
		self._is_running_chain = False
		self._on_chain_complete()

	def cleanup(self):
		"""Stop all active resources before destroying the tab."""
		if self.completion_handler.is_running():
			log.debug("Stopping completion handler before closing tab")
			self.completion_handler.stop_completion(skip_callbacks=True)
		stop_sound()

	# -- Chain orchestration --

	def _submit_next_participant(self):
		"""Submit a completion for the current participant in the chain."""
		participant = self.participants[self._current_participant_index]
		position = self._current_participant_index

		# Populate the profile name map so base_engine prefixes responses.
		self.conversation._profile_name_map = {
			str(p.profile_id): p.name for p in self.participants
		}

		# Resolve account and engine for this participant
		account = self._resolve_account(participant)
		if account is None:
			log.error(
				"Cannot resolve account for participant %s, stopping chain",
				participant.name,
			)
			self._is_running_chain = False
			self._on_chain_complete()
			return
		engine = account.provider.engine_cls(account)

		# Build the system message from the participant's snapshot
		system_message: Optional[SystemMessage] = None
		if participant.system_prompt:
			system_message = SystemMessage(content=participant.system_prompt)

		# For debate rounds > 0 use an empty sentinel request so the model
		# responds only based on conversation history.
		if self._current_round > 0:
			request_content = ""
		else:
			request_content = (
				self._pending_request.content if self._pending_request else ""
			)
		request_attachments = (
			self._pending_request.attachments
			if (
				self._pending_request
				and self._current_round == 0
				and position == 0
			)
			else None
		)

		new_block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=request_content,
				attachments=request_attachments,
			),
			model=AIModelInfo(
				provider_id=account.provider.id,
				model_id=participant.ai_model_info.model_id,
			),
			temperature=participant.temperature,
			max_tokens=participant.max_tokens,
			top_p=participant.top_p,
			stream=participant.stream_mode,
			profile_id=participant.profile_id,
			group_id=self._current_group_id,
			group_position=position,
		)

		self.view.set_active_participant(self._current_participant_index)
		self.completion_handler.start_completion(
			engine=engine,
			system_message=system_message,
			conversation=self.conversation,
			new_block=new_block,
			stream=new_block.stream,
		)

	def _resolve_account(self, participant: GroupParticipant):
		"""Resolve the live Account object for a participant.

		Falls back to the first account for the participant's provider if the
		original account is no longer present.

		Args:
			participant: The group participant snapshot.

		Returns:
			The resolved Account, or None if unavailable.
		"""
		accounts = config.accounts()
		provider_id = participant.ai_model_info.provider_id
		# Try to find the exact account from the snapshot
		account_id = participant.account_info.get("id")
		if account_id:
			from uuid import UUID

			try:
				uid = UUID(str(account_id))
				for acct in accounts:
					if acct.id == uid:
						return acct
			except ValueError, Exception:
				pass
		# Fall back to first account for this provider
		for acct in accounts:
			if acct.provider.id == provider_id:
				return acct
		return None

	# -- Completion callbacks --

	@_guard_destroying
	def _on_completion_start(self):
		"""Called when a completion starts."""
		self.view.on_completion_start()

	@_guard_destroying
	def _on_completion_end(self, success: bool):
		"""Called when a completion ends."""
		if not success:
			self._is_running_chain = False
			self._on_chain_complete()
			return
		# Advance to next participant
		self._current_participant_index += 1
		if self._current_participant_index < len(self.participants):
			# More participants in this round
			self._submit_next_participant()
		elif (
			self._mode == "debate"
			and self._current_round < self._total_rounds - 1
		):
			# Start next debate round
			self._current_round += 1
			self._current_group_id = str(uuid4())
			self._current_participant_index = 0
			self.view.announce_round(self._current_round + 1)
			self._submit_next_participant()
		else:
			# Chain complete
			self._is_running_chain = False
			self._on_chain_complete()

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

	@_guard_destroying
	def _on_completion_error(self, error_message: str):
		"""Called when a completion error occurs."""
		self._is_running_chain = False
		self._on_chain_complete()
		self.view.show_enhanced_error(
			_("An error occurred during completion: %s") % error_message,
			_("Completion Error"),
			is_completion_error=True,
		)

	def _on_chain_complete(self):
		"""Called when the full chain has completed or been stopped."""
		self.conversation._profile_name_map = {}
		self.view.set_active_participant(None)
		self.view.on_chain_complete()

	# -- Service delegations --

	def save_conversation(self, file_path: str) -> bool:
		"""Save the conversation to a file.

		Args:
			file_path: The target file path.

		Returns:
			True if saved successfully.
		"""
		success, error = self.service.save_conversation(
			self.conversation, file_path, None
		)
		if not success and error is not None:
			self.view.show_enhanced_error(
				_("An error occurred while saving the conversation: %s")
				% error,
				_("Save Error"),
			)
		return success

	def flush_draft(self):
		"""No-op: group chats don't use draft blocks."""
