import wx
from config import conf
from localization import _
from logging import getLogger

log = getLogger(__name__)

LOG_LEVELS = ["INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG"]
LANGUAGES = {
	"auto": _("Auto"),
	"en": _("English"),
	"fi": _("Finnish"),
	"fr": _("French"),
	"ru": _("Russian"),
	"uk": _("Ukrainian"),
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
		log_level = conf["general"]["log_level"]
		value = log_level if log_level in LOG_LEVELS else LOG_LEVELS[0]
		self.log_level = wx.ComboBox(
			panel, choices=LOG_LEVELS, value=value, style=wx.CB_READONLY
		)
		sizer.Add(self.log_level, 0, wx.ALL, 5)

		cur_lang = conf["general"]["language"]
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
		self.advanced_mode = wx.CheckBox(
			panel, label=_("Advanced mode"), style=wx.ALIGN_LEFT
		)
		self.advanced_mode.SetValue(conf["general"]["advanced_mode"])
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
		conf["general"]["log_level"] = self.log_level.GetValue()
		language = self.language.GetValue()
		for key, value in LANGUAGES.items():
			if language == value:
				conf["general"]["language"] = key
				break
		conf["general"]["advanced_mode"] = self.advanced_mode.GetValue()
		log.debug("New configuration: %s", conf)
		conf.write()
		self.EndModal(wx.ID_OK)

	def onCancel(self, event):
		self.EndModal(wx.ID_CANCEL)


if __name__ == "__main__":
	app = wx.App()
	ConfigDialog(None, -1, _("Settings"))
	app.MainLoop()
