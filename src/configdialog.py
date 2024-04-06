import wx
from config import conf
from localization import _
from logging import getLogger
from accountdialog import AccountDialog

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
		self.initData()
		self.Centre()
		self.Show()

	def initUI(self):
		panel = wx.Panel(self)
		sizer = wx.BoxSizer(wx.VERTICAL)
		panel.SetSizer(sizer)

		label = wx.StaticText(
			panel,
			label=_("Log level"),
			style=wx.ALIGN_LEFT
		)
		sizer.Add(label, 0, wx.ALL, 5)

		self.log_level = wx.ComboBox(
			panel,
			choices=LOG_LEVELS,
			style=wx.CB_READONLY
		)
		sizer.Add(self.log_level, 0, wx.ALL, 5)

		label = wx.StaticText(
			panel,
			label=_("Language"),
			style=wx.ALIGN_LEFT
		)
		sizer.Add(label, 0, wx.ALL, 5)
		self.language = wx.ComboBox(
			panel,
			choices=list(LANGUAGES.values()),
			style=wx.CB_READONLY
		)
		sizer.Add(self.language, 0, wx.ALL, 5)

		accountsBtn = wx.Button(panel, label=_("Manage &accounts"))
		accountsBtn.Bind(wx.EVT_BUTTON, self.onManageAccounts)

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

	def initData(self):
		self.log_level.SetValue(conf["general"]["log_level"])
		cur_lang = conf["general"]["language"]
		value = LANGUAGES.get(cur_lang, LANGUAGES["auto"])
		self.language.SetValue(value)

	def onManageAccounts(self, event):
		dlg = AccountDialog(self, _("Manage accounts"))
		dlg.ShowModal()
		dlg.Destroy()

	def onOK(self, event):
		log.debug("Saving configuration")
		conf["general"]["log_level"] = self.log_level.GetValue()
		language = self.language.GetValue()
		for key, value in LANGUAGES.items():
			if language == value:
				conf["general"]["language"] = key
				break
		log.debug("New configuration: %s", conf)
		conf.write()
		self.EndModal(wx.ID_OK)

	def onCancel(self, event):
		self.EndModal(wx.ID_CANCEL)

if __name__ == "__main__":
	app = wx.App()
	ConfigDialog(None, -1, _("Settings"))
	app.MainLoop()
