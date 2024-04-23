import locale
import gettext

from pathlib import Path
from babel import Locale
from consts import APP_NAME, DEFAULT_LANG
from config import conf
from logger import get_app_logger

logger = get_app_logger(__name__)

LOCALE_DIR = Path(__file__).parent / Path("res", "locale")


def get_supported_locales(domain: str = APP_NAME) -> list[Locale]:
	"""get all supported translation language from the locale directory and check if a mo file exwist for the language"""
	supported_locales = [Locale.parse(DEFAULT_LANG)]
	mo_sub_path = Path("LC_MESSAGES", f"{domain}.mo")
	for lang in LOCALE_DIR.iterdir():
		mo_file = lang / mo_sub_path
		detected_locale = Locale.parse(lang.name)
		if mo_file.exists():
			supported_locales.append(detected_locale)
		else:
			logger.warning(
				f"Translation compiled file not found for: {detected_locale.english_name}"
			)
	return supported_locales


def get_current_app_locale() -> Locale:
	"""Get the current application locale"""
	app_locale = locale.getdefaultlocale()[0]
	if conf.general.language != "auto":
		app_locale = conf.general.language
	return Locale.parse(app_locale)


def setup_translation(locale: Locale) -> gettext.NullTranslations:
	"""Setup the translation for the application"""
	global translation
	global _
	translation = gettext.translation(
		domain=APP_NAME,
		localedir=LOCALE_DIR,
		languages=[str(locale)],
		fallback=True,
	)
	_ = translation.gettext
	logger.info(f"Translation setup for: {locale.english_name}")


setup_translation(get_current_app_locale())
