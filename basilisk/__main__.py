import argparse
import os
import psutil
import sys
from basilisk.consts import APP_NAME, TMP_DIR, FILE_LOCK_PATH
from basilisk.filewatcher import send_focus_signal
from basilisk import globalvars
from basilisk.singletoninstance import SingletonInstance


def parse_args():
	parser = argparse.ArgumentParser(
		description="Runs the application with customized configurations."
	)
	parser.add_argument(
		"--language", "-l", help="Set the application language", default=None
	)
	parser.add_argument(
		"--log_level",
		"-L",
		help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
		default=None,
	)
	parser.add_argument(
		"--no-env-account",
		"-N",
		help="Disable loading accounts from environment variables",
		action="store_true",
	)
	parser.add_argument(
		"-n",
		help="Show message window if application is already running",
		action="store_true",
	)
	return parser.parse_args()


if __name__ == '__main__':
	os.makedirs(TMP_DIR, exist_ok=True)
	globalvars.args = parse_args()
	singleton_instance = SingletonInstance(FILE_LOCK_PATH)
	if not singleton_instance.acquire():
		existing_pid = singleton_instance.get_existing_pid()
		if existing_pid:
			try:
				psutil.Process(existing_pid)
				if "-n" in sys.argv:
					import ctypes

					ctypes.windll.user32.MessageBoxW(
						0,
						f"{APP_NAME} is already running. Use the tray icon to interact with the application or AltGr+Shift+B to focus the window.",
						APP_NAME,
						0x40 | 0x0,
					)
				else:
					send_focus_signal()
				sys.exit(0)
			except psutil.NoSuchProcess:
				singleton_instance.acquire()
	from basilisk.mainapp import MainApp

	app = MainApp()
	app.MainLoop()
