"""Module for sending signals to a running basiliskLLM application."""

import time

from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE


def send_focus_signal():
	"""Send a focus signal by writing the current timestamp to a predefined file.

	This function writes the current system time as a floating-point timestamp to the
	FOCUS_FILE, which can be used to indicate a focus-related event or timing marker.
	"""
	with open(FOCUS_FILE, 'w') as f:
		f.write(str(time.time()))


def send_open_bskc_file_signal(bskc_file: str):
	"""Send a signal by writing the specified BSKC file path to a predefined file.

	Args:
		bskc_file: The path of the BSKC file to be opened.
	"""
	with open(OPEN_BSKC_FILE, 'w') as f:
		f.write(bskc_file)
