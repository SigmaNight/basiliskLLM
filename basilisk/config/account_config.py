"""Module for managing accounts configuration for different AI providers."""

from __future__ import annotations

import logging
import re
from functools import cache, cached_property
from os import getenv
from typing import Annotated, Any, Iterable, Optional, Union
from uuid import UUID, uuid4

import keyring
from more_itertools import locate
from pydantic import (
	UUID4,
	BaseModel,
	ConfigDict,
	Field,
	FieldSerializationInfo,
	OnErrorOmit,
	SecretStr,
	SerializerFunctionWrapHandler,
	ValidationInfo,
	field_serializer,
	field_validator,
	model_validator,
)

import basilisk.global_vars as global_vars
from basilisk.consts import APP_NAME
from basilisk.provider import Provider, get_provider, providers

from .config_enums import AccountSource, KeyStorageMethodEnum
from .config_helper import (
	BasiliskBaseSettings,
	get_settings_config_dict,
	save_config_file,
)

log = logging.getLogger(__name__)

CUSTOM_BASE_URL_PATTERN = re.compile(
	r"^https?://[\w.-]+(?::\d{1,5})?(?:/[\w-]+)*/?$"
)


class AccountOrganization(BaseModel):
	"""Manage organization key for an account."""

	model_config = ConfigDict(populate_by_name=True)
	id: UUID4 = Field(default_factory=uuid4)
	name: str
	key_storage_method: KeyStorageMethodEnum = Field(
		default=KeyStorageMethodEnum.PLAIN
	)
	key: SecretStr
	source: AccountSource = Field(default=AccountSource.CONFIG, exclude=True)

	@field_validator("key", mode="before")
	@classmethod
	def validate_key(
		cls, value: Optional[Any], info: ValidationInfo
	) -> SecretStr:
		"""Validate organization key and return a SecretStr instance.

		Depending on the key storage method, the key is either a plain string or stored in the system keyring. If the key is stored in the system keyring, it is retrieved using the account ID.

		Args:
			value: Organization key value in the configuration file.
			info: Validation information.

		Returns:
			The organization key as a SecretStr instance.

		Raises:
			ValueError: If the key is not a string or the key storage method is invalid.
		"""
		if isinstance(value, SecretStr):
			return value
		data = info.data
		if data["key_storage_method"] == KeyStorageMethodEnum.PLAIN:
			if not isinstance(value, str):
				raise ValueError("Key must be a string")
			return SecretStr(value)
		elif data["key_storage_method"] == KeyStorageMethodEnum.SYSTEM:
			value = keyring.get_password(APP_NAME, str(data["id"]))
			if not value:
				raise ValueError("Key not found in keyring")
			return SecretStr(value)
		else:
			raise ValueError("Invalid key storage method")

	@field_serializer("key", when_used="json")
	def dump_secret(self, value: SecretStr) -> str:
		"""Serialize the organization key to a string in case of JSON serialization.

		Depending on the key storage method, the key is either a plain string or stored in the system keyring. If the key is stored in the system keyring, it is saved using the account ID.

		Args:
			value: Organization key value.

		Returns:
			The organization key as a string. Can be None if the key storage method is system.
		"""
		if self.key_storage_method == KeyStorageMethodEnum.PLAIN:
			return value.get_secret_value()
		elif self.key_storage_method == KeyStorageMethodEnum.SYSTEM:
			keyring.set_password(
				APP_NAME, str(self.id), value.get_secret_value()
			)
		return None

	def delete_keyring_password(self):
		"""Delete the organization key from the system keyring."""
		if self.key_storage_method == KeyStorageMethodEnum.SYSTEM:
			keyring.delete_password(APP_NAME, str(self.id))


AccountInfoStr = Annotated[str, Field(pattern="^env:[a-zA-Z]+")]
AccountInfo = Union[UUID4, AccountInfoStr]


