"""Module to handle the translation of the application."""

import gettext
import locale
import logging
from pathlib import Path
from typing import Optional

import wx
from babel import Locale

from .consts import APP_NAME, DEFAULT_LANG
from .global_vars import resource_path

log = logging.getLogger(__name__)


LOCALE_DIR = resource_path / Path("locale")


def get_supported_locales(domain: str = APP_NAME) -> list[Locale]:
	"""Get the supported locales for the application from the compiled translation files.

	Args:
		domain: The domain of the translation to check for the compiled files (default: APP_NAME)

	Returns:
		A list of supported locales for the application
	"""
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
	"""Get the current application locale based on the system locale or the provided language.

	Args:
		language: The language to use for the application (default: None)

	Returns:
		The locale to use for the application based on the system locale or the provided language string.
	"""
	if language is None or language == "auto":
		language = locale.getdefaultlocale()[0]
	return Locale.parse(language)


def get_wx_locale(current_locale: Locale) -> wx.Locale:
	"""Get the wxPython locale name from the babel locale.

	Args:
		current_locale: The current locale to get the wxPython locale for.

	Returns:
		The wxPython locale object for the current locale.
	"""
	find_language = wx.Locale.FindLanguageInfo(current_locale.language)
	if find_language:
		log.debug(
			f"wxPython locale found for: {current_locale.english_name}({find_language.Language})"
		)
		return wx.Locale(find_language.Language)
	log.warning(f"wxPython locale not found for: {current_locale.english_name}")
	return wx.Locale(wx.LANGUAGE_DEFAULT)


def setup_translation(locale: Locale) -> None:
	"""Setup the translation for the application based on the provided locale.

	Args:
		locale: The locale to use for the translation.
	"""
	translation = gettext.translation(
		domain=APP_NAME,
		localedir=LOCALE_DIR,
		languages=[str(locale)],
		fallback=True,
	)
	translation.install()
	log.debug(f"gettext Translation setup for: {locale.english_name}")


def init_translation(language: Optional[str]) -> wx.Locale:
	"""Initialize the translation for the application based on the provided language.

	Args:
		language: The language to use for the application (default: None)

	Returns:
		The wxPython locale object for the current locale.
	"""
	app_locale = get_app_locale(language)
	# Initialize the translation
	setup_translation(app_locale)
	return get_wx_locale(app_locale)
