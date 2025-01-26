import time

from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE


def send_focus_signal():
	"""Send a focus signal by writing the current timestamp to a predefined file.

	This function writes the current system time as a floating-point timestamp to the
	FOCUS_FILE, which can be used to indicate a focus-related event or timing marker.

	Note:
	    - Uses the current system time from time.time()
	    - Overwrites any existing content in the file
	    - Does not include error handling for file operations

	Returns:
	    None
	"""
	with open(FOCUS_FILE, 'w') as f:
		f.write(str(time.time()))


def send_open_bskc_file_signal(bskc_file: str):
	"""Send a signal by writing the specified BSKC file path to a predefined file.

	Args:
	    bskc_file (str): The path or name of the BSKC file to be signaled.

	Note:
	    This function writes the provided file path to a predetermined signal file
	    using context management to ensure proper file handling.
	"""
	with open(OPEN_BSKC_FILE, 'w') as f:
		f.write(bskc_file)
