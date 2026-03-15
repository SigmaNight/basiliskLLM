"""Dialog for editing message blocks in a conversation.

This module provides a dialog for editing message blocks, allowing users to modify
prompt text, attachments, model settings, and other parameters. It reuses components
from BaseConversation for consistency in the user interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx

import basilisk.config as config
from basilisk.conversation.content_utils import format_response_for_display
from basilisk.conversation.conversation_model import Conversation, SystemMessage
from basilisk.presenters.edit_block_presenter import EditBlockPresenter

from .base_conversation import BaseConversation
from .prompt_attachments_panel import PromptAttachmentsPanel

if TYPE_CHECKING:
	from .conversation_tab import ConversationTab

logger = logging.getLogger(__name__)


class EditBlockDialog(wx.Dialog, BaseConversation):
	"""Dialog for editing message blocks in a conversation.

	This dialog allows users to edit various properties of a message block,
	including the user prompt, system message, model settings, and other parameters.
	It reuses components from BaseConversation for consistency in the user interface.
	"""

	def __init__(self, parent: ConversationTab, message_block_index: int):
		"""Initialize the edit block dialog.

		Args:
			parent: The parent conversation tab
			message_block_index: The message block index to edit in the conversation
		"""
		wx.Dialog.__init__(
			self,
			parent,
			title=_("Edit Message Block"),
			size=(800, 600),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		BaseConversation.__init__(
			self, account_model_service=parent.account_model_service
		)
		self.conversation: Conversation = parent.conversation
		self.a_output = parent.messages.a_output
		self.block_index = message_block_index
		if not (0 <= self.block_index < len(self.conversation.messages)):
			logger.warning(
				"EditBlockDialog: block_index %d out of range (len=%d)",
				self.block_index,
				len(self.conversation.messages),
			)
			self.block = None
			wx.MessageBox(
				# Translators: Error shown when the message block to edit no longer exists
				_("Message block %d no longer exists in the conversation.")
				% self.block_index,
				# Translators: Title of the error dialog when editing a message block fails
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self,
			)
			wx.CallAfter(self.EndModal, wx.ID_CANCEL)
			return
		self.block = self.conversation.messages[self.block_index]
		self.system_message: SystemMessage | None = None
		if self.block.system_index is not None:
			self.system_message = self.conversation.systems[
				self.block.system_index
			]
		self.speak_response = parent.messages.speak_response

		self.presenter = EditBlockPresenter(
			self, parent.conversation, message_block_index, parent.service
		)

		self.init_ui()
		self.load_message_block_data()

	def get_effective_show_reasoning_blocks(self) -> bool:
		"""Use parent tab's setting when editing from a conversation tab."""
		parent = self.GetParent()
		if hasattr(parent, "get_effective_show_reasoning_blocks"):
			return parent.get_effective_show_reasoning_blocks()
		return config.conf().conversation.show_reasoning_blocks

	def init_ui(self):
		"""Initialize the dialog's user interface components."""
		sizer = wx.BoxSizer(wx.VERTICAL)

		label = self.create_account_widget()
		sizer.Add(
			label,
			proportion=0,
			flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
			border=10,
		)
		sizer.Add(
			self.account_combo,
			proportion=0,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		label = self.create_system_prompt_widget()
		sizer.Add(
			label,
			proportion=0,
			flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
			border=10,
		)
		sizer.Add(
			self.system_prompt_txt,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		response_label = wx.StaticText(
			self,
			# Translators: This is a label for assistant response in the edit dialog
			label=_("&Assistant response:"),
		)
		sizer.Add(
			response_label,
			proportion=0,
			flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
			border=10,
		)
		self.response_txt = wx.TextCtrl(
			self,
			size=(-1, 200),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		sizer.Add(
			self.response_txt,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		self.prompt_panel = PromptAttachmentsPanel(
			self, self.GetParent().conv_storage_path, self.on_regenerate
		)
		sizer.Add(
			self.prompt_panel,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		self.create_settings_section()
		sizer.Add(
			self.settings_section_sizer,
			proportion=0,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
			border=10,
		)

		btn_sizer = wx.StdDialogButtonSizer()

		self.regenerate_btn = wx.Button(
			self,
			# Translators: This is a label for regenerate button
			label=_("&Regenerate Response"),
		)
		self.regenerate_btn.Bind(wx.EVT_BUTTON, self.on_regenerate)

		self.stop_btn = wx.Button(
			self,
			# Translators: This is a label for stop regeneration button
			label=_("Stop completio&n"),
		)
		self.stop_btn.Bind(wx.EVT_BUTTON, self.on_stop_regenerate)
		self.stop_btn.Hide()

		btn_sizer.AddButton(wx.Button(self, wx.ID_OK))
		btn_sizer.AddButton(wx.Button(self, wx.ID_CANCEL))

		self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)
		self.Bind(wx.EVT_BUTTON, self.on_cancel, id=wx.ID_CANCEL)

		btn_sizer.Realize()

		button_row = wx.BoxSizer(wx.HORIZONTAL)
		button_row.Add(
			self.regenerate_btn, proportion=0, flag=wx.RIGHT, border=10
		)
		button_row.Add(self.stop_btn, proportion=0, flag=wx.RIGHT, border=10)

		button_row.Add(btn_sizer, proportion=1, flag=wx.EXPAND)

		sizer.Add(button_row, proportion=0, flag=wx.ALL | wx.EXPAND, border=10)

		self.SetSizer(sizer)

	def _load_account_and_model(self):
		"""Restore account and model selection from block."""
		try:
			model_id = self.block.model.model_id
			provider = self.block.model.provider
			account = next(
				config.accounts().get_accounts_by_provider(provider.name), None
			)
			if account:
				self.set_account_combo(account)
			engine = self.current_engine
			if engine:
				self.prompt_panel.set_engine(engine)
				model = engine.get_model(model_id)
				if model:
					self.set_model_list(model)
			self.update_parameter_controls_visibility()
		except Exception:
			logger.debug(
				"Could not restore block account/model selection", exc_info=True
			)

	def _load_audio_params(self):
		"""Restore output modality and audio voice from block."""
		if hasattr(self, "output_modality_choice"):
			self.output_modality_choice.SetSelection(
				1
				if getattr(self.block, "output_modality", "text") == "audio"
				else 0
			)
		if hasattr(self, "audio_voice_choice"):
			voice = getattr(self.block, "audio_voice", "alloy")
			voices = [
				"alloy",
				"ash",
				"ballad",
				"coral",
				"echo",
				"fable",
				"onyx",
				"nova",
				"sage",
				"shimmer",
				"verse",
				"marin",
				"cedar",
			]
			idx = voices.index(voice) if voice in voices else 0
			self.audio_voice_choice.SetSelection(idx)

	def _load_reasoning_params(self):
		"""Restore reasoning parameters from block."""
		if not hasattr(self, "reasoning_mode"):
			return
		self.reasoning_mode.SetValue(self.block.reasoning_mode)
		self.reasoning_adaptive.SetValue(self.block.reasoning_adaptive)
		if self.block.reasoning_budget_tokens is not None:
			self.reasoning_budget_spin.SetValue(
				self.block.reasoning_budget_tokens
			)
		if self.block.reasoning_effort:
			engine = self.current_engine
			model = self.current_model
			options = ("low", "medium", "high")
			if engine and model:
				spec = engine.get_reasoning_ui_spec(model)
				if spec.effort_options:
					options = spec.effort_options
			val = self.block.reasoning_effort.lower()
			idx = options.index(val) if val in options else len(options) - 1
			self.reasoning_effort_choice.SetSelection(idx)
		self.update_parameter_controls_visibility()

	def load_message_block_data(self):
		"""Load data from the message block into the dialog."""
		if self.system_message:
			self.system_prompt_txt.SetValue(self.system_message.content)
		if self.block.response:
			reasoning = getattr(self.block.response, "reasoning", None)
			content = self.block.response.content
			display = format_response_for_display(
				reasoning, content, self.get_effective_show_reasoning_blocks()
			)
			self.response_txt.SetValue(display)
		self.prompt_panel.prompt_text = self.block.request.content

		if self.block.request.attachments:
			self.prompt_panel.attachment_files = (
				self.block.request.attachments.copy()
			)
			self.prompt_panel.refresh_attachments_list()

		self._load_account_and_model()

		self.temperature_spinner.SetValue(self.block.temperature)
		self.max_tokens_spin_ctrl.SetValue(self.block.max_tokens)
		self.top_p_spinner.SetValue(self.block.top_p)
		self.frequency_penalty_spinner.SetValue(self.block.frequency_penalty)
		self.presence_penalty_spinner.SetValue(self.block.presence_penalty)
		self.seed_spin_ctrl.SetValue(self.block.seed or 0)
		self.top_k_spin_ctrl.SetValue(self.block.top_k or 0)
		if self.block.stop:
			self.stop_text_ctrl.SetValue("\n".join(self.block.stop))
		else:
			self.stop_text_ctrl.SetValue("")
		self.stream_mode.SetValue(self.block.stream)
		if hasattr(self, "web_search_mode"):
			self.web_search_mode.SetValue(
				getattr(self.block, "web_search_mode", False)
			)
		self._load_audio_params()
		self._load_reasoning_params()

	def on_account_change(self, event):
		"""Handle account selection changes.

		Updates the engine and available models.

		Args:
			event: The selection change event
		"""
		# Call the parent method first
		super().on_account_change(event)

		# Update the engine in the prompt_attachments_panel
		if self.current_engine:
			self.prompt_panel.set_engine(self.current_engine)

	def on_ok(self, event: wx.CommandEvent):
		"""Handle the OK button click.

		Delegates to the presenter to validate and save the block.

		Args:
			event: The button event
		"""
		if not self.presenter.save_block():
			event.Skip(False)
			return
		event.Skip()

	def on_cancel(self, event: wx.CommandEvent):
		"""Handle the Cancel button click.

		Stops any active completion and closes the dialog.

		Args:
			event: The button event
		"""
		self.presenter.stop_regenerate()
		event.Skip()

	def on_regenerate(self, event: wx.CommandEvent):
		"""Handle the regenerate button click.

		Delegates to the presenter to start a completion.

		Args:
			event: The button event
		"""
		self.presenter.start_regenerate()

	def on_stop_regenerate(self, event: wx.CommandEvent):
		"""Handle the stop regeneration button click.

		Args:
			event: The button event
		"""
		self.presenter.stop_regenerate()

	@property
	def should_speak_response(self) -> bool:
		"""Check if the response should be spoken.

		This property checks if the speak stream mode is enabled and if the text control has focus or its parent prompt panel has focus.

		Returns:
			True if the stream should be spoken, False otherwise.
		"""
		return (
			self.speak_response
			and (
				self.response_txt.HasFocus()
				or self.prompt_panel.prompt.HasFocus()
			)
			and self.GetTopLevelParent().IsShown()
		)