class Account(BaseModel):
	"""Manage API key and organization key."""

	model_config = ConfigDict(populate_by_name=True)
	id: UUID4 = Field(default_factory=uuid4)
	name: str
	provider: Provider = Field(
		validation_alias="provider_id", serialization_alias="provider_id"
	)
	api_key_storage_method: Optional[KeyStorageMethodEnum] = Field(
		default=KeyStorageMethodEnum.PLAIN
	)
	api_key: Optional[SecretStr] = Field(default=None)
	organizations: Optional[list[AccountOrganization]] = Field(default=None)
	active_organization_id: Optional[UUID4] = Field(default=None)
	source: AccountSource = Field(default=AccountSource.CONFIG, exclude=True)
	custom_base_url: Optional[str] = Field(
		default=None,
		pattern=CUSTOM_BASE_URL_PATTERN,
		description="Custom base URL for the API provider. Must be a valid HTTP/HTTPS URL.",
	)

	def __init__(self, **data: Any):
		"""
		Initialize an account instance with the given configuration data.
		
		This constructor passes all provided keyword arguments to the superclass initializer. If an error occurs during initialization,
		the error is logged with detailed information and the exception is re-raised, preventing the creation of an incomplete account instance.
		
		Parameters:
		    **data (Any): Arbitrary keyword arguments representing the account configuration.
		
		Raises:
		    Exception: Propagates any exception caught during initialization.
		"""
		try:
			super().__init__(**data)
		except Exception as e:
			log.error(
				f"Error in account {e} the account will not be accessible",
				exc_info=e,
			)
			raise e

	@field_serializer("provider", when_used="always")
	def serialize_provider(value: Provider) -> str:
		"""Serialize the provider to a string. This is used when the provider is used in the JSON serialization.

		Args:
			value: Provider instance.

		Returns:
			The provider ID as a string.
		"""
		return value.id

	@field_validator("api_key", mode="before")
	@classmethod
	def validate_api_key(
		cls, value: Optional[Any], info: ValidationInfo
	) -> Optional[SecretStr]:
		"""
		Validate the API key configuration and return a SecretStr instance if applicable.
		
		This method checks the provided API key based on the configured key storage method:
		- If the API key is already a SecretStr, it is returned as-is.
		- For a plain string API key (when using plain storage), the value must be a string and is wrapped in a SecretStr.
		- For system storage, the key is retrieved from the system keyring using the account's identifier.
		- If the provider does not require an API key and the provided value is None, the function returns None.
		
		Parameters:
		    value (Optional[Any]): The API key from the configuration file, or an already wrapped SecretStr.
		    info (ValidationInfo): Validation context containing configuration data, including the API key storage method,
		                           account identifier, and provider details.
		
		Returns:
		    Optional[SecretStr]: The API key as a SecretStr instance if validation succeeds, or None if the provider
		                         does not require an API key and no key is provided.
		
		Raises:
		    ValueError: If the API key is not a string when using plain storage, if the API key is not found in the keyring
		                when using system storage, or if an invalid API key storage method is encountered.
		"""
		if isinstance(value, SecretStr):
			return value
		data = info.data
		if data["api_key_storage_method"] == KeyStorageMethodEnum.PLAIN:
			if not isinstance(value, str):
				raise ValueError("API key must be a string")
			return SecretStr(value)
		elif data["api_key_storage_method"] == KeyStorageMethodEnum.SYSTEM:
			value = keyring.get_password(APP_NAME, str(data["id"]))
			if not value:
				raise ValueError("API key not found in keyring")
			return SecretStr(value)
		elif not data["provider"].require_api_key and value is None:
			return None
		else:
			raise ValueError("Invalid API key storage method")

	@field_serializer("api_key", when_used="json")
	def dump_secret(self, value: SecretStr) -> Optional[str]:
		"""Serialize the API key to a string in case of JSON serialization.

		Depending on the key storage method, the API key is either a plain string or stored in the system keyring. If the key is stored in the system keyring, it is saved using the account ID.

		Args:
			value: API key value.

		Returns:
			The API key as a string. Can be None if the key storage method is system.
		"""
		if self.api_key_storage_method == KeyStorageMethodEnum.PLAIN:
			return value.get_secret_value()
		elif self.api_key_storage_method == KeyStorageMethodEnum.SYSTEM:
			keyring.set_password(
				APP_NAME, str(self.id), value.get_secret_value()
			)
		return None

	@field_validator("provider", mode="plain")
	@classmethod
	def validate_provider(cls, value: Any) -> Provider:
		"""Validate the provider and return a Provider instance.

		Args:
			value: Provider instance or provider ID.

		Returns:
			Provider instance.

		Raises:
			ValueError: If no provider exists for the given ID.
		"""
		if isinstance(value, Provider):
			return value
		if isinstance(value, str):
			return get_provider(id=value)

	@model_validator(mode="after")
	def require_keys(self) -> Account:
		"""Validate the account and check if the API key is required.

		Raises:
			ValueError: If the API key is required but not provided or the organization mode is not available and an organization is active.

		Returns:
			The account instance.
		"""
		if self.provider.require_api_key and not self.api_key:
			raise ValueError(f"API key for {self.provider.name} is required")
		if (
			not self.provider.organization_mode_available
			and self.active_organization_id
		):
			raise ValueError(
				f"Organization mode is not available for {self.provider.name}"
			)
		return self

	@model_validator(mode="after")
	def validate_active_organization(self) -> Account:
		"""Validate the account and check if the active organization exists.

		Raises:
			ValueError: If no organizations are found or the active organization does not exist.

		Returns:
			The account instance.
		"""
		if not self.active_organization_id:
			return self
		if not self.organizations:
			raise ValueError(
				f"No organizations found for {self.provider.name} account"
			)
		if not any(
			org.id == self.active_organization_id for org in self.organizations
		):
			raise ValueError(
				f"Organization '{self.active_organization_id}' not found for {self.provider.name} account"
			)
		return self

	@cached_property
	def active_organization(self) -> Optional[AccountOrganization]:
		"""Get the active organization for the account.

		Returns:
			The active organization instance or None if no active organization is set.
		"""
		if not self.active_organization_id:
			return None
		return next(
			filter(
				lambda x: x.id == self.active_organization_id,
				self.organizations,
			),
			None,
		)

	def reset_active_organization(self):
		"""Reset the active organization cached property for the account."""
		try:
			del self.__dict__["active_organization"]
		except KeyError:
			pass

	@property
	def active_organization_name(self) -> Optional[str]:
		"""Get the name of the active organization for the account.

		Returns:
			The name of the active organization or None if no active organization is set.
		"""
		return (
			self.active_organization.name if self.active_organization else None
		)

	@property
	def active_organization_key(self) -> Optional[SecretStr]:
		"""Get the key of the active organization for the account.

		Returns:
			The key of the active organization or None if no active organization is set.
		"""
		return (
			self.active_organization.key if self.active_organization else None
		)

	def delete_keyring_password(self):
		"""Delete the API key and organization keys from the system keyring."""
		if self.organizations:
			for org in self.organizations:
				org.delete_keyring_password()
		if self.api_key_storage_method == KeyStorageMethodEnum.SYSTEM:
			keyring.delete_password(APP_NAME, str(self.id))

	def get_account_info(self) -> AccountInfo:
		"""Get a summary of the account information.

		This meshod create a string for representing account information in other configurations file like conversation profile.

		Returns:
			A string representing the account information.
		"""
		if self.source == AccountSource.ENV_VAR:
			return f"env:{self.provider.name}"
		return self.id

	def __eq__(self, value: Account) -> bool:
		"""Compare two accounts by their ID.

		Args:
			value: Account instance to compare with.

		Returns:
			True if the accounts have the same ID, False otherwise.
		"""
		return self.id == value.id

	@property
	def display_name(self) -> str:
		"""Get the display name of the account.

		Aedding the account name, organization name, and provider name. If no active organization is set, the organization name is set to "Personal".

		Returns:
			The display name of the account.
		"""
		organization = (
			self.active_organization.name
			if self.active_organization
			else _("Personal")
		)
		provider_name = self.provider.name
		return f"{self.name} ({organization}) - {provider_name}"


