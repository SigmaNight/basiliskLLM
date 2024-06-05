from enum import Enum

APP_NAME = "BasiliskLLM"
APP_REPO = "aaclause/basiliskLLM"
APP_SOURCE_URL = f"https://github.com/{APP_REPO}"
DEFAULT_LANG = "en"
WORKFLOW_NAME = "ci"
UNINSTALL_FILE_NAME = "unins000.exe"

class HotkeyAction(Enum):
	TOGGLE_VISIBILITY = 1
	CAPTURE_FULL = 20
	CAPTURE_WINDOW = 21
