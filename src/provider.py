import re
from logging import getLogger

log = getLogger(__name__)


class Provider:
	"""
	Manage API key
	"""

	def __init__(
		self,
		name: str,
		base_url: str,
		organization_mode_available: bool = False,
		require_api_key: bool = True,
		custom: bool = False,
		env_var_name_api_key: str = None,
		env_var_name_organization_key: str = None,
	):
		if not isinstance(name, str) or not name:
			raise ValueError("Provider name is required")
		if (
			not isinstance(base_url, str)
			or not base_url
			or not re.match(r"^https?://", base_url)
		):
			raise ValueError("Base URL is required and must be a valid URL")
		if not isinstance(organization_mode_available, bool):
			raise ValueError("organization_mode_available must be a boolean")
		if not isinstance(custom, bool):
			raise ValueError("custom must be a boolean")
		if not isinstance(require_api_key, bool):
			raise ValueError("require_api_key must be a boolean")
		self.name = name
		self.base_url = base_url
		self.organization_mode_available = organization_mode_available
		self.require_api_key = require_api_key
		self.custom = custom
		self.env_var_name_api_key = env_var_name_api_key
		self.env_var_name_organization_key = env_var_name_organization_key


providers = [
	Provider(
		name="OpenAI",
		base_url="https://api.openai.com/v1",
		organization_mode_available=True,
		require_api_key=True,
		env_var_name_api_key="OPENAI_API_KEY",
		env_var_name_organization_key="OPENAI_ORG_KEY",
	),
	Provider(
		name="MistralAI",
		base_url="https://api.mistral.ai/v1",
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="MISTRAL_API_KEY",
	),
	Provider(
		name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="OPENROUTER_API_KEY",
	),
]


def get(provider_name: str) -> Provider:
	if provider_name not in providers:
		raise ValueError(f"Provider '{provider_name}' is not supported")
	return providers[provider_name]
