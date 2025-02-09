"""Module for the about dialog of the basiliskLLM application."""

import sys

import wx.adv

from basilisk.consts import (
	APP_AUTHORS,
	APP_NAME,
	APP_SOURCE_URL,
	APP_TRANSLATORS,
)

if getattr(sys, "frozen", False):
	from BUILD_CONSTANTS import *  # noqa # type: ignore

	app_version = BUILD_RELEASE_STRING  # noqa # type: ignore
else:
	from setuptools_scm import get_version

	app_version = get_version(root="../..", relative_to=__file__)


def display_about_dialog(parent):
	"""Display the about dialog of the application."""
	info = wx.adv.AboutDialogInfo()
	info.SetName(APP_NAME)
	info.SetVersion(app_version)
	info.SetDescription(_("Where LLMs Unite"))
	info.SetWebSite(APP_SOURCE_URL)
	info.SetLicense(_("GPLV2"))
	info.SetDevelopers(APP_AUTHORS)
	info.SetTranslators(APP_TRANSLATORS)
	wx.adv.AboutBox(info)
