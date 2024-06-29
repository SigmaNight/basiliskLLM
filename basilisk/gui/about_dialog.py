import sys
import wx.adv
from basilisk.consts import APP_NAME, APP_SOURCE_URL

app_version = None
if getattr(sys, "frozen", False):
	from BUILD_CONSTANTS import *  # noqa # type: ignore

	app_version = BUILD_RELEASE_STRING  # noqa # type: ignore
else:
	from setuptools_scm import get_version

	app_version = get_version(root="../..", relative_to=__file__)

APP_AUTHORS = ["André-Abush Clause", "Clément Boussiron" "Nael Sayegh"]

APP_TRANSLATORS = [
	"André-Abush Clause (French)",
	"Clément Boussiron (French)",
	"Daniil Lepke (Russian)",
	"Umut Korkmaz (Turkish)",
]


def display_about_dialog(parent):
	info = wx.adv.AboutDialogInfo()
	info.SetName(APP_NAME)
	info.SetVersion(app_version)
	info.SetDescription(_("Where LLMs Unite"))
	info.SetWebSite(APP_SOURCE_URL)
	info.SetLicense(_("GPLV2"))
	info.SetDevelopers(APP_AUTHORS)
	info.SetTranslators(APP_TRANSLATORS)
	wx.adv.AboutBox(info)
