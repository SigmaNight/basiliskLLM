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

from basilisk import global_vars
from basilisk.consts import APP_NAME, TMP_DIR
from basilisk.send_signal import send_focus_signal, send_open_bskc_file_signal
from basilisk.singleton_instance import SingletonInstance


def parse_args():
	"""Parse command-line arguments for the Basilisk application.

	Configures and processes command-line options to customize application startup and behavior.

	Arguments:
		--language, -l (str | None): Sets the application language. Defaults to None.
		--log_level, -L (str | None): Sets the logging level. Valid levels are DEBUG, INFO, WARNING, ERROR, CRITICAL. Defaults to None.
		--no-env-account, -n (bool): Disables loading accounts from environment variables. Defaults to False.
		--minimize, -m (bool): Starts the application in a minimized window state. Defaults to False.

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
		"-n",
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
		'bskc_file',
		nargs='?',
		help='Basilisk conversation file to open',
		default=None,
	)
	return parser.parse_args()


def action_on_already_running() -> None:
	"""Handle actions when the Basilisk application is already running.

	This function performs the appropriate action based on command-line arguments.
	If a BSKC file is specified, it sends a signal to open that file in the existing instance.
	Otherwise, it sends a focus signal to bring the existing instance to the foreground.
	"""
	if global_vars.args.bskc_file:
		send_open_bskc_file_signal(global_vars.args.bskc_file)
	else:
		send_focus_signal()


if __name__ == '__main__':
	# Enable multiprocessing support for frozen executables
	multiprocessing.freeze_support()

	os.makedirs(TMP_DIR, exist_ok=True)
	global_vars.args = parse_args()
	singleton_instance = SingletonInstance()
	if not singleton_instance.acquire():
		# Another instance is already running
		# The singleton mechanism handles stale lock detection and cleanup automatically
		# Send signal to existing instance
		action_on_already_running()
		sys.exit(0)

	from basilisk.main_app import MainApp

	app = MainApp()
	app.MainLoop()
