"""Presenter for the preferences dialog.

Extracts business logic from PreferencesDialog into a wx-free presenter.
"""

from __future__ import annotations

import logging

import basilisk.audio as audio
import basilisk.config as config
from basilisk.audio.devices import AudioDeviceManager
from basilisk.config import (
	AutomaticUpdateModeEnum,
	LogLevelEnum,
	ReleaseChannelEnum,
)
from basilisk.localization import get_app_locale, get_supported_locales
from basilisk.logger import set_log_level

log = logging.getLogger(__name__)

LOG_LEVELS = LogLevelEnum.get_labels()
RELEASE_CHANNELS = ReleaseChannelEnum.get_labels()
AUTO_UPDATE_MODES = AutomaticUpdateModeEnum.get_labels()
# Translators: Label for the system default audio device in preferences
SYSTEM_DEFAULT_DEVICE_LABEL = _("System default")


class PreferencesPresenter:
	"""Presenter for the preferences dialog.

	Handles language list construction and config persistence,
	keeping the view free of direct config dependencies.

	Attributes:
		view: The PreferencesDialog instance.
		languages: Ordered dict mapping locale key to display label.
	"""

	def __init__(self, view) -> None:
		"""Initialize the presenter.

		Args:
			view: The dialog view with widget accessors.
		"""
		self.view = view
		conf = config.conf()
		app_locale = get_app_locale(conf.general.language)
		self.languages: dict[str, str] = self._build_languages(app_locale)
		self._build_device_choices(conf)

	def _build_device_choices(self, conf) -> None:
		"""Build input/output device choice lists and initial selections.

		Args:
			conf: The current BasiliskConfig instance.
		"""
		input_devices = AudioDeviceManager.get_input_devices()
		output_devices = AudioDeviceManager.get_output_devices()
		self._input_device_indices = [None] + [d.index for d in input_devices]
		self._output_device_indices = [None] + [d.index for d in output_devices]
		self.input_device_choices = [SYSTEM_DEFAULT_DEVICE_LABEL] + [
			d.name for d in input_devices
		]
		self.output_device_choices = [SYSTEM_DEFAULT_DEVICE_LABEL] + [
			d.name for d in output_devices
		]
		cfg_in = conf.recordings.input_device
		cfg_out = conf.recordings.output_device
		try:
			self.initial_input_device_index = (
				self._input_device_indices.index(cfg_in)
				if cfg_in in self._input_device_indices
				else 0
			)
		except ValueError:
			self.initial_input_device_index = 0
		try:
			self.initial_output_device_index = (
				self._output_device_indices.index(cfg_out)
				if cfg_out in self._output_device_indices
				else 0
			)
		except ValueError:
			self.initial_output_device_index = 0

	def _build_languages(self, cur_locale) -> dict[str, str]:
		"""Build the language display dict.

		Args:
			cur_locale: The current Babel Locale for display name formatting.

		Returns:
			An ordered dict with "auto" first, then supported locales.
		"""
		languages: dict[str, str] = {
			# Translators: A label for the language in the settings dialog
			"auto": _("System default (auto)")
		}
		supported_locales = get_supported_locales()
		languages.update(
			{
				str(
					locale
				): f"{locale.get_display_name(cur_locale).capitalize()} ({locale})"
				for locale in supported_locales
			}
		)
		return languages

	def on_ok(self) -> None:
		"""Read widget values, save config, and close the dialog."""
		import wx

		log.debug("Saving configuration")
		conf = config.conf()
		conf.general.log_level = list(LOG_LEVELS.keys())[
			self.view.log_level.GetSelection()
		]
		conf.general.language = list(self.languages.keys())[
			self.view.language.GetSelection()
		]
		conf.general.quit_on_close = self.view.quit_on_close.GetValue()
		conf.general.release_channel = list(RELEASE_CHANNELS.keys())[
			self.view.release_channel.GetSelection()
		]
		conf.general.automatic_update_mode = list(AUTO_UPDATE_MODES.keys())[
			self.view.auto_update_mode.GetSelection()
		]
		conf.general.advanced_mode = self.view.advanced_mode.GetValue()
		conf.conversation.role_label_user = self.view.role_label_user.GetValue()
		conf.conversation.role_label_assistant = (
			self.view.role_label_assistant.GetValue()
		)
		conf.conversation.nav_msg_select = self.view.nav_msg_select.GetValue()
		conf.conversation.shift_enter_mode = (
			self.view.shift_enter_mode.GetValue()
		)
		conf.conversation.use_accessible_output = (
			self.view.use_accessible_output.GetValue()
		)
		conf.conversation.focus_history_after_send = (
			self.view.focus_history_checkbox.GetValue()
		)
		conf.conversation.auto_save_to_db = self.view.auto_save_to_db.GetValue()
		conf.conversation.auto_save_draft = self.view.auto_save_draft.GetValue()
		conf.conversation.reopen_last_conversation = (
			self.view.reopen_last_conversation.GetValue()
		)
		conf.images.resize = self.view.image_resize.GetValue()
		conf.images.max_height = int(self.view.image_max_height.GetValue())
		conf.images.max_width = int(self.view.image_max_width.GetValue())
		conf.images.quality = int(self.view.image_quality.GetValue())
		conf.network.use_system_cert_store = (
			self.view.use_system_cert_store.GetValue()
		)
		conf.server.enable = self.view.server_enable.GetValue()
		conf.server.port = int(self.view.server_port.GetValue())

		in_sel = self.view.input_device.GetSelection()
		out_sel = self.view.output_device.GetSelection()
		conf.recordings.input_device = self._input_device_indices[in_sel]
		new_output_device = self._output_device_indices[out_sel]
		if conf.recordings.output_device != new_output_device:
			conf.recordings.output_device = new_output_device
			try:
				audio.get_manager().set_output_device(new_output_device)
			except RuntimeError:
				pass

		conf.save()
		set_log_level(conf.general.log_level.name)

		self.view.EndModal(wx.ID_OK)
