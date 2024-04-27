import logging


def setup_logging(level: str):
	"""Setup logging configuration"""
	console_handler = logging.StreamHandler()
	file_handler = logging.FileHandler("basiliskLLM.log", mode='w')
	logging.basicConfig(
		level=level,
		format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
		handlers=[console_handler, file_handler],
		force=True,
	)


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
