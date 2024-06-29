import logging
import os
import re
import threading
import time
import wx
import basilisk.config as config
from uuid import UUID

from basilisk.conversation import (
	Conversation,
	ImageUrlMessageContent,
	TextMessageContent,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk import globalvars
from basilisk.imagefile import ImageFile, URL_PATTERN, get_image_dimensions
from basilisk.provideraimodel import ProviderAIModel
from basilisk.providercapability import ProviderCapability
from basilisk.providerengine import BaseEngine
from basilisk.recordingthread import RecordingThread
from basilisk.soundmanager import play_sound, stop_sound

log = logging.getLogger(__name__)


class ConversationTab(wx.Panel):
	def __init__(self, parent: wx.Window):
		wx.Panel.__init__(self, parent)
		self.SetStatusText = parent.GetParent().GetParent().SetStatusText
		self.conversation = Conversation()
		self.image_files = []
		self.last_time = 0
		self.recording_thread: RecordingThread = None
		self.task = None
		self.stream_buffer = ""
		self._messages_already_focused = False
		self._stop_completion = False
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
		self.system_prompt_txt = wx.TextCtrl(
			self,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		sizer.Add(self.system_prompt_txt, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Messages:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.messages = wx.TextCtrl(
			self,
			size=(800, 400),
			style=wx.TE_MULTILINE
			| wx.TE_READONLY
			| wx.TE_WORDWRAP
			| wx.HSCROLL,
		)
		sizer.Add(self.messages, proportion=1, flag=wx.EXPAND)

		label = wx.StaticText(
			self,
			# Translators: This is a label for user prompt in the main window
			label=_("&Prompt:"),
		)
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.prompt = wx.TextCtrl(
			self,
			size=(800, 100),
			style=wx.TE_MULTILINE | wx.TE_WORDWRAP | wx.HSCROLL,
		)
		self.prompt.Bind(wx.EVT_KEY_DOWN, self.on_prompt_key_down)
		self.prompt.Bind(wx.EVT_CONTEXT_MENU, self.on_prompt_context_menu)
		sizer.Add(self.prompt, proportion=1, flag=wx.EXPAND)
		self.prompt.SetFocus()

		self.images_list_label = wx.StaticText(
			self,
			# Translators: This is a label for models in the main window
			label=_("&Images:"),
		)
		sizer.Add(self.images_list_label, proportion=0, flag=wx.EXPAND)
		self.images_list = wx.ListCtrl(
			self, size=(800, 100), style=wx.LC_REPORT
		)
		self.images_list.Bind(wx.EVT_CONTEXT_MENU, self.on_images_context_menu)
		self.images_list.Bind(wx.EVT_KEY_DOWN, self.on_images_key_down)
		self.images_list.InsertColumn(0, _("Name"))
		self.images_list.InsertColumn(1, _("Size"))
		self.images_list.InsertColumn(2, _("Dimensions"))
		self.images_list.InsertColumn(3, _("Path"))
		self.images_list.SetColumnWidth(0, 200)
		self.images_list.SetColumnWidth(1, 100)
		self.images_list.SetColumnWidth(2, 100)
		self.images_list.SetColumnWidth(3, 200)
		sizer.Add(self.images_list, proportion=0, flag=wx.ALL | wx.EXPAND)

		label = wx.StaticText(self, label=_("M&odels:"))
		sizer.Add(label, proportion=0, flag=wx.EXPAND)
		self.model_list = wx.ListCtrl(self, style=wx.LC_REPORT)
		self.model_list.InsertColumn(0, _("Name"))
		self.model_list.InsertColumn(1, _("Context window"))
		self.model_list.InsertColumn(2, _("Max tokens"))
		self.model_list.SetColumnWidth(0, 200)
		self.model_list.SetColumnWidth(1, 100)
		self.model_list.SetColumnWidth(2, 100)
		sizer.Add(self.model_list, proportion=0, flag=wx.ALL | wx.EXPAND)
		self.model_list.Bind(wx.EVT_LIST_ITEM_SELECTED, self.on_model_change)
		self.model_list.Bind(wx.EVT_KEY_DOWN, self.on_model_key_down)

		self.max_tokens_label = wx.StaticText(
			self,
			# Translators: This is a label for max tokens in the main window
			label=_("Max to&kens:"),
		)
		sizer.Add(self.max_tokens_label, proportion=0, flag=wx.EXPAND)
		self.max_tokens_spin_ctrl = wx.SpinCtrl(
			self, value='0', min=0, max=2000000
		)
		sizer.Add(self.max_tokens_spin_ctrl, proportion=0, flag=wx.EXPAND)

		self.temperature_label = wx.StaticText(
			self,
			# Translators: This is a label for temperature in the main window
			label=_("&Temperature:"),
		)
		sizer.Add(self.temperature_label, proportion=0, flag=wx.EXPAND)
		self.temperature_spinner = wx.SpinCtrl(
			self, value="100", min=0, max=200
		)
		sizer.Add(self.temperature_spinner, proportion=0, flag=wx.EXPAND)

		self.top_p_label = wx.StaticText(
			self,
			# Translators: This is a label for top P in the main window
			label=_("Probabilit&y Mass (top P):"),
		)
		sizer.Add(self.top_p_label, proportion=0, flag=wx.EXPAND)
		self.top_p_spinner = wx.SpinCtrl(self, value="100", min=0, max=100)
		sizer.Add(self.top_p_spinner, proportion=0, flag=wx.EXPAND)

		self.stream_mode = wx.CheckBox(
			self,
			# Translators: This is a label for stream mode in the main window
			label=_("&Stream mode"),
		)
		self.stream_mode.SetValue(True)
		sizer.Add(self.stream_mode, proportion=0, flag=wx.EXPAND)

		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

		self.submit_btn = wx.Button(
			self,
			# Translators: This is a label for submit button in the main window
			label=_("Su&bmit (Ctrl+Enter)"),
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

		sizer.Add(btn_sizer, proportion=0, flag=wx.EXPAND)

		self.SetSizerAndFit(sizer)

	def init_data(self):
		self.on_account_change(None)
		self.on_model_change(None)
		self.refresh_images_list()

	def update_ui(self):
		controls = (
			self.max_tokens_label,
			self.max_tokens_spin_ctrl,
			self.temperature_label,
			self.temperature_spinner,
			self.top_p_label,
			self.top_p_spinner,
			self.stream_mode,
		)
		for control in controls:
			control.Enable(config.conf.general.advanced_mode)
			control.Show(config.conf.general.advanced_mode)
		self.Layout()

	def on_account_change(self, event: wx.CommandEvent):
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
		self.toggle_record_btn.Enable(
			ProviderCapability.STT in account.provider.engine_cls.capabilities
		)

	def on_images_context_menu(self, event: wx.ContextMenuEvent):
		selected = self.images_list.GetFirstSelected()
		menu = wx.Menu()

		if selected != wx.NOT_FOUND:
			item = wx.MenuItem(
				menu, wx.ID_ANY, _("Remove selected image") + " (Del)"
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_images_remove, item)

			item = wx.MenuItem(
				menu, wx.ID_ANY, _("Copy image URL") + " (Ctrl+C)"
			)
			menu.Append(item)
			self.Bind(wx.EVT_MENU, self.on_copy_image_url, item)

		item = wx.MenuItem(menu, wx.ID_ANY, _("Add image files..."))
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.add_image_files, item)

		item = wx.MenuItem(menu, wx.ID_ANY, _("Add image URL..."))
		menu.Append(item)
		self.Bind(wx.EVT_MENU, self.add_image_url, item)

		self.images_list.PopupMenu(menu)
		menu.Destroy()

	def on_images_key_down(self, event: wx.KeyEvent):
		key_code = event.GetKeyCode()
		modifiers = event.GetModifiers()
		if modifiers == wx.MOD_CONTROL and key_code == ord("C"):
			self.on_copy_image_url(None)
		if modifiers == wx.MOD_NONE and key_code == wx.WXK_DELETE:
			self.on_images_remove(None)
		event.Skip()

	def add_image_files(self, event: wx.CommandEvent = None):
		file_dialog = wx.FileDialog(
			self,
			message=_("Select one or more image files"),
			style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST | wx.FD_MULTIPLE,
			wildcard=_("Image files")
			+ " (*.png;*.jpeg;*.jpg;*.gif)|*.png;*.jpeg;*.jpg;*.gif",
		)
		if file_dialog.ShowModal() == wx.ID_OK:
			paths = file_dialog.GetPaths()
			self.add_images(paths)
		file_dialog.Destroy()

	def add_image_url(self, event: wx.CommandEvent = None):
		url_dialog = wx.TextEntryDialog(
			self,
			# Translators: This is a label for image URL in conversation tab
			message=_("Enter the URL of the image:"),
			caption=_("Add image URL"),
		)
		if url_dialog.ShowModal() != wx.ID_OK:
			return
		url = url_dialog.GetValue()
		if not url:
			return
		url_pattern = re.compile(URL_PATTERN)
		if re.match(url_pattern, url) is None:
			wx.MessageBox(
				_("Invalid URL, bad format."), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		try:
			import urllib.request

			r = urllib.request.urlopen(url)
		except urllib.error.HTTPError as err:
			wx.MessageBox(
				# Translators: This message is displayed when the image URL returns an HTTP error.
				_("HTTP error %s.") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		if not r.headers.get_content_type().startswith("image/"):
			if (
				wx.MessageBox(
					# Translators: This message is displayed when the image URL seems to not point to an image.
					_(
						"The URL seems to not point to an image (content type: %s). Do you want to continue?"
					)
					% r.headers.get_content_type(),
					_("Warning"),
					wx.YES_NO | wx.ICON_WARNING | wx.NO_DEFAULT,
				)
				== wx.NO
			):
				return
		description = ''
		content_type = r.headers.get_content_type()
		if content_type:
			description = content_type
		size = r.headers.get("Content-Length")
		if size and size.isdigit():
			size = int(size)
		try:
			dimensions = get_image_dimensions(r)
		except BaseException as err:
			log.error(err)
			dimensions = None
			wx.MessageBox(
				_("Error getting image dimensions: %s") % err,
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
		self.add_images(
			[
				ImageFile(
					location=url,
					description=description,
					size=size,
					dimensions=dimensions,
				)
			]
		)
		url_dialog.Destroy()

	def on_images_remove(self, event: wx.CommandEvent):
		selection = self.images_list.GetFirstSelected()
		if selection == wx.NOT_FOUND:
			return
		self.image_files.pop(selection)
		self.refresh_images_list()
		if selection >= self.images_list.GetItemCount():
			selection -= 1
		if selection >= 0:
			self.images_list.SetItemState(
				selection, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
			)
		else:
			self.prompt.SetFocus()

	def on_copy_image_url(self, event: wx.CommandEvent):
		selected = self.images_list.GetFirstSelected()
		if selected == wx.NOT_FOUND:
			return
		url = self.image_files[selected].location
		wx.TheClipboard.Open()
		wx.TheClipboard.SetData(wx.TextDataObject(url))
		wx.TheClipboard.Close()

	def on_model_change(self, event: wx.CommandEvent):
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
		self.max_tokens_spin_ctrl.SetValue(0)

	def refresh_accounts(self):
		account_index = self.account_combo.GetSelection()
		account_id = None
		if account_index != wx.NOT_FOUND:
			account_id = config.conf.accounts[account_index].id
		self.account_combo.Clear()
		self.account_combo.AppendItems(self.get_display_accounts(True))
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

	def refresh_images_list(self):
		self.images_list.DeleteAllItems()
		if not self.image_files:
			self.images_list_label.Hide()
			self.images_list.Hide()
			self.Layout()
			return
		self.images_list_label.Show()
		self.images_list.Show()
		self.Layout()
		for i, image in enumerate(self.image_files):
			self.images_list.InsertItem(i, image.name)
			self.images_list.SetItem(i, 1, image.size)
			self.images_list.SetItem(
				i, 2, f"{image.dimensions[0]}x{image.dimensions[1]}"
			)
			self.images_list.SetItem(i, 3, image.display_location)
		self.images_list.SetItemState(
			i, wx.LIST_STATE_FOCUSED, wx.LIST_STATE_FOCUSED
		)
		self.images_list.EnsureVisible(i)

	def add_images(self, path: list[str | ImageFile]):
		log.debug(f"Adding images: {path}")
		for path in path:
			if isinstance(path, ImageFile):
				self.image_files.append(path)
			else:
				self.image_files.append(ImageFile(path))
		self.refresh_images_list()

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

	def on_prompt_context_menu(self, event: wx.ContextMenuEvent):
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

	def on_prompt_key_down(self, event: wx.KeyEvent):
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

	def on_model_key_down(self, event: wx.KeyEvent):
		if event.GetKeyCode() == wx.WXK_RETURN:
			self.on_submit(event)
		event.Skip()

	def on_key_down(self, event: wx.KeyEvent):
		if (
			event.GetModifiers() == wx.ACCEL_CTRL
			and event.GetKeyCode() == wx.WXK_RETURN
		):
			self.on_submit(event)
		event.Skip()

	def insert_previous_prompt(self, event: wx.CommandEvent = None):
		if self.conversation.messages:
			last_user_message = self.conversation.messages[-1].request.content
			self.prompt.SetValue(last_user_message)

	def get_display_accounts(self, force_refresh: bool = False) -> list[str]:
		accounts = []
		for account in config.conf.accounts:
			if force_refresh:
				if "active_organization" in account.__dict__:
					del account.__dict__["active_organization"]
			name = account.name
			organization = (
				account.active_organization.name
				if account.active_organization
				else _("Personal")
			)
			provider_name = account.provider.name
			accounts.append(f"{name} ({organization}) - {provider_name}")
		return accounts

	def extract_text_from_message(
		self, content: list[TextMessageContent | ImageUrlMessageContent] | str
	) -> str:
		if isinstance(content, str):
			return content
		text = ""
		for item in content:
			if item.type == "text":
				text += item.text
		return text

	def display_new_block(self, new_block: MessageBlock):
		if not self.messages.IsEmpty():
			self.messages.AppendText(os.linesep)
		content = self.extract_text_from_message(new_block.request.content)
		self.messages.AppendText(f"{new_block.request.role.value}: {content}")
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
		self.image_files.clear()
		self.refresh_images_list()
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

	def get_content_for_completion(
		self, images_files: list[ImageFile] = None, prompt: str = None
	) -> list[dict[str, str]]:
		if not images_files:
			images_files = self.image_files
		if not images_files:
			return prompt
		content = []
		if prompt:
			content.append({"type": "text", "text": prompt})
		for image_file in images_files:
			content.append(
				{
					"type": "image_url",
					"image_url": {
						"url": image_file.get_url(
							resize=config.conf.images.resize,
							max_width=config.conf.images.max_width,
							max_height=config.conf.images.max_height,
							quality=config.conf.images.quality,
						)
					},
				}
			)
		return content

	def transcribe_audio_file(self, audio_file: str = None):
		self.recording_thread = RecordingThread(
			provider_engine=self.current_engine,
			recordings_settings=config.conf.recordings,
			conversation_tab=self,
			audio_file_path=audio_file,
		)
		self.recording_thread.daemon = True
		self.recording_thread.start()

	def on_transcribe_audio_file(self):
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
		play_sound("recording_started")
		self.SetStatusText(_("Recording..."))

	def on_recording_stopped(self):
		play_sound("recording_stopped")
		self.SetStatusText(_("Recording stopped"))

	def on_transcription_started(self):
		play_sound("progress", loop=True)
		self.SetStatusText(_("Transcribing..."))

	def on_transcription_received(self, transcription):
		stop_sound()
		self.SetStatusText(_("Ready"))
		self.prompt.AppendText(transcription.text)
		self.prompt.SetInsertionPointEnd()
		self.prompt.SetFocus()

	def on_transcription_error(self, error):
		stop_sound()
		self.SetStatusText(_("Ready"))
		wx.MessageBox(
			_("An error occurred during transcription: ") + str(error),
			_("Error"),
			wx.OK | wx.ICON_ERROR,
		)

	def toggle_recording(self, event: wx.CommandEvent):
		if self.recording_thread and self.recording_thread.is_alive():
			self.stop_recording()
		else:
			self.start_recording()

	def start_recording(self):
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
		self.recording_thread.stop()
		self.toggle_record_btn.SetLabel(_("Record") + " (Ctrl+R)")
		self.submit_btn.Enable()

	def on_submit(self, event: wx.CommandEvent):
		if not self.prompt.GetValue() and not self.image_files:
			self.prompt.SetFocus()
			return
		model = self.current_model
		if not model:
			wx.MessageBox(
				_("Please select a model"), _("Error"), wx.OK | wx.ICON_ERROR
			)
			return
		if self.image_files and not model.vision:
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
			return
		self.submit_btn.Disable()
		self.stop_completion_btn.Show()
		system_message = None
		if self.system_prompt_txt.GetValue():
			system_message = Message(
				role=MessageRoleEnum.SYSTEM,
				content=self.system_prompt_txt.GetValue(),
			)
		new_block = MessageBlock(
			request=Message(
				role=MessageRoleEnum.USER,
				content=self.get_content_for_completion(
					images_files=self.image_files, prompt=self.prompt.GetValue()
				),
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

	def on_stop_completion(self, event: wx.CommandEvent):
		self._stop_completion = True

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
			wx.CallAfter(self._pre_handle_completion_with_stream, new_block)
			for chunk in self.current_engine.completion_response_with_stream(
				response
			):
				if self._stop_completion or globalvars.app_should_exit:
					log.debug("Stopping completion")
					break
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
		self.image_files.clear()
		self.refresh_images_list()

	def _handle_completion_with_stream(self, chunk: str):
		self.stream_buffer += chunk
		if '\n' in chunk or len(self.stream_buffer) > 120:
			self._flush_stream_buffer()
			if not self._messages_already_focused:
				self.messages.SetFocus()
				self._messages_already_focused = True
		new_time = time.time()
		if new_time - self.last_time > 4:
			play_sound("chat_response_pending")
			self.last_time = new_time

	def _flush_stream_buffer(self):
		pos = self.messages.GetInsertionPoint()
		self.messages.AppendText(self.stream_buffer)
		self.stream_buffer = ""
		self.messages.SetInsertionPoint(pos)

	def _post_completion_with_stream(self, new_block: MessageBlock):
		self._flush_stream_buffer()
		self._end_task()
		self._messages_already_focused = False

	def _post_completion_without_stream(self, new_block: MessageBlock):
		self._end_task()
		self.conversation.messages.append(new_block)
		self.display_new_block(new_block)
		self.prompt.Clear()
		self.image_files.clear()
		self.refresh_images_list()

	def _end_task(self, success: bool = True):
		if not self._messages_already_focused:
			self.messages.SetFocus()
			self._messages_already_focused = True
		task = self.task
		task.join()
		thread_id = task.ident
		log.debug(f"Task {thread_id} ended")
		self.task = None
		stop_sound()
		if success:
			play_sound("chat_response_received")
		self.stop_completion_btn.Hide()
		self.submit_btn.Enable()
		self._stop_completion = False
