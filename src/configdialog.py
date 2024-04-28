import logging
import wx
from babel import Locale
from config import conf, LogLevelEnum
from accountdialog import AccountDialog
from localization import get_supported_locales, get_app_locale
from logger import set_log_level

log = logging.getLogger(__name__)

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
		self.init_ui()
		self.Centre()
		self.Show()

	def init_ui(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(panel, label=_("Log level"), style=wx.ALIGN_LEFT)
		sizer.Add(label, 0, wx.ALL, 5)
		log_level_value = LOG_LEVELS[conf.general.log_level]
		self.log_level = wx.ComboBox(
			panel,
			choices=list(LOG_LEVELS.values()),
			value=log_level_value,
			style=wx.CB_READONLY,
		)
		sizer.Add(self.log_level, 0, wx.ALL, 5)
		app_locale = get_app_locale(conf.general.language)
		self.init_languages(app_locale)
		value = self.languages.get(
			conf.general.language, self.languages["auto"]
		)
		label = wx.StaticText(
			panel, label=_("Language (Requires restart)"), style=wx.ALIGN_LEFT
		)
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

		accountsBtn = wx.Button(panel, label=_("Manage &accounts"))
		accountsBtn.Bind(wx.EVT_BUTTON, self.on_manage_accounts)

		bSizer = wx.BoxSizer(wx.HORIZONTAL)

		btn = wx.Button(panel, wx.ID_OK, _("Save"))
		btn.Bind(wx.EVT_BUTTON, self.on_ok)
		bSizer.Add(btn, 0, wx.ALL, 5)

		btn = wx.Button(panel, wx.ID_CANCEL, _("Cancel"))
		btn.Bind(wx.EVT_BUTTON, self.on_cancel)
		bSizer.Add(btn, 0, wx.ALL, 5)

		sizer.Add(bSizer, 0, wx.ALL, 5)

		panel.Layout()
		self.Layout()

	def on_manage_accounts(self, event):
		dlg = AccountDialog(self, _("Manage accounts"))
		dlg.ShowModal()
		dlg.Destroy()

	def on_ok(self, event):
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

		self.EndModal(wx.ID_OK)

	def on_cancel(self, event):
		self.EndModal(wx.ID_CANCEL)

	def init_languages(self, cur_locale: Locale) -> dict[str, str]:
		"""Get all supported languages and set the current language as default"""
		self.languages = {
			# Translators: A label for the language in the settings dialog
			"auto": _("System default (auto)")
		}
		supported_locales = get_supported_locales()
		self.languages.update(
			{
				str(
					locale
				): f"{locale.get_display_name(cur_locale).capitalize()} ({locale})"
				for locale in supported_locales
			}
		)
