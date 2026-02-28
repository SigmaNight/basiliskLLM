"""Presenter for EditBlockDialog orchestration logic.

Coordinates between the EditBlockDialog view, CompletionHandler, and the
conversation model. Owns the completion handler and exposes the
start/stop/save interface used by the dialog.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import basilisk.config as config
from basilisk.completion_handler import CompletionHandler
from basilisk.conversation.conversation_model import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
	SystemMessage,
)
from basilisk.presenters.presenter_mixins import DestroyGuardMixin
from basilisk.provider_ai_model import AIModelInfo

if TYPE_CHECKING:
	from basilisk.views.edit_block_dialog import EditBlockDialog

log = logging.getLogger(__name__)


class EditBlockPresenter(DestroyGuardMixin):
	"""Orchestrates completion and save flows for EditBlockDialog.

	The presenter holds the CompletionHandler and implements the callbacks
	that the handler invokes on completion events.  UI mutations are
	performed by calling methods / setting properties on ``self.view``
	(MVP pattern).

	Attributes:
		view: The EditBlockDialog that owns this presenter.
		conversation: The conversation model.
		block_index: Index of the edited block in conversation.messages.
		block: The MessageBlock being edited.
		completion_handler: Handler for AI completions.
	"""

	def __init__(
		self,
		view: EditBlockDialog,
		conversation: Conversation,
		block_index: int,
	):
		"""Initialise the presenter.

		Args:
			view: The EditBlockDialog view instance.
			conversation: The active conversation model.
			block_index: Index of the block to edit in conversation.messages.
		"""
		self.view = view
		self.conversation = conversation
		self.block_index = block_index
		self.block: MessageBlock = conversation.messages[block_index]

		self.completion_handler = CompletionHandler(
			on_completion_start=self._on_regenerate_start,
			on_completion_end=self._on_regenerate_end,
			on_stream_chunk=self._on_stream_chunk,
			on_stream_start=self._on_stream_start,
			on_stream_finish=self._on_stream_finish,
			on_non_stream_finish=self._on_non_stream_finish,
		)

	# ------------------------------------------------------------------
	# Public interface
	# ------------------------------------------------------------------

	def start_regenerate(self) -> bool:
		"""Validate inputs and start a completion for the edited block.

		A temporary MessageBlock is constructed from the current view state
		and passed to the CompletionHandler.  The block is NOT added to
		``conversation.messages`` (unlike ConversationPresenter) because we
		are editing an existing block.

		Returns:
			True if completion was started, False if validation failed.
		"""
		model = self.view.prompt_panel.ensure_model_compatibility(
			self.view.current_model
		)
		if not model:
			return False
		account = self.view.current_account
		if not account:
			return False
		if not self.view.prompt_panel.check_attachments_valid():
			return False

		system_message: Optional[SystemMessage] = None
		system_prompt = self.view.system_prompt_txt.GetValue()
		if system_prompt:
			system_message = SystemMessage(content=system_prompt)

		temp_block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=self.view.prompt_panel.prompt_text,
				attachments=self.view.prompt_panel.attachment_files or None,
			),
			model_id=model.id,
			provider_id=account.provider.id,
			temperature=self.view.temperature_spinner.GetValue(),
			top_p=self.view.top_p_spinner.GetValue(),
			max_tokens=self.view.max_tokens_spin_ctrl.GetValue(),
			stream=self.view.stream_mode.GetValue(),
		)

		self.completion_handler.start_completion(
			engine=self.view.current_engine,
			system_message=system_message,
			conversation=self.conversation,
			new_block=temp_block,
			stream=temp_block.stream,
			stop_block_index=self.block_index,
		)
		return True

	def stop_regenerate(self) -> None:
		"""Stop any active completion."""
		self.completion_handler.stop_completion()

	def save_block(self) -> bool:
		"""Validate and persist view state into the edited MessageBlock.

		Mutates ``self.block`` in-place (request content, attachments,
		system_index, model, temperature, max_tokens, top_p, stream, and
		optionally response content).

		Returns:
			True if the block was saved successfully, False if validation
			failed (model or account missing, or attachments invalid).
		"""
		model = self.view.prompt_panel.ensure_model_compatibility(
			self.view.current_model
		)
		account = self.view.current_account
		if not account or not model:
			return False
		if not self.view.prompt_panel.check_attachments_valid():
			return False

		# Update request content and attachments
		self.block.request.content = self.view.prompt_panel.prompt_text
		self.block.request.attachments = (
			self.view.prompt_panel.attachment_files or None
		)

		# Update system message reference
		system_prompt = self.view.system_prompt_txt.GetValue()
		if system_prompt:
			system_message = SystemMessage(content=system_prompt)
			system_index = self.conversation.systems.add(system_message)
			self.block.system_index = system_index
		else:
			self.block.system_index = None

		# Update model and generation parameters
		self.block.model = AIModelInfo(
			provider_id=account.provider.id, model_id=model.id
		)
		self.block.temperature = self.view.temperature_spinner.GetValue()
		self.block.max_tokens = self.view.max_tokens_spin_ctrl.GetValue()
		self.block.top_p = self.view.top_p_spinner.GetValue()
		self.block.stream = self.view.stream_mode.GetValue()

		# Update response if present
		if self.block.response:
			self.block.response.content = self.view.response_txt.GetValue()

		return True

	# ------------------------------------------------------------------
	# CompletionHandler callbacks (private)
	# ------------------------------------------------------------------

	def _on_regenerate_start(self) -> None:
		"""Hide regenerate button, show stop button, clear response area."""
		self.view.regenerate_btn.Hide()
		self.view.stop_btn.Show()
		self.view.response_txt.SetValue("")
		self.view.Layout()

	def _on_regenerate_end(self, success: bool) -> None:
		"""Swap regenerate/stop buttons; optionally focus response area.

		Args:
			success: True if the completion ended successfully.
		"""
		self.view.stop_btn.Hide()
		self.view.regenerate_btn.Show()
		self.view.Layout()
		if success and config.conf().conversation.focus_history_after_send:
			self.view.response_txt.SetFocus()

	def _on_stream_start(
		self, new_block: MessageBlock, system_message: Optional[SystemMessage]
	) -> None:
		"""No-op: the block is not added to the conversation here.

		Args:
			new_block: The temporary block being completed.
			system_message: Optional system message used for this completion.
		"""

	def _on_stream_finish(self, new_block: MessageBlock) -> None:
		"""Flush the accessible-output stream buffer.

		Args:
			new_block: The completed temporary block.
		"""
		self.view.a_output.handle_stream_buffer()

	def _on_non_stream_finish(
		self, new_block: MessageBlock, system_message: Optional[SystemMessage]
	) -> None:
		"""Display the completed response and optionally speak it.

		Args:
			new_block: The completed temporary block with response content.
			system_message: Optional system message used for this completion.
		"""
		self.view.response_txt.SetValue(new_block.response.content)
		if self.view.should_speak_response:
			self.view.a_output.handle(new_block.response.content)

	def _on_stream_chunk(self, chunk: str) -> None:
		"""Append a streaming chunk to the response control.

		Preserves the insertion point so the cursor stays put, and speaks
		the chunk through the accessible output if appropriate.

		Args:
			chunk: The latest text chunk from the stream.
		"""
		pos = self.view.response_txt.GetInsertionPoint()
		if self.view.should_speak_response:
			self.view.a_output.handle_stream_buffer(new_text=chunk)
		self.view.response_txt.AppendText(chunk)
		self.view.response_txt.SetInsertionPoint(pos)
