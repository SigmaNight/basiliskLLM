import configobj
import configobj.validate
import os
import sys

CFG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")
CFG_SPEC = """
[general]
language = string(default='auto')
log_level = option("INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG", default='DEBUG')

[services]
[[open_ai]]
api_key = string()
use_org = boolean(default=False)
org_api_key = string()

[[mistral]]
api_key = string()
use_org = boolean(default=False)
org_api_key = string()

[[openrouter]]
api_key = string()
use_org = boolean(default=False)
org_api_key = string()
"""

conf = None


def initialize_config():
	global conf
	config_spec = configobj.ConfigObj(
		CFG_SPEC.split('\n'), list_values=False, _inspec=True
	)
	conf = configobj.ConfigObj(CFG_PATH, configspec=config_spec)

	validator = configobj.validate.Validator()
	result = conf.validate(validator, preserve_errors=True)

	if not result:
		raise ValueError("Invalid configuration file")
		sys.exit(1)
