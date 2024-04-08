from enum import Enum
from typing import Optional, Iterable, Any
from pydantic import BaseModel, HttpUrl, Field
from logging import getLogger

log = getLogger(__name__)


class ProviderAPIType(Enum):
	OPENAI = "openai"
	ANTHROPIC = "anthropic"
	OLLAMA = "ollama"


class Provider(BaseModel):
	"""
	Manage API key
	"""

	id: str
	name: str
	base_url: HttpUrl
	api_type: ProviderAPIType
	organization_mode_available: bool = Field(default=False)
	require_api_key: bool = Field(default=True)
	custom: bool = Field(default=True)
	env_var_name_api_key: Optional[str] = Field(default=None)
	env_var_name_organization_key: Optional[str] = Field(default=None)


providers = [
	Provider(
		id="openai",
		name="OpenAI",
		base_url="https://api.openai.com/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=True,
		require_api_key=True,
		env_var_name_api_key="OPENAI_API_KEY",
		env_var_name_organization_key="OPENAI_ORG_KEY",
	),
	Provider(
		id="mistralai",
		name="MistralAI",
		base_url="https://api.mistral.ai/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="MISTRAL_API_KEY",
	),
	Provider(
		id="openrouter",
		name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="OPENROUTER_API_KEY",
	),
]


def get_providers(**kwargs: dict[str, Any]) -> Iterable[Provider]:
	"""
	Get provider by criteria
	"""
	match_providers = providers
	for k, v in kwargs.items():
		match_providers = list(
			filter(lambda x: getattr(x, k, None) == v, match_providers)
		)
	return match_providers


def get_provider(**kwargs: dict[str, Any]) -> Provider:
	"""
	Get provider by criteria
	"""
	match_providers = list(get_providers(**kwargs))
	if not match_providers or len(match_providers) == 0:
		raise ValueError("No provider found")
	if len(match_providers) > 1:
		raise ValueError("Multiple providers found")
	return match_providers[0]
