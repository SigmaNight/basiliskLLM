from __future__ import annotations
from enum import Enum
from logging import getLogger
from os import getenv
from typing import Any, Iterable, Optional
from uuid import uuid4
from pydantic import (
	BaseModel,
	ConfigDict,
	Field,
	RootModel,
	SecretStr,
	UUID4,
	field_serializer,
	field_validator,
	model_validator,
	model_serializer,
)
from provider import Provider, providers, get_provider

log = getLogger(__name__)


class AccountSource(Enum):
	ENV_VAR = "env_var"
	CONFIG = "config"


class AccountOrganization(BaseModel):
	model_config = ConfigDict(populate_by_name=True)
	id: UUID4 = Field(default_factory=uuid4)
	name: str
	key: SecretStr
	source: AccountSource = Field(default=AccountSource.CONFIG, exclude=True)

	@field_serializer("key", when_used="json")
	def dump_secret(self, value: SecretStr) -> str:
		return value.get_secret_value()


class Account(BaseModel):
	"""
	Manage API key and organization key
	"""

	model_config = ConfigDict(populate_by_name=True)
	id: UUID4 = Field(default_factory=uuid4)
	name: str
	provider: Provider = Field(
		validation_alias="provider_id", serialization_alias="provider_id"
	)
	api_key: Optional[SecretStr] = Field(default=None)
	organizations: Optional[list[AccountOrganization]] = Field(default=None)
	active_organization: Optional[UUID4] = Field(default=None)
	source: AccountSource = Field(default=AccountSource.CONFIG, exclude=True)

	@field_serializer("provider", when_used="always")
	def serialize_provider(value: Provider) -> str:
		return value.id

	@field_serializer("api_key", when_used="json")
	def dump_secret(self, value: SecretStr) -> str:
		return value.get_secret_value()

	@field_validator("provider", mode="plain")
	@classmethod
	def validate_provider(cls, value: Any) -> Provider:
		if isinstance(value, Provider):
			return value
		if isinstance(value, str):
			return get_provider(id=value)
		raise ValueError("the value must be a string or a provider instance")

	@model_validator(mode="after")
	def require_keys(self) -> Account:
		if self.provider.require_api_key and not self.api_key:
			raise ValueError(f"API key for {self.provider.name} is required")
		if (
			not self.provider.organization_mode_available
			and self.active_organization
		):
			raise ValueError(
				f"Organization mode is not available for {self.provider.name}"
			)
		return self

	@model_validator(mode="after")
	def validate_active_organization(self) -> Account:
		if not self.active_organization:
			return self
		if not self.organizations:
			raise ValueError(
				f"No organizations found for {self.provider.name} account"
			)
		if not any(
			org.id == self.active_organization for org in self.organizations
		):
			raise ValueError(
				f"Organization '{self.active_organization}' not found for {self.provider.name} account"
			)
		return self


class AccountManager(RootModel[list[Account]]):
	"""
	Manage multiple accounts for different providers
	A provider can have several accounts
	"""

	def model_post_init(self, __context: Any) -> None:
		for provider in providers:
			organizations = []
			api_key = None
			if not provider.env_var_name_api_key:
				continue
			api_key = getenv(provider.env_var_name_api_key)
			if not api_key:
				continue
			active_organization = None
			if (
				provider.organization_mode_available
				and provider.env_var_name_organization_key
				and getenv(provider.env_var_name_organization_key)
			):
				active_organization = uuid4()
				organizations.append(
					AccountOrganization(
						id=active_organization,
						name=_("From environment variable"),
						key=SecretStr(
							getenv(provider.env_var_name_organization_key)
						),
						source=AccountSource.ENV_VAR,
					)
				)
			else:
				active_organization = None
			self.root.append(
				Account(
					name=f"{provider.name} account",
					provider=provider,
					api_key=api_key,
					organizations=organizations,
					active_organization=active_organization,
					source=AccountSource.ENV_VAR,
				)
			)

	@model_serializer(mode="plain", when_used="json")
	def serialize_account_config(self) -> list[dict[str, Any]]:
		accounts_config = filter(
			lambda x: x.source == AccountSource.CONFIG, self.root
		)
		return [
			acc.model_dump(mode="json", by_alias=True, exclude_none=True)
			for acc in accounts_config
		]

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


def get_account_source_labels() -> dict[AccountSource, str]:
	return {
		# Translators: Account source label
		AccountSource.ENV_VAR: _("Environment variable"),
		# Translators: Account source label
		AccountSource.CONFIG: _("Configuration file"),
	}