config_file_name = "accounts.yml"


class AccountManager(BasiliskBaseSettings):
	"""Manage multiple accounts for different AI providers. This is stored in the accounts.yml file."""

	model_config = get_settings_config_dict(config_file_name)

	accounts: list[OnErrorOmit[Account]] = Field(default=list())

	default_account_info: Optional[AccountInfo] = Field(
		default=None, union_mode="left_to_right"
	)

	@cached_property
	def default_account(self) -> Account:
		"""Get the default account for the configuration. If the default account is not found, use the first account.

		Returns:
			The default account instance.
		"""
		account = self.get_account_from_info(self.default_account_info)
		if not account:
			log.warning(
				f"Default account not found for id {self.default_account_info} using the first account"
			)
			account = self[0]
		return account

	def get_account_from_info(self, value: AccountInfo) -> Optional[Account]:
		"""Get an account instance from the account information.

		Args:
			value: Account information as a UUID or a string.

		Returns:
			The account instance if found, None otherwise.
		"""
		if isinstance(value, UUID):
			try:
				return self[value]
			except KeyError:
				return None
		elif isinstance(value, str):
			provider_name = value[4:]
			index = next(
				locate(
					self.accounts,
					lambda x: x.provider.name == provider_name
					and x.source == AccountSource.ENV_VAR,
				),
				None,
			)
			if index is None:
				return self.accounts[0]
			return self.accounts[index]

	def set_default_account(self, value: Optional[Account]):
		"""Set the default account for the configuration.

		Args:
			value: Account instance or account information.

		Raises:
			ValueError: If the account is not an instance of Account.
		"""
		if not value or not isinstance(value, Account):
			self.default_account_info = None
			del self.__dict__["default_account"]
			return
		self.default_account_info = value.get_account_info()
		self.__dict__["default_account"] = value

	@field_validator("accounts", mode="after")
	@classmethod
	def add_accounts_from_env_vars(
		cls, accounts: list[Account]
	) -> list[Account]:
		"""Load accounts from environment variables for each provider.

		Args:
			accounts: List of accounts previously loaded from the configuration file.

		Returns:
			List of accounts with the accounts loaded from environment variables added.
		"""
		if global_vars.args.no_env_account:
			return accounts
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
			accounts.append(
				Account(
					name=f"{provider.name} account",
					provider=provider,
					api_key=api_key,
					organizations=organizations,
					active_organization_id=active_organization,
					source=AccountSource.ENV_VAR,
				)
			)
		return accounts

	@field_serializer("accounts", mode="wrap", when_used="json")
	@classmethod
	def serialize_accounts(
		cls,
		accounts: list[Account],
		handler: SerializerFunctionWrapHandler,
		info: FieldSerializationInfo,
	) -> list[dict[str, Any]]:
		"""Serialize accounts to a list of dictionaries. This is used when the accounts are serialized to JSON.

		Remove The account information from the configuration file if the account source is environment variable.

		Args:
			accounts: List of accounts to serialize.
			handler: The handler for the serialization function.
			info: Serialization information.

		Returns:
			List of dictionaries representing the accounts.
		"""
		accounts_config = filter(
			lambda x: x.source == AccountSource.CONFIG, accounts
		)
		return handler(list(accounts_config), info)

	def add(self, account: Account):
		"""Add an account to the configuration.

		Args:
			account: Account instance to add.

		Raises:
			ValueError: If the account is not an instance of Account.
		"""
		if not isinstance(account, Account):
			raise ValueError("Account must be an instance of Account")
		self.accounts.append(account)
		log.debug(
			f"Added account for {account.provider.name} ({account.name}, source: {account.source})"
		)

	def get_accounts_by_provider(
		self, provider_name: Optional[str] = None
	) -> Iterable[Account]:
		"""Get accounts by provider name.

		Args:
			provider_name: Provider name to filter accounts.

		Returns:
			Iterable of accounts for the provider.
		"""
		return filter(lambda x: x.provider.name == provider_name, self.accounts)

	def remove(self, account: Account):
		"""Remove an account from the configuration.

		Args:
			account: Account instance to remove.

		Raises:
			ValueError: If the account is not found in the configuration.
		"""
		account.delete_keyring_password()
		self.accounts.remove(account)

	def clear(self):
		"""Clear all accounts from the configuration."""
		self.accounts.clear()

	def __len__(self) -> int:
		"""Get the number of accounts in the configuration.

		Returns:
			The number of accounts in the configuration.
		"""
		return len(self.accounts)

	def __iter__(self):
		"""Iterate over the accounts in the configuration.

		Returns:
			An iterator for the accounts in the configuration.
		"""
		return iter(self.accounts)

	def __getitem__(self, index: int | UUID) -> Account:
		"""Get an account by index or ID. If the index is an integer, return the account at that index. If the index is a UUID, return the account with that ID.

		Args:
			index: Index or ID of the account.

		Returns:
			The account instance.

		Raises:
			KeyError: If the account is not found.
		"""
		if isinstance(index, int):
			return self.accounts[index]
		elif isinstance(index, UUID):
			try:
				return next(filter(lambda x: x.id == index, self.accounts))
			except StopIteration:
				raise KeyError(f"Account with id {index} not found")

	def __setitem__(self, index: int | UUID, value: Account):
		"""Set an account by index or ID. If the index is an integer, set the account at that index. If the index is a UUID, set the account with that ID.

		Args:
			index: Index or ID of the account.
			value: Account instance to set.
		"""
		if isinstance(index, int):
			self.accounts[index] = value
		elif isinstance(index, UUID):
			index = next(locate(self.accounts, lambda x: x.id == index), None)
			if index is None:
				self.accounts.append(value)
			else:
				self.accounts[index] = value

	def save(self):
		"""Save the accounts configuration to the accounts.yml file."""
		save_config_file(
			self.model_dump(
				mode="json",
				by_alias=True,
				exclude_defaults=True,
				exclude_none=True,
			),
			file_path=config_file_name,
		)


@cache
def get_account_config() -> AccountManager:
	"""Get the account configuration instance. This is cached to avoid loading the configuration multiple times.

	Returns:
		AccountManager instance.
	"""
	log.debug("Loading account config")
	return AccountManager()
