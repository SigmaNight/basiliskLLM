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


def set_log_level(level):
	"""Change global log level to new level and update all loggers
	:param level: new log level
	"""
	cur_level = logging.getLevelName(logging.getLogger().getEffectiveLevel())
	if cur_level == level:
		return
	logging.getLogger().setLevel(level)
	for handler in logging.getLogger().handlers:
		handler.setLevel(level)
	new_level = logging.getLevelName(logging.getLogger().getEffectiveLevel())
	logging.getLogger().debug(
		f"Log level changed from {cur_level} to {new_level}"
	)


def get_app_logger(name):
	return logging.getLogger(name)
