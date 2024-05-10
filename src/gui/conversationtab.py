from uuid import UUID
import logging
import os
import threading
import time
import wx

import config
from conversation import Conversation, Message, MessageBlock, MessageRoleEnum
from provideraimodel import ProviderAIModel
from providerengine import BaseEngine
from soundmanager import play_sound, stop_sound

log = logging.getLogger(__name__)


class ConversationTab(wx.Panel):
	def __init__(self, parent):
		wx.Panel.__init__(self, parent)
		self.conversation = Conversation()
		self.task = None
		self.accounts_engines: dict[UUID, BaseEngine] = {}
		self.init_ui()
		self.init_data()
		self.update_ui()

	def init_ui(self):
		sizer = wx.BoxSizer(wx.VERTICAL)

		label = wx.StaticText(
			self,
			# Translators: This is a label for account in the main window
			label=_("&Account:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.account_combo = wx.ComboBox(
			self, style=wx.CB_READONLY, choices=self.get_display_accounts()
		)
		self.account_combo.Bind(wx.EVT_COMBOBOX, self.on_account_change)
		if len(self.account_combo.GetItems()) > 0:
			self.account_combo.SetSelection(0)
		sizer.Add(self.account_combo, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for system prompt in the main window
			label=_("S&ystem prompt:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.system_prompt_txt = wx.TextCtrl(self, style=wx.TE_MULTILINE)
		sizer.Add(self.system_prompt_txt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Messages:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(
			self, style=wx.TE_MULTILINE | wx.TE_READONLY
		)
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Prompt:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(self, style=wx.TE_MULTILINE)
		self.prompt.Bind(wx.EVT_KEY_DOWN, self.on_prompt_key_down)
		self.prompt.Bind(wx.EVT_CONTEXT_MENU, self.on_prompt_context_menu)
		sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		label = wx.StaticText(self, label=_("M&odels:"))
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.model_list = wx.ListCtrl(self, style=wx.LC_REPORT)
		self.model_list.InsertColumn(0, _("Name"))
		self.model_list.InsertColumn(1, _("Context window"))
		self.model_list.InsertColumn(2, _("Max tokens"))
		sizer.Add(self.model_list, proportion=2, flag=wx.EXPAND)
		self.model_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_model_change)
		self.model_list.Bind(wx.EVT_KEY_DOWN, self.on_model_key_down)

		label = wx.StaticText(
			self,
			# Translators: This is a label for max tokens in the main window
			label=_("Max to&kens:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.max_tokens_spin_ctrl = wx.SpinCtrl(
			self, value='1024', min=1, max=64000
		)
		sizer.Add(self.max_tokens_spin_ctrl, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for temperature in the main window
			label=_("&Temperature:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.temperature_spinner = wx.SpinCtrl(
			self, value="100", min=0, max=200
		)
		sizer.Add(self.temperature_spinner, proportion=0, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for top P in the main window
			label=_("Probability &Mass (top P):"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.top_p_spinner = wx.SpinCtrl(self, value="100", min=0, max=100)
		sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)

		self.stream_mode = wx.CheckBox(
			self,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)
		sizer.Add(self.stream_mode, proportion=0, flag=wx.EXPAND)

		self.submit_btn = wx.Button(
			self,
			# Translators: This is a label for submit button in the main window
			label=_("Su&bmit (Ctrl+Enter)"),
		)
		self.submit_btn.Bind(wx.EVT_BUTTON, self.on_submit)
		self.submit_btn.SetDefault()
		sizer.Add(self.submit_btn, proportion=0, flag=wx.EXPAND)

		self.SetSizerAndFit(sizer)

	def init_data(self):
		self.on_account_change(None)
		self.on_model_change(None)

	def update_ui(self):
		controls = (
			self.temperature_spinner,
			self.top_p_spinner,
			self.stream_mode,
		)
		for control in controls:
			control.Show(config.conf.general.advanced_mode)
		self.Layout()

	def on_account_change(self, event):
		account_index = self.account_combo.GetSelection()
		if account_index == wx.NOT_FOUND:
			if not config.conf.accounts:
				if (
					wx.MessageBox(
						_(
							"Please add an account first. Do you want to add an account now?"
						),
						_("No account configured"),
						wx.YES_NO | wx.ICON_QUESTION,
					)
					== wx.YES
				):
					self.GetParent().GetParent().GetParent().on_manage_accounts(
						None
					)
					self.on_config_change()
			return
		account = config.conf.accounts[account_index]
		self.accounts_engines.setdefault(
			account.id, account.provider.engine_cls(account)
		)
		self.model_list.DeleteAllItems()
		for i, model in enumerate(self.get_display_models()):
			self.model_list.InsertItem(i, model[0])
			self.model_list.SetItem(i, 1, model[1])
			self.model_list.SetItem(i, 2, model[2])
		self.model_list.SetItemState(
			0,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
		)

	def on_model_change(self, event):
		model_index = self.model_list.GetFirstSelected()
		if model_index == wx.NOT_FOUND:
			return
		model = self.current_engine.models[model_index]
		self.temperature_spinner.SetMax(int(model.max_temperature * 100))
		self.temperature_spinner.SetValue(
			str(int(model.max_temperature / 2 * 100))
		)
		max_tokens = model.max_output_tokens
		if max_tokens < 1:
			max_tokens = model.context_window
		self.max_tokens_spin_ctrl.SetMax(max_tokens)
		self.max_tokens_spin_ctrl.SetValue(max_tokens // 2)

	def refresh_accounts(self):
		account_index = self.account_combo.GetSelection()
		account_id = None
		if account_index != wx.NOT_FOUND:
			account_id = config.conf.accounts[account_index].id
		self.account_combo.Clear()
		self.account_combo.AppendItems(self.get_display_accounts())
		account_index = wx.NOT_FOUND
		if account_id:
			for i, account in enumerate(config.conf.accounts):
				if account.id == account_id:
					account_index = i
					break
		if account_index != wx.NOT_FOUND:
			self.account_combo.SetSelection(account_index)
		elif self.account_combo.GetCount() > 0:
			self.account_combo.SetSelection(0)
			self.account_combo.SetFocus()

	def on_config_change(self):
		self.refresh_accounts()
		self.on_account_change(None)
		self.on_model_change(None)
		self.update_ui()

	def add_standard_context_menu_items(self, menu: wx.Menu):
		menu.Append(wx.ID_UNDO)
		menu.Append(wx.ID_REDO)
		menu.Append(wx.ID_CUT)
		menu.Append(wx.ID_COPY)
		menu.Append(wx.ID_PASTE)
		menu.Append(wx.ID_SELECTALL)

	def on_prompt_context_menu(self, event):
		menu = wx.Menu()
		item = wx.MenuItem(
			menu, wx.ID_ANY, _("Insert previous prompt") + " (Ctrl+Up)"
		)
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.insert_previous_prompt, item)

		item = wx.MenuItem(menu, wx.ID_ANY, _("Submit") + " (Ctrl+Enter)")
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.on_submit, item)

		self.add_standard_context_menu_items(menu)
		self.prompt.PopupMenu(menu)
		menu.Destroy()

	def on_prompt_key_down(self, event):
		key_code = event.GetKeyCode()
		modifiers = event.GetModifiers()
		if (
			modifiers == wx.ACCEL_CTRL
			and key_code == wx.WXK_UP
			and not self.prompt.GetValue()
		):
			self.insert_previous_prompt()
		elif modifiers == wx.ACCEL_CTRL and key_code == wx.WXK_RETURN:
			self.on_submit(event)
		event.Skip()

	def on_model_key_down(self, event):
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_submit(event)
		event.Skip()

	def on_key_down(self, event):
		if (
			event.GetModifiers() == wx.ACCEL_CTRL
			and event.GetKeyCode() == wx.WXK_RETURN
		):
			self.on_submit(event)
		event.Skip()

	def insert_previous_prompt(self, event=None):
		if self.conversation.messages:
			last_user_message = self.conversation.messages[-1].request.content
			self.prompt.SetValue(last_user_message)

	def get_display_accounts(self) -> list:
		accounts = []
		for account in config.conf.accounts:
			name = account.name
			organization = account.active_organization or _("Personal")
			provider_name = account.provider.name
			accounts.append(f"{name} ({organization}) - {provider_name}")
		return accounts

	def display_new_block(self, new_block: MessageBlock):
		if not self.messages.IsEmpty():
			self.messages.AppendText(os.linesep)
		self.messages.AppendText(
			f"{new_block.request.role.value}: {new_block.request.content}"
		)
		self.messages.AppendText(os.linesep)
		pos = self.messages.GetInsertionPoint()
		if new_block.response:
			self.messages.AppendText(
				f"{new_block.response.role.value}: {new_block.response.content}"
			)
			if new_block.response.content:
				self.messages.AppendText(os.linesep)
		self.messages.SetInsertionPoint(pos)

	def update_messages(self):
		self.messages.Clear()
		for block in self.conversation.messages:
			self.display_new_block(block)

	@property
	def current_engine(self) -> BaseEngine:
		account_index = self.account_combo.GetSelection()
		account = config.conf.accounts[account_index]
		return self.accounts_engines[account.id]

	@property
	def current_model(self) -> ProviderAIModel:
		model_index = self.model_list.GetFirstSelected()
		if model_index == wx.NOT_FOUND:
			return
		return self.current_engine.models[model_index]

	def get_display_models(self) -> list[tuple[str, str, str]]:
		return [m.display_model for m in self.current_engine.models]

	def on_submit(self, event):
		model = self.current_model
		if not model:
			wx.MessageBox(
				_("Please select a model"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		system_message = None
		if self.system_prompt_txt.GetValue():
			system_message = Message(
				role=MessageRoleEnum.SYSTEM,
				content=self.system_prompt_txt.GetValue(),
			)
		new_block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER, content=self.prompt.GetValue()
			),
			model=model,
			temperature=self.temperature_spinner.GetValue() / 100,
			top_p=self.top_p_spinner.GetValue() / 100,
			max_tokens=self.max_tokens_spin_ctrl.GetValue(),
			stream=self.stream_mode.GetValue(),
		)
		completion_kw = {
			"engine": self.current_engine,
			"system_message": system_message,
			"conversation": self.conversation,
			"new_block": new_block,
			"stream": new_block.stream,
		}
		log.debug(f"Completion params: {completion_kw}")
		if self.task:
			wx.MessageBox(
				_("A task is already running. Please wait for it to complete."),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		thread = self.task = threading.Thread(
			target=self._handle_completion, kwargs=completion_kw
		)
		thread.start()
		thread_id = thread.ident
		log.debug(f"Task {thread_id} started")

	def _handle_completion(self, engine: BaseEngine, **kwargs):
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
		if kwargs.get("stream", False):
			new_block.response = Message(
				role=MessageRoleEnum.ASSISTANT, content=""
			)
			wx.CallAfter(self.messages.SetFocus)
			wx.CallAfter(self._pre_handle_completion_with_stream, new_block)
			for chunk in self.current_engine.completion_response_with_stream(
				response
			):
				new_block.response.content += chunk
				wx.CallAfter(self._handle_completion_with_stream, chunk)
			wx.CallAfter(self._post_completion_with_stream, new_block)
		else:
			new_block = engine.completion_response_without_stream(
				response=response, **kwargs
			)
			wx.CallAfter(self._post_completion_without_stream, new_block)

	def _pre_handle_completion_with_stream(self, new_block: MessageBlock):
		self.conversation.messages.append(new_block)
		self.display_new_block(new_block)
		self.messages.SetInsertionPointEnd()
		self.prompt.Clear()
		self.last_time = time.time()

	def _handle_completion_with_stream(self, chunk: str):
		pos = self.messages.GetInsertionPoint()
		self.messages.AppendText(chunk)
		self.messages.SetInsertionPoint(pos)
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _post_completion_with_stream(self, new_block: MessageBlock):
		self._end_task()

	def _post_completion_without_stream(self, new_block: MessageBlock):
		self._end_task()
		self.conversation.messages.append(new_block)
		self.display_new_block(new_block)
		self.prompt.Clear()

	def _end_task(self, success: bool = True):
		task = self.task
		task.join()
		thread_id = task.ident
		log.debug(f"Task {thread_id} ended")
		self.task = None
		stop_sound()
		if success:
			play_sound("chat_response_received")
