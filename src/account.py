import os
from typing import List
from config import conf
from logging import getLogger
from provider import providers, Provider

log = getLogger(__name__)
accountManager = None


class Account:
	"""
	Manage API key and organization key
	"""

	index = -1

	def __init__(self, provider: Provider, **kwargs):
		self._provider = provider
		self._api_key = kwargs.get("api_key")
		self._organization_key = kwargs.get("organization_key")
		self._custom_models = kwargs.get("custom_models", [])
		self._name = kwargs.get("name", None)
		self._validate()
		Account.index += 1

	def _validate(self):
		if self._provider.require_api_key and not self._api_key:
			raise ValueError(f"API key for {self._provider.name} is required")
		if (
			not self._provider.organization_mode_available
			and self._organization_key
		):
			raise ValueError(
				f"Organization mode is not available for {self._provider.name}"
			)

	@property
	def api_key(self) -> str:
		if self._api_key:
			return self._api_key
		else:
			self._api_key = conf["services"][self._provider.name]["api_key"]
		return self._api_key

	@property
	def name(self) -> str:
		if not self._name or not self._name.strip():
			account_index = Account.index
			return f"#{account_index}@{self._provider.name}"
		return self._name

	@api_key.setter
	def api_key(self, value: str):
		self._api_key = value

	@property
	def organization_key(self) -> str:
		return self._organization_key

	@organization_key.setter
	def organization_key(self, value: str):
		self._organization_key = value

	@property
	def provider(self) -> Provider:
		return self._provider

	@provider.setter
	def provider(self, value: Provider):
		raise ValueError("Provider cannot be changed")


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
		log.debug(f"Added account for {account.provider.name}")

	def get(self, provider_name: str = None) -> List[Account]:
		if provider_name:
			return [
				account
				for account in self._accounts
				if account._provider.name == provider_name
			]
		return self._accounts

	def remove(self, account: Account):
		self._accounts.remove(account)

	def clear(self):
		self._accounts.clear()


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
		if (
			provider.organization_mode_available
			and provider.env_var_name_organization_key
		):
			organization_key = os.getenv(provider.env_var_name_organization_key)
		account = Account(
			provider, api_key=api_key, organization_key=organization_key
		)
		accountManager.add(account)
