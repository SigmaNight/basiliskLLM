import os
import tempfile

APP_NAME = "basiliskLLM"
APP_AUTHOR = "SigmaNight"
APP_REPO = f"{APP_AUTHOR}/{APP_NAME}"

APP_SOURCE_URL = f"https://github.com/{APP_REPO}"
DEFAULT_LANG = "en"
WORKFLOW_NAME = "ci"
UNINSTALL_FILE_NAME = "unins000.exe"
TMP_DIR = os.path.join(tempfile.gettempdir(), "basilisk")
FILE_LOCK_PATH = os.path.join(TMP_DIR, "app.lock")
FOCUS_FILE = os.path.join(TMP_DIR, "focus_file")
OPEN_BSKC_FILE = os.path.join(TMP_DIR, "open_bskc_file")
