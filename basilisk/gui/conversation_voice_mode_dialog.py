from __future__ import annotations

import tempfile
import threading
from base64 import b64decode
from logging import getLogger
from typing import TYPE_CHECKING, Optional

import wx

from basilisk.config import Account
from basilisk.conversation import (
	Conversation,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.sound_manager import play_sound, stop_sound

from .base_conversation import BaseConversation

if TYPE_CHECKING:
	from basilisk.provider_engine.base_engine import BaseEngine

log = getLogger(__name__)


class ConversationVoiceModeDialog(wx.Dialog, BaseConversation):
	def __init__(
		self,
		parent: wx.Window,
		account: Account,
		title: str = '',
		size: tuple[int, int] = (800, 600),
	) -> None:
		self.account = account
		self.conversation = Conversation()
		self.task = None
		if not title:
			title = _("Voice Mode") + f" - {self.account.provider.name}"
		wx.Dialog.__init__(self, parent=parent, title=title, size=size)

		self.voice_mode = True
		self.init_ui()
		self.update_ui()

	def init_ui(self) -> None:
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)

		label = self.create_model_widget(panel)
		sizer.Add(label, 0, wx.ALL, 5)
		sizer.Add(self.model_list, 0, wx.ALL | wx.EXPAND, 5)

		label = wx.StaticText(
			panel,
			# Translators: This is a label for user prompt in the main window
			label=_("&Voice:"),
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.voice_list = wx.Choice(panel, choices=self.current_engine.voices)
		self.voice_list.SetSelection(0)
		sizer.Add(self.voice_list, 0, wx.ALL | wx.EXPAND, 5)

		label = self.create_system_prompt_widget(panel)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		sizer.Add(self.system_prompt_txt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			panel,
			# Translators: This is a label for user prompt in the main window
			label=_("&Messages:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(
			panel,
			size=(800, 400),
			style=wx.TE_MULTILINE
			| wx.TE_READONLY
			| wx.TE_WORDWRAP
			| wx.HSCROLL,
		)
		# self.messages.Bind(wx.EVT_CONTEXT_MENU, self.on_messages_context_menu)
		# self.messages.Bind(wx.EVT_KEY_DOWN, self.on_messages_key_down)
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			panel,
			# Translators: This is a label for user prompt in the main window
			label=_("&Prompt:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(
			panel,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		# self.prompt.Bind(wx.EVT_KEY_DOWN, self.on_prompt_key_down)
		# self.prompt.Bind(wx.EVT_CONTEXT_MENU, self.on_prompt_context_menu)
		# self.prompt.Bind(wx.EVT_TEXT_PASTE, self.on_prompt_paste)
		sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.submit_btn = wx.Button(panel, wx.ID_OK, label=_("Submit"))
		self.submit_btn.Bind(wx.EVT_BUTTON, self.on_submit)
		button_sizer.Add(self.submit_btn, 0, wx.ALL, 5)

		close_button = wx.Button(panel, wx.ID_CLOSE)
		close_button.Bind(wx.EVT_BUTTON, self.on_close)
		button_sizer.Add(close_button, 0, wx.ALL, 5)
		sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

		panel.SetSizer(sizer)
		sizer.Fit(self)

		self.Bind(wx.EVT_CLOSE, self.on_close)

		self.SetEscapeId(wx.ID_CLOSE)

	@property
	def current_engine(self) -> Optional[BaseEngine]:
		return self.account.provider.engine_cls(self.account)

	def update_model_list(self):
		self.model_list.DeleteAllItems()
		for model in self.get_display_models():
			self.model_list.Append(model)
		if self.model_list.GetItemCount() == 1:
			self.model_list.SetItemState(
				0,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
				wx.LIST_STATE_SELECTED | wx.LIST_STATE_FOCUSED,
			)
		else:
			self.model_list.SetFocus()

	def on_model_change(self, event: wx.ListEvent) -> None:
		pass

	@property
	def current_voice(self) -> str:
		return self.voice_list.GetStringSelection()

	def update_ui(self) -> None:
		self.update_model_list()

		self.Layout()

		self.Centre()

	def toggle_controls(self, enabled: bool) -> None:
		"""
		Toggle the controls for submission
		"""
		self.model_list.Enable(enabled)
		self.prompt.Enable(enabled)
		self.submit_btn.Enable(enabled)

	def _end_task(self, success: bool = True):
		task = self.task
		task.join()
		thread_id = task.ident
		log.debug(f"Task {thread_id} ended")
		self.task = None
		stop_sound()
		if success:
			play_sound("chat_response_received")
		self.toggle_controls(True)

	def _post_completion_without_stream(self, new_block: MessageBlock) -> None:
		self._end_task()
		wav_bytes = b64decode(new_block.response.content.data)
		# TODO: avoid writing to disk
		# play_sound(wav_bytes)
		with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
			f.write(wav_bytes)
			f.flush()
			play_sound(f.name)
		transcript = new_block.response.content.transcript
		# TODO: add to conversation
		self.messages.AppendText(f"User: {new_block.request.content}\n")
		self.messages.AppendText(f"AI: {transcript}\n")
		# self.conversation.messages.append(new_block)
		# self.prompt.Clear()
		# self.display_new_block(new_block)

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
		new_block = engine.completion_response_without_stream(
			response=response, **kwargs
		)
		wx.CallAfter(self._post_completion_without_stream, new_block)

	def on_submit(self, event: wx.CommandEvent) -> None:
		if not self.submit_btn.IsEnabled() or self.task:
			return
		model = self.current_model
		if not model:
			wx.MessageBox(
				_("Please select a model."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			self.model_list.SetFocus()
			return
		voice = self.current_voice
		if not voice:
			wx.MessageBox(
				_("Please select a voice."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			self.voice_list.SetFocus()
			return
		prompt = self.prompt.GetValue()
		if not prompt:
			wx.MessageBox(
				_("Please enter a prompt."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			self.prompt.SetFocus()
			return
		self.toggle_controls(False)
		system_message = None
		if self.system_prompt_txt.GetValue():
			system_message = Message(
				role=MessageRoleEnum.SYSTEM,
				content=self.system_prompt_txt.GetValue(),
			)
		try:
			new_block = MessageBlock(
				request=Message(
					role=MessageRoleEnum.USER, content=self.prompt.GetValue()
				),
				model=model,
				modalities=["text", "audio"],
				audio={"voice": voice, "format": "wav"},
			)
			completion_kw = {
				"engine": self.current_engine,
				"system_message": system_message,
				"conversation": self.conversation,
				"new_block": new_block,
			}
			thread = self.task = threading.Thread(
				target=self._handle_completion, kwargs=completion_kw
			)
			thread.start()
			thread_id = thread.ident
			log.debug(f"Task {thread_id} started")
		except Exception:
			log.exception("Error submitting voice mode request")
			wx.MessageBox(
				_(
					"An error occurred while submitting the request. Please check the logs for more information."
				),
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)

	def on_close(self, event: wx.CloseEvent) -> None:
		"""
		Close the dialog
		"""
		self.EndModal(wx.ID_CLOSE)
