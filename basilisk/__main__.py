import argparse
import os
import sys

import psutil

from basilisk import global_vars
from basilisk.consts import APP_NAME, FILE_LOCK_PATH, TMP_DIR
from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal
from basilisk.singleton_instance import SingletonInstance


def display_already_running_msg():
	"""
	Display a message box indicating that the Basilisk application is already running.

	This function uses the Windows API via ctypes to show a message box informing the user that the application is currently active. The message provides guidance on how to interact with the running instance.

	Notes:
	    - Uses Windows-specific MessageBoxW function
	    - Displays an informational icon (0x40)
	    - Message includes application name and interaction instructions
	"""
	import ctypes

	ctypes.windll.user32.MessageBoxW(
		0,
		f"{APP_NAME} is already running. Use the tray icon to interact with the application or AltGr+Shift+B to focus the window.",
		APP_NAME,
		0x40 | 0x0,
	)


def parse_args():
	"""
	Parse command-line arguments for the Basilisk application.

	Configures and processes command-line options to customize application startup and behavior.

	Arguments:
	    --language, -l (str, optional): Sets the application language. Defaults to None.
	    --log_level, -L (str, optional): Sets the logging level.
	        Valid levels are DEBUG, INFO, WARNING, ERROR, CRITICAL. Defaults to None.
	    --no-env-account, -N (bool): Disables loading accounts from environment variables.
	        Defaults to False.
	    --minimize, -m (bool): Starts the application in a minimized window state.
	        Defaults to False.
	    -n (bool): Shows a message window if another application instance is already running.
	        Defaults to False.
	    bskc_file (str, optional): Path to a Basilisk conversation file to open.
	        Defaults to None.

	Returns:
	    argparse.Namespace: Parsed command-line arguments with their respective values.

	Example:
	    python basilisk.py --language en --log_level DEBUG --minimize conversation.bskc
	"""
	parser = argparse.ArgumentParser(
		prog=APP_NAME,
		description="Runs the application with customized configurations.",
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
		"--minimize",
		"-m",
		help="Start the application minimized",
		action="store_true",
	)
	parser.add_argument(
		"-n",
		help="Show message window if application is already running",
		action="store_true",
		dest="show_already_running_msg",
	)
	parser.add_argument(
		'bskc_file',
		nargs='?',
		help='Basilisk conversation file to open',
		default=None,
	)
	return parser.parse_args()


if __name__ == '__main__':
	os.makedirs(TMP_DIR, exist_ok=True)
	global_vars.args = parse_args()
	singleton_instance = SingletonInstance(FILE_LOCK_PATH)
	if not singleton_instance.acquire():
		existing_pid = singleton_instance.get_existing_pid()
		if existing_pid:
			try:
				psutil.Process(existing_pid)
				if global_vars.args.show_already_running_msg:
					display_already_running_msg()
				else:
					if global_vars.args.bskc_file:
						send_open_bskc_file_signal(global_vars.args.bskc_file)
					else:
						send_focus_signal()
				sys.exit(0)
			except psutil.NoSuchProcess:
				singleton_instance.acquire()
	from basilisk.main_app import MainApp

	app = MainApp()
	app.MainLoop()
