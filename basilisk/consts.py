"""Constant values used in the application."""

import os
import tempfile
from enum import IntEnum

# application name
APP_NAME = "basiliskLLM"

# application author
APP_AUTHOR = "SigmaNight"
# application authors list
APP_AUTHORS = ["André-Abush Clause", "Clément Boussiron", "Nael Sayegh"]

# application translators list
APP_TRANSLATORS = [
	"André-Abush Clause (French)",
	"Clément Boussiron (French)",
	"Daniil Lepke (Russian)",
	"Umut Korkmaz (Turkish)",
]

# application repository
APP_REPO = f"{APP_AUTHOR}/{APP_NAME}"

# application source URL
APP_SOURCE_URL = f"https://github.com/{APP_REPO}"

# default application language
DEFAULT_LANG = "en"

# github workflow name used to get development updates
WORKFLOW_NAME = "ci"

# name of the uninstaller executable file in the installation directory
UNINSTALL_FILE_NAME = "unins000.exe"
# basilisk temp directory
TMP_DIR = os.path.join(tempfile.gettempdir(), "basilisk")

# File lock path to prevent multiple instances of the application
FILE_LOCK_PATH = os.path.join(TMP_DIR, "app.lock")

# Path to send focus event using file watcher
FOCUS_FILE = os.path.join(TMP_DIR, "focus_file")

# Path to open a conversation using file watcher
OPEN_BSKC_FILE = os.path.join(TMP_DIR, "open_bskc_file")

# current version number of the bskc file format
BSKC_VERSION = 2


class HotkeyAction(IntEnum):
	"""Enumeration of hotkey actions."""

	TOGGLE_VISIBILITY = 1
	CAPTURE_FULL = 20
	CAPTURE_WINDOW = 21
