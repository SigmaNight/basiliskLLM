import os
from enum import Enum
from typing import List, Union
from config import conf
from logging import getLogger
from provider import providers, Provider, get_provider

log = getLogger(__name__)

accountManager = None

class AccountSource(Enum):

	ENV_VAR = "env_var"
	CONFIG = "config"
	UNKNOWN = "unknown"

class Account:

	"""
	Manage API key and organization key
	"""

	def __init__(
		self,
		provider: Union[str, Provider],
		source: AccountSource = AccountSource.UNKNOWN,
		**kwargs
	):
		name = kwargs.get("name")
		if isinstance(provider, str):
			provider = get_provider(provider)
		if not isinstance(provider, Provider):
			raise TypeError(f"Provider must be an instance of Provider. Got: {provider}")
		api_key = kwargs.get("api_key")
		if provider.require_api_key and not api_key:
			raise ValueError(f"API key for {provider.name} is required")
		use_organization_key = kwargs.get("use_organization_key", False)
		organization_key = kwargs.get("organization_key")
		if (
			not provider.organization_mode_available
			and organization_key
		):
			raise ValueError(
				f"Organization mode is not available for {provider.name}"
			)
		if isinstance(source, str):
			try:
				source = AccountSource(source)
			except ValueError:
				raise ValueError(f"Invalid source: {source}")

		self._name = name
		self._provider = provider
		self._api_key = api_key
		self._use_organization_key = use_organization_key
		self._organization_key = organization_key
		self._source = source
		# TODO: Implement custom models

	@property
	def name(self) -> str:
		return self._name or f"{self._provider.name} account"

	@property
	def provider(self) -> Provider:
		return self._provider

	@provider.setter
	def provider(self, value: Provider):
		raise ValueError("Provider cannot be changed")

	@property
	def api_key(self) -> str:
		if self._api_key:
			return self._api_key
		else:
			self._api_key = conf["services"][self._provider.name]["api_key"]
		return self._api_key

	@api_key.setter
	def api_key(self, value: str):
		self._api_key = value

	@property
	def use_organization_key(self) -> bool:
		return self._provider.organization_mode_available and self._use_organization_key

	@property
	def organization_key(self) -> str:
		return self._organization_key

	@organization_key.setter
	def organization_key(self, value: str):
		self._organization_key = value

	@property
	def source(self) -> AccountSource:
		return self._source

	def dump(self):
		return {
			"name": self._name,
			"provider": self._provider.name,
			"api_key": self._api_key,
			"organization_key": self._organization_key,
			"source": self._source.value
		}


class AccountManager:

	"""
	Manage multiple accounts for different providers
	A provider can have several accounts
	"""

	def __init__(self):
		self._accounts = []

	def add(self, account: Account):
		if not isinstance(account, Account):
			raise ValueError("Account must be an instance of Account")
		self._accounts.append(account)
		log.debug(f"Added account for {account.provider.name} ({account.name}, source: {account.source})")

	def get(self, provider_name: str = None) -> List[Account]:
		if provider_name:
			return [account for account in self._accounts if account._provider.name == provider_name]
		return self._accounts

	def remove(self, account: Account):
		self._accounts.remove(account)

	def clear(self):
		self._accounts.clear()

	def __len__(self):
		return len(self._accounts)

	def __iter__(self):
		return iter(self._accounts)

	def __getitem__(self, index):
		return self._accounts[index]

	def __setitem__(self, index, value):
		self._accounts[index] = value

	def dump(
			self,
			source: AccountSource = None
	) -> dict:
		accounts = []
		for account in self._accounts:
			accounts.append(account.dump())
		if source:
			accounts = filter(lambda x: x["source"] == source.value, accounts)
		return accounts

	def load(self, accounts):
		self.clear()
		for account_data in accounts:
			log.debug(f"Loading account: {account_data}")
			provider = get_provider(account_data["provider"])
			account = Account(
				provider=provider,
				name=account_data["name"],
				api_key=account_data["api_key"],
				organization_key=account_data["organization_key"],
				#custom_models=account_data["custom_models"],
				source=account_data.get("source", AccountSource.UNKNOWN)
			)
			self.add(account)

	def copy(self):
		newAccountManager = AccountManager()
		newAccountManager.load(self.dump())
		return newAccountManager


ACCOUNT_SOURCE_LABELS = {
	AccountSource.ENV_VAR: "Environment variable",
	AccountSource.CONFIG: "Configuration file",
	AccountSource.UNKNOWN: "Unknown"
}


def initialize_accountManager():
	global accountManager
	accountManager = AccountManager()
	for provider in providers:
		api_key = None
		if not provider.env_var_name_api_key:
			continue
		api_key = os.getenv(provider.env_var_name_api_key)
		if not api_key:
			continue
		organization_key = None
		if provider.organization_mode_available and provider.env_var_name_organization_key:
			organization_key = os.getenv(provider.env_var_name_organization_key)
		account = Account(
			provider=provider,
			api_key=api_key,
			organization_key=organization_key,
			source=AccountSource.ENV_VAR
		)
		accountManager.add(account)

	accounts = conf["accounts"]
	for account_data in accounts.values():
		provider = get_provider(account_data["provider"])
		account = Account(
			provider=provider,
			name=account_data["name"],
			api_key=account_data["api_key"],
			organization_key=account_data["organization_key"],
			use_organization_key=account_data["use_organization_key"],
			source=AccountSource.CONFIG
		)
		accountManager.add(account)

