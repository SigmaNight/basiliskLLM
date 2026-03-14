"""Preferences dialog for the BasiliskLLM application."""

import logging

import wx

import basilisk.config as config
from basilisk.presenters.preferences_presenter import (
	AUTO_UPDATE_MODES,
	LOG_LEVELS,
	RELEASE_CHANNELS,
	PreferencesPresenter,
)

log = logging.getLogger(__name__)


class PreferencesDialog(wx.Dialog):
	"""A dialog to configure the application preferences."""

	def __init__(
		self, parent: wx.Window, title: str, size: tuple[int, int] = (400, 400)
	):
		"""Create the dialog.

		Args:
			parent: The parent window.
			title: The dialog title.
			size: The dialog size.
		"""
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.parent = parent
		self.presenter = PreferencesPresenter(self)
		self.init_ui()
		self.Centre()
		self.Show()

	def init_ui(self):
		"""Create the user interface."""
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel,
			# Translators: A label for the log level selection in the preferences dialog
			label=_("Log level"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		conf = config.conf()
		log_level_value = LOG_LEVELS[conf.general.log_level]
		self.log_level = wx.ComboBox(
			panel,
			choices=list(LOG_LEVELS.values()),
			value=log_level_value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.log_level, 0, wx.ALL, 5)
		value = self.presenter.languages.get(
			conf.general.language, self.presenter.languages["auto"]
		)
		label = wx.StaticText(
			panel,
			# Translators: A label for the language selection in the preferences dialog
			label=_("Language (Requires restart)"),
			style=wx.ALIGN_LEFT,
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.language = wx.ComboBox(
			panel,
			choices=list(self.presenter.languages.values()),
			value=value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.language, 0, wx.ALL, 5)

		self.quit_on_close = wx.CheckBox(
			panel, label=_("Quit on &close, don't minimize")
		)
		self.quit_on_close.SetValue(conf.general.quit_on_close)
		sizer.Add(self.quit_on_close, 0, wx.ALL, 5)

		update_group = wx.StaticBox(panel, label=_("Update"))
		update_group_sizer = wx.StaticBoxSizer(update_group, wx.VERTICAL)

		label = wx.StaticText(
			panel, label=_("Release channel"), style=wx.ALIGN_LEFT
		)
		update_group_sizer.Add(label, 0, wx.ALL, 5)

		release_channel_value = RELEASE_CHANNELS[conf.general.release_channel]
		self.release_channel = wx.ComboBox(
			panel,
			choices=list(RELEASE_CHANNELS.values()),
			value=release_channel_value,
			style=wx.CB_READONLY,
		)
		update_group_sizer.Add(self.release_channel, 0, wx.ALL, 5)

		label = wx.StaticText(
			panel, label=_("Automatic update mode"), style=wx.ALIGN_LEFT
		)
		update_group_sizer.Add(label, 0, wx.ALL, 5)
		auto_update_mode_value = AUTO_UPDATE_MODES[
			conf.general.automatic_update_mode
		]
		self.auto_update_mode = wx.ComboBox(
			panel,
			choices=list(AUTO_UPDATE_MODES.values()),
			value=auto_update_mode_value,
			style=wx.CB_READONLY,
		)
		update_group_sizer.Add(self.auto_update_mode, 0, wx.ALL, 5)

		sizer.Add(update_group_sizer, 0, wx.ALL, 5)

		self.advanced_mode = wx.CheckBox(
			panel,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Advanced mode"),
			style=wx.ALIGN_LEFT,
		)
		self.advanced_mode.SetValue(conf.general.advanced_mode)
		sizer.Add(self.advanced_mode, 0, wx.ALL, 5)

		conversation_group = wx.StaticBox(panel, label=_("Conversation"))
		conversation_group_sizer = wx.StaticBoxSizer(
			conversation_group, wx.VERTICAL
		)

		label = wx.StaticText(
			conversation_group,
			# Translators: A label in the preferences dialog
			label=_("Custom role label for user:"),
		)
		conversation_group_sizer.Add(label, 0, wx.ALL, 5)
		self.role_label_user = wx.TextCtrl(
			conversation_group, value=conf.conversation.role_label_user or ""
		)
		conversation_group_sizer.Add(self.role_label_user, 0, wx.ALL, 5)

		label = wx.StaticText(
			conversation_group,
			# Translators: A label in the preferences dialog
			label=_("Custom role label for assistant:"),
		)
		conversation_group_sizer.Add(label, 0, wx.ALL, 5)
		self.role_label_assistant = wx.TextCtrl(
			conversation_group,
			value=conf.conversation.role_label_assistant or "",
		)
		conversation_group_sizer.Add(self.role_label_assistant, 0, wx.ALL, 5)

		self.nav_msg_select = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Message Selection on Previous/Next Navigation"),
		)
		self.nav_msg_select.SetValue(conf.conversation.nav_msg_select)
		conversation_group_sizer.Add(self.nav_msg_select, 0, wx.ALL, 5)

		self.shift_enter_mode = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Send message with Enter, insert newline with Shift+Enter"),
		)
		self.shift_enter_mode.SetValue(conf.conversation.shift_enter_mode)
		conversation_group_sizer.Add(self.shift_enter_mode, 0, wx.ALL, 5)

		self.use_accessible_output = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_(
				"Enable &Accessible Output to provide spoken and braille feedback for actions and messages"
			),
		)
		self.use_accessible_output.SetValue(
			conf.conversation.use_accessible_output
		)
		conversation_group_sizer.Add(self.use_accessible_output, 0, wx.ALL, 5)

		self.focus_history_checkbox = wx.CheckBox(
			conversation_group, label=_("Focus message history after sending")
		)
		self.focus_history_checkbox.SetValue(
			conf.conversation.focus_history_after_send
		)
		conversation_group_sizer.Add(self.focus_history_checkbox, 0, wx.ALL, 5)

		self.auto_save_to_db = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Automatically save conversations to &database"),
		)
		self.auto_save_to_db.SetValue(conf.conversation.auto_save_to_db)
		self.auto_save_to_db.Bind(
			wx.EVT_CHECKBOX, self.on_auto_save_to_db_changed
		)
		conversation_group_sizer.Add(self.auto_save_to_db, 0, wx.ALL, 5)

		self.auto_save_draft = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Auto-save &draft prompt text"),
		)
		self.auto_save_draft.SetValue(conf.conversation.auto_save_draft)
		self.auto_save_draft.Enable(conf.conversation.auto_save_to_db)
		conversation_group_sizer.Add(self.auto_save_draft, 0, wx.ALL, 5)

		self.reopen_last_conversation = wx.CheckBox(
			conversation_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("&Reopen last conversation on startup"),
		)
		self.reopen_last_conversation.SetValue(
			conf.conversation.reopen_last_conversation
		)
		conversation_group_sizer.Add(
			self.reopen_last_conversation, 0, wx.ALL, 5
		)

		sizer.Add(conversation_group_sizer, 0, wx.ALL, 5)

		images_group = wx.StaticBox(panel, label=_("Images"))
		images_group_sizer = wx.StaticBoxSizer(images_group, wx.VERTICAL)

		self.image_resize = wx.CheckBox(
			images_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Resize images before uploading"),
		)
		self.image_resize.SetValue(conf.images.resize)
		self.image_resize.Bind(wx.EVT_CHECKBOX, self.on_resize)
		images_group_sizer.Add(self.image_resize, 0, wx.ALL, 5)

		label = wx.StaticText(
			images_group,
			# Translators: A label in the preferences dialog
			label=_(
				"Maximum &height (0 to resize proportionally to the width):"
			),
		)
		images_group_sizer.Add(label, 0, wx.ALL, 5)
		self.image_max_height = wx.SpinCtrl(
			images_group, value=str(conf.images.max_height), min=0, max=10000
		)
		images_group_sizer.Add(self.image_max_height, 0, wx.ALL, 5)

		label = wx.StaticText(
			images_group,
			# Translators: A label in the preferences dialog
			label=_(
				"Maximum &width (0 to resize proportionally to the height):"
			),
		)
		images_group_sizer.Add(label, 0, wx.ALL, 5)
		self.image_max_width = wx.SpinCtrl(
			images_group, value=str(conf.images.max_width), min=0, max=10000
		)
		images_group_sizer.Add(self.image_max_width, 0, wx.ALL, 5)

		label = wx.StaticText(
			images_group,
			# Translators: A label in the preferences dialog
			label=_(
				"&Quality for JPEG images (0 [worst] to 95 [best], values above 95 should be avoided):"
			),
		)
		images_group_sizer.Add(label, 0, wx.ALL, 5)
		self.image_quality = wx.SpinCtrl(
			images_group, value=str(conf.images.quality), min=1, max=100
		)
		images_group_sizer.Add(self.image_quality, 0, wx.ALL, 5)

		self.on_resize(None)
		sizer.Add(images_group_sizer, 0, wx.ALL, 5)
		network_group = wx.StaticBox(
			panel,
			# Translators: a group label in the preference dialog
			label=_("Network"),
		)
		network_sizer = wx.StaticBoxSizer(network_group, wx.VERTICAL)
		self.use_system_cert_store = wx.CheckBox(
			network_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Use system certificate store (Requires restart)"),
		)
		self.use_system_cert_store.SetValue(conf.network.use_system_cert_store)
		network_sizer.Add(self.use_system_cert_store, 0, wx.ALL, 5)
		sizer.Add(network_sizer, 0, wx.ALL, 5)

		server_group = wx.StaticBox(panel, label=_("Server"))
		server_group_sizer = wx.StaticBoxSizer(server_group, wx.VERTICAL)

		self.server_enable = wx.CheckBox(
			server_group,
			# Translators: A label for a checkbox in the preferences dialog
			label=_("Enable server mode (requires restart)"),
		)
		self.server_enable.SetValue(conf.server.enable)
		server_group_sizer.Add(self.server_enable, 0, wx.ALL, 5)

		label = wx.StaticText(
			server_group,
			# Translators: A label in the preferences dialog
			label=_("Port:"),
		)
		server_group_sizer.Add(label, 0, wx.ALL, 5)
		self.server_port = wx.SpinCtrl(
			server_group, value=str(conf.server.port), min=1, max=65535
		)
		server_group_sizer.Add(self.server_port, 0, wx.ALL, 5)

		sizer.Add(server_group_sizer, 0, wx.ALL, 5)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_SAVE)
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		btn.SetDefault()
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

		panel.Layout()
		self.Layout()

	def on_auto_save_to_db_changed(self, event: wx.Event | None):
		"""Enable or disable the auto-save draft option based on auto-save DB.

		Args:
			event: The checkbox event.
		"""
		self.auto_save_draft.Enable(self.auto_save_to_db.GetValue())

	def on_resize(self, event: wx.Event | None):
		"""Enable or disable the image resizing options.

		Args:
			event: The event that enable or disable the options.
		"""
		val = self.image_resize.GetValue()
		self.image_max_height.Enable(val)
		self.image_max_width.Enable(val)
		self.image_quality.Enable(val)

	def on_ok(self, event: wx.Event | None):
		"""Save the configuration and close the dialog.

		Args:
			event: The event that triggered the save.
		"""
		self.presenter.on_ok()

	def on_cancel(self, event):
		"""Close the dialog without saving the configuration."""
		self.EndModal(wx.ID_CANCEL)
