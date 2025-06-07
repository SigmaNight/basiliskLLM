"""Dialog for editing message blocks in a conversation.

This module provides a dialog for editing message blocks, allowing users to modify
prompt text, attachments, model settings, and other parameters. It reuses components
from BaseConversation for consistency in the user interface.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import wx
from more_itertools import locate

import basilisk.config as config
from basilisk.conversation.conversation_model import (
	Conversation,
	MessageBlock,
	SystemMessage,
)

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
		BaseConversation.__init__(self)
		self.conversation: Conversation = parent.conversation
		self.block: MessageBlock = self.conversation.messages[
			message_block_index
		]
		self.system_message: SystemMessage | None = None
		if self.block.system_index is not None:
			self.system_message = self.conversation.systems[
				self.block.system_index
			]

		self.accounts_engines = parent.accounts_engines
		self.init_ui()
		self.load_message_block_data()

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
			self, self.GetParent().conv_storage_path
		)
		sizer.Add(
			self.prompt_panel,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		label = self.create_model_widget()
		sizer.Add(
			label,
			proportion=0,
			flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
			border=10,
		)
		sizer.Add(
			self.model_list,
			proportion=0,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=10,
		)

		params_sizer = wx.BoxSizer(wx.HORIZONTAL)

		self.create_temperature_widget()
		temp_sizer = wx.BoxSizer(wx.VERTICAL)
		temp_sizer.Add(
			self.temperature_spinner_label, proportion=0, flag=wx.EXPAND
		)
		temp_sizer.Add(self.temperature_spinner, proportion=0, flag=wx.EXPAND)
		params_sizer.Add(
			temp_sizer, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10
		)

		self.create_max_tokens_widget()
		tokens_sizer = wx.BoxSizer(wx.VERTICAL)
		tokens_sizer.Add(
			self.max_tokens_spin_label, proportion=0, flag=wx.EXPAND
		)
		tokens_sizer.Add(
			self.max_tokens_spin_ctrl, proportion=0, flag=wx.EXPAND
		)
		params_sizer.Add(
			tokens_sizer, proportion=1, flag=wx.EXPAND | wx.RIGHT, border=10
		)

		self.create_top_p_widget()
		top_p_sizer = wx.BoxSizer(wx.VERTICAL)
		top_p_sizer.Add(self.top_p_spinner_label, proportion=0, flag=wx.EXPAND)
		top_p_sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)
		params_sizer.Add(top_p_sizer, proportion=1, flag=wx.EXPAND)

		sizer.Add(
			params_sizer,
			proportion=0,
			flag=wx.EXPAND | wx.TOP | wx.LEFT | wx.RIGHT,
			border=10,
		)

		self.create_stream_widget()
		sizer.Add(
			self.stream_mode,
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
		self.regenerate_btn.Disable()  # To be implemented later

		btn_sizer.AddButton(wx.Button(self, wx.ID_OK))
		btn_sizer.AddButton(wx.Button(self, wx.ID_CANCEL))
		btn_sizer.Realize()

		button_row = wx.BoxSizer(wx.HORIZONTAL)
		button_row.Add(
			self.regenerate_btn, proportion=0, flag=wx.RIGHT, border=10
		)
		button_row.Add(btn_sizer, proportion=1, flag=wx.EXPAND)

		sizer.Add(button_row, proportion=0, flag=wx.ALL | wx.EXPAND, border=10)

		self.SetSizer(sizer)
		self.Bind(wx.EVT_BUTTON, self.on_ok, id=wx.ID_OK)

	def load_message_block_data(self):
		"""Load data from the message block into the dialog."""
		if self.system_message:
			self.system_prompt_txt.SetValue(self.system_message.content)
		if self.block.response:
			self.response_txt.SetValue(self.block.response.content)
		self.prompt_panel.prompt_text = self.block.request.content

		# Set attachments if available
		if self.block.request.attachments:
			self.prompt_panel.attachment_files = (
				self.block.request.attachments.copy()
			)
			self.prompt_panel.refresh_attachments_list()

		# Set account
		accounts = config.accounts()
		account_index = next(
			locate(
				accounts,
				lambda acc: acc.provider.id == self.block.model.provider_id,
			),
			wx.NOT_FOUND,
		)
		if account_index != wx.NOT_FOUND:
			self.account_combo.SetSelection(account_index)
			self.on_account_change(None)

			# Set model
			engine = self.current_engine
			if engine:
				self.prompt_panel.set_engine(engine)
				model = engine.get_model(self.block.model.model_id)
				if model:
					self.set_model_list(model)

		# Set parameters
		self.temperature_spinner.SetValue(self.block.temperature)
		self.max_tokens_spin_ctrl.SetValue(self.block.max_tokens)
		self.top_p_spinner.SetValue(self.block.top_p)
		self.stream_mode.SetValue(self.block.stream)

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

		Updates the original message block with the edited values.

		Args:
			event: The button event
		"""
		model = self.current_model
		account = self.current_account
		if not account and not model:
			wx.MessageBox(
				_("Please select a model"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			event.Skip(False)
			return

		# Check if attachments are valid
		if not self.prompt_panel.check_attachments_valid():
			event.Skip(False)
			return

		# Update request content
		self.block.request.content = self.prompt_panel.prompt_text

		# Update request attachments
		if self.prompt_panel.attachment_files:
			self.block.request.attachments = self.prompt_panel.attachment_files
		else:
			self.block.request.attachments = None

		# Update system message
		system_prompt = self.system_prompt_txt.GetValue()
		if system_prompt:
			system_message = SystemMessage(content=system_prompt)
			system_index = self.conversation.systems.add(system_message)
			self.block.system_index = system_index
		else:
			self.block.system_index = None

		# Update model and parameters
		self.block.model.provider_id = account.provider.id
		self.block.model.model_id = model.id
		self.block.temperature = self.temperature_spinner.GetValue()
		self.block.max_tokens = self.max_tokens_spin_ctrl.GetValue()
		self.block.top_p = self.top_p_spinner.GetValue()
		self.block.stream = self.stream_mode.GetValue()

		# Update response
		if self.block.response:
			self.block.response.content = self.response_txt.GetValue()
		event.Skip()
