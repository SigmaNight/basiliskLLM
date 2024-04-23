import wx
from config import conf, LogLevelEnum
from localization import (
	_,
	get_supported_locales,
	get_current_app_locale,
	setup_translation,
)
from logger import get_app_logger, set_log_level

log = get_app_logger(__name__)

LOG_LEVELS = {
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.NOTSET: _("Off"),
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.DEBUG: _("Debug"),
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.INFO: _("Info"),
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.WARNING: _("Warning"),
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.ERROR: _("Error"),
	# Translators: A label for the log level in the settings dialog
	LogLevelEnum.CRITICAL: _("Critical"),
}


class ConfigDialog(wx.Dialog):
	def __init__(self, parent, title, size=(400, 400)):
		wx.Dialog.__init__(self, parent, title=title, size=size)
		self.parent = parent
		self.initUI()
		self.Centre()
		self.Show()

	def initUI(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(panel, label=_("Log level"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		log_level_value = conf.general.log_level.value
		self.log_level = wx.ComboBox(
			panel,
			choices=list(LOG_LEVELS.values()),
			value=log_level_value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.log_level, 0, wx.ALL, 5)
		cur_lang = conf.general.language
		self.init_languages(get_current_app_locale())
		value = self.languages.get(cur_lang, self.languages["auto"])
		label = wx.StaticText(panel, label=_("Language"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		self.language = wx.ComboBox(
			panel,
			choices=list(self.languages.values()),
			value=value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.language, 0, wx.ALL, 5)
		self.advanced_mode = wx.CheckBox(
			panel, label=_("Advanced mode"), style=wx.ALIGN_LEFT
		)
		self.advanced_mode.SetValue(conf.general.advanced_mode)
		sizer.Add(self.advanced_mode, 0, wx.ALL, 5)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK, _("Save"))
		btn.Bind(wx.EVT_BUTTON, self.onOK)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
		btn.Bind(wx.EVT_BUTTON, self.onCancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

		panel.Layout()
		self.Layout()

	def onOK(self, event):
		log.debug("Saving configuration")
		conf.general.log_level = list(LOG_LEVELS.keys())[
			self.log_level.GetSelection()
		]
		conf.general.language = list(self.languages.keys())[
			self.language.GetSelection()
		]
		conf.general.advanced_mode = self.advanced_mode.GetValue()
		log.debug("New configuration: %s", conf)
		conf.save()
		set_log_level(conf.general.log_level.name)
		setup_translation(get_current_app_locale())
		self.EndModal(wx.ID_OK)

	def onCancel(self, event):
		self.EndModal(wx.ID_CANCEL)

	def init_languages(self, current_lang: str) -> dict[str, str]:
		"""Get all supported languages and set the current language as default"""
		self.languages = {
			# Translators: A label for the language in the settings dialog
			"auto": _("Auto")
		}
		supported_locales = get_supported_locales()
		self.languages.update(
			{
				str(locale): locale.get_display_name(current_lang)
				for locale in supported_locales
			}
		)


if __name__ == "__main__":
	app = wx.App()
	ConfigDialog(None, -1, _("Settings"))
	app.MainLoop()
