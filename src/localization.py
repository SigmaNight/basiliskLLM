import gettext
import os

LOCALE_DIR = os.path.join(os.path.dirname(__file__), "res", "locales")
DEFAULT_LANG = "en"
find_locale = gettext.find(DEFAULT_LANG, LOCALE_DIR)
current_locale = find_locale if find_locale else None
_ = gettext.gettext
if current_locale:
	trans = gettext.translation(
		DEFAULT_LANG, LOCALE_DIR, [current_locale], fallback=True
	)
else:
	trans = gettext.NullTranslations()

_ = trans.gettext


def setup_locale(language=DEFAULT_LANG):
	"""
	Setup the locale for the application
	:param language: The language code to setup
	"""
	global _
	current_locale, _ = gettext.find(language, LOCALE_DIR)
	if current_locale:
		trans = gettext.translation(
			language, LOCALE_DIR, [current_locale], fallback=True
		)
	else:
		trans = gettext.NullTranslations()
	_ = trans.gettext
