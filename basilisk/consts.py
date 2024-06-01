from enum import Enum

APP_NAME = "BasiliskLLM"
APP_SOURCE_URL = "https://github.com/aaclause/basiliskLLM"
DEFAULT_LANG = "en"


class HotkeyAction(Enum):
	TOGGLE_VISIBILITY = 1
	CAPTURE_FULL = 20
	CAPTURE_WINDOW = 21


HOTKEY_CAPTURE_WINDOW = 21
