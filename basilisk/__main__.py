"""This module is the entry point for the Basilisk application.

It provides a command-line interface for configuring and starting the application.
The module parses command-line arguments, processes them, and initializes the application with the specified configurations.
The module also checks for an existing instance of the application and displays a message if the application is already running.
If the application is already running, the module sends signals to the running instance.
"""

import argparse
import multiprocessing
import os
import sys

import psutil

from basilisk import global_vars
from basilisk.consts import APP_NAME, FILE_LOCK_PATH, TMP_DIR
from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal
from basilisk.singleton_instance import SingletonInstance


def display_already_running_msg():
	"""Display a message box indicating that the Basilisk application is already running.

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
	"""Parse command-line arguments for the Basilisk application.

	Configures and processes command-line options to customize application startup and behavior.

	Arguments:
		--language, -l (str | None): Sets the application language. Defaults to None.
		--log_level, -L (str | None): Sets the logging level. Valid levels are DEBUG, INFO, WARNING, ERROR, CRITICAL. Defaults to None.
		--no-env-account, -N (bool): Disables loading accounts from environment variables. Defaults to False.
		--minimize, -m (bool): Starts the application in a minimized window state. Defaults to False.
		--show_already_running_msg, -n (bool): Shows a message if the application is already running. Defaults to False.

	Returns:
		argparse.Namespace: Parsed command-line arguments with their values.
	"""
	parser = argparse.ArgumentParser(description=f"Run {APP_NAME}")
	parser.add_argument(
		"--language",
		"-l",
		type=str,
		default=None,
		help="Set the application language",
	)
	parser.add_argument(
		"--log_level",
		"-L",
		type=str,
		default=None,
		help="Set the log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
	)
	parser.add_argument(
		"--no-env-account",
		"-N",
		help="Do not load accounts from environment variables",
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
	# Enable multiprocessing support for frozen executables
	multiprocessing.freeze_support()

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
