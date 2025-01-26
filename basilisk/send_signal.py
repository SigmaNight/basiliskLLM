import time

from basilisk.consts import FOCUS_FILE, OPEN_BSKC_FILE


def send_focus_signal():
	with open(FOCUS_FILE, 'w') as f:
		f.write(str(time.time()))


def send_open_bskc_file_signal(bskc_file: str):
	with open(OPEN_BSKC_FILE, 'w') as f:
		f.write(bskc_file)
