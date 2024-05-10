import sys
import gettext
import locale
import logging
import wx
from typing import Optional
from pathlib import Path
from babel import Locale
from basilisk.consts import APP_NAME, DEFAULT_LANG

log = logging.getLogger(__name__)


if getattr(sys, "frozen", False):
	logging.debug("Running in a cxfreeze bundle")
	LOCALE_DIR = Path(sys.executable).parent / Path("res", "locale")
else:
	log.debug("Running in a normal Python environment")
	LOCALE_DIR = Path(__file__).parent / Path("res", "locale")


def get_supported_locales(domain: str = APP_NAME) -> list[Locale]:
	"""get all supported translation language from the locale directory and check if a mo file exwist for the language"""
	supported_locales = [Locale.parse(DEFAULT_LANG)]
	mo_sub_path = Path("LC_MESSAGES", f"{domain}.mo")
	log.debug("Locale directory: %s", LOCALE_DIR)
	for lang in LOCALE_DIR.iterdir():
		mo_file = lang / mo_sub_path
		detected_locale = Locale.parse(lang.name)
		if mo_file.exists():
			supported_locales.append(detected_locale)
		else:
			log.warning(
				f"Translation compiled file not found for: {detected_locale.english_name}"
			)
	return supported_locales


def get_app_locale(language: Optional[str]) -> Locale:
	"""Get the current application locale"""
	if language is None or language == "auto":
		language = locale.getdefaultlocale()[0]
	return Locale.parse(language)


def get_wx_locale(current_locale: Locale) -> wx.Locale:
	"""Get the wxPython locale name from the babel locale"""
	find_language = wx.Locale.FindLanguageInfo(current_locale.language)
	if find_language:
		log.debug(
			f"wxPython locale found for: {current_locale.english_name}({find_language.Language})"
		)
		return wx.Locale(find_language.Language)
	log.warning(f"wxPython locale not found for: {current_locale.english_name}")
	return wx.Locale(wx.LANGUAGE_DEFAULT)


def setup_translation(locale: Locale) -> None:
	"""Setup the translation for the application"""
	translation = gettext.translation(
		domain=APP_NAME,
		localedir=LOCALE_DIR,
		languages=[str(locale)],
		fallback=True,
	)
	translation.install()
	log.debug(f"gettext Translation setup for: {locale.english_name}")


def init_translation(language: Optional[str]) -> wx.Locale:
	"""Initialize the translation for the application"""
	app_locale = get_app_locale(language)
	# Initialize the translation
	setup_translation(app_locale)
	return get_wx_locale(app_locale)
