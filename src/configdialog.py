import wx
from config import conf, LogLevelEnum
from localization import _
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

LANGUAGES = {
	# Translators: A label for the language in the settings dialog
	"auto": _("Auto"),
	# Translators: A label for the language in the settings dialog
	"en": _("English"),
	# Translators: A label for the language in the settings dialog
	"fi": _("Finnish"),
	# Translators: A label for the language in the settings dialog
	"fr": _("French"),
	# Translators: A label for the language in the settings dialog
	"ru": _("Russian"),
	# Translators: A label for the language in the settings dialog
	"uk": _("Ukrainian"),
	# Translators: A label for the language in the settings dialog
	"tr": _("Turkish"),
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
		value = LANGUAGES.get(cur_lang, LANGUAGES["auto"])
		label = wx.StaticText(panel, label=_("Language"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		self.language = wx.ComboBox(
			panel,
			choices=list(LANGUAGES.values()),
			value=value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.language, 0, wx.ALL, 5)

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
		conf.general.language = list(LANGUAGES.keys())[
			self.language.GetSelection()
		]
		log.debug("New configuration: %s", conf)
		conf.save()
		set_log_level(conf.general.log_level.name)
		self.EndModal(wx.ID_OK)

	def onCancel(self, event):
		self.EndModal(wx.ID_CANCEL)


if __name__ == "__main__":
	app = wx.App()
	ConfigDialog(None, -1, _("Settings"))
	app.MainLoop()
