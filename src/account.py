from __future__ import annotations
from enum import Enum
from logging import getLogger
from typing import Any, Iterable, Optional
from pydantic import (
	BaseModel,
	RootModel,
	Field,
	field_serializer,
	field_validator,
	model_validator,
	SecretStr,
	model_serializer,
	ConfigDict,
)
from provider import Provider, get_providers

log = getLogger(__name__)


class AccountSource(Enum):
	ENV_VAR = "env_var"
	CONFIG = "config"
	UNKNOWN = "unknown"


class Account(BaseModel):
	"""
	Manage API key and organization key
	"""

	model_config = ConfigDict(populate_by_name=True)
	name: str
	use_organization_key: bool = Field(default=False)
	api_key: Optional[SecretStr] = Field(default=None)
	organization_key: Optional[SecretStr] = Field(default=None)
	source: AccountSource = Field(default=AccountSource.UNKNOWN)
	provider: Provider = Field(
		validation_alias="providerID", serialization_alias="providerId"
	)

	@field_serializer("provider", when_used="always")
	def serialize_provider(value: Provider) -> str:
		return value.id

	@field_serializer("api_key", "organization_key", when_used="json")
	def dump_secret(self, value: SecretStr) -> str:
		return value.get_secret_value()

	@field_validator("provider", mode="plain")
	@classmethod
	def validate_provider(cls, value: Any) -> Provider:
		if isinstance(value, Provider):
			return value
		if isinstance(value, str):
			return get_providers(id=value)[0]
		raise ValueError("the value must be a string or a provider instance")

	@model_validator(mode="after")
	def require_keys(self) -> Account:
		if self.provider.require_api_key and not self.api_key:
			raise ValueError(f"API key for {self.provider.name} is required")
		if (
			not self.provider.organization_mode_available
			and not self.use_organization_key
			and self.organization_key
		):
			raise ValueError(
				f"Organization mode is not available for {self.provider.name}"
			)
		return self


class AccountManager(RootModel[list[Account]]):
	"""
	Manage multiple accounts for different providers
	A provider can have several accounts
	"""

	@model_serializer(mode="plain", when_used="json")
	def serialize_account_config(self) -> list[dict[str, Any]]:
		accounts_config = filter(
			lambda x: x.source == AccountSource.CONFIG, self.root
		)
		return [acc.model_dump(mode="json") for acc in accounts_config]

	def add(self, account: Account):
		if not isinstance(account, Account):
			raise ValueError("Account must be an instance of Account")
		self.root.append(account)
		log.debug(
			f"Added account for {account.provider.name} ({account.name}, source: {account.source})"
		)

	def get_accounts_by_provider(
		self, provider_name: Optional[str] = None
	) -> Iterable[Account]:
		return filter(lambda x: x.provider.name == provider_name, self.root)

	def remove(self, account: Account):
		self.root.remove(account)

	def clear(self):
		self.root.clear()

	def __len__(self):
		return len(self.root)

	def __iter__(self):
		return iter(self.root)

	def __getitem__(self, index):
		return self.root[index]

	def __setitem__(self, index, value):
		self.root[index] = value


ACCOUNT_SOURCE_LABELS = {
	AccountSource.ENV_VAR: "Environment variable",
	AccountSource.CONFIG: "Configuration file",
	AccountSource.UNKNOWN: "Unknown",
}

"""
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
			provider=provider,
			api_key=api_key,
			organization_key=organization_key,
			source=AccountSource.ENV_VAR,
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
			source=AccountSource.CONFIG,
		)
		accountManager.add(account)
"""
