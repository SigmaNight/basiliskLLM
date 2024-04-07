import logging
from config import conf

logging.basicConfig(
	filename="basiliskLLM.log",
	level=conf.general.log_level.name,
	filemode='w',
	format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

console_handler = logging.StreamHandler()
console_handler.setFormatter(
	logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
)

logging.getLogger().addHandler(console_handler)


def get_app_logger(name):
	return logging.getLogger(name)
