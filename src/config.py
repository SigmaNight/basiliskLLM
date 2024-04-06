import configobj
import configobj.validate
import os
import sys

CFG_PATH = os.path.join(os.path.dirname(__file__), "config.ini")
CFG_SPEC = """
[general]
language = string(default='auto')
log_level = option("INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG", default='DEBUG')

[accounts]
[[__many__]]
name = string
provider = string
api_key = string
organization_key = string
use_organization_key = boolean(default=False)

[custom_providers]
[[__many__]]
name = string
base_url = string
api_type = string
require_api_key = boolean(default=True)
organization_mode_available = boolean(default=False)

"""

conf = None

def save_accounts(
	accounts
):
	from account import AccountSource, AccountManager, Account
	if not isinstance(accounts, AccountManager):
		raise ValueError("Invalid accounts object")
	conf["accounts"] = {}
	i = 0
	for account in accounts:
		if account.source == AccountSource.ENV_VAR:
			continue
		i += 1
		conf["accounts"][f"account_{i}"] = {
			"name": account.name,
			"provider": account.provider.name,
			"api_key": account.api_key,
			"organization_key": account.organization_key,
			"use_organization_key": account.use_organization_key
		}
	conf.write()


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
