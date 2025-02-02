from __future__ import annotations

import logging
from dataclasses import dataclass, field
from functools import cached_property
from typing import TYPE_CHECKING, Any, Iterable, Optional, Type

from .decorators import measure_time
from .enums import ProviderAPIType

if TYPE_CHECKING:
	from .provider_engine.base_engine import BaseEngine

log = logging.getLogger(__name__)


@dataclass
class Provider:
	"""
	Manage API key
	"""

	id: str
	name: str
	api_type: ProviderAPIType
	engine_cls_path: str
	base_url: Optional[str] = field(default=None)
	organization_mode_available: bool = field(default=False)
	require_api_key: bool = field(default=True)
	custom: bool = field(default=True)
	env_var_name_api_key: Optional[str] = field(default=None)
	env_var_name_organization_key: Optional[str] = field(default=None)

	@cached_property
	@measure_time
	def engine_cls(self) -> Type[BaseEngine]:
		"""
		Get engine class
		"""
		try:
			module_path, class_name = self.engine_cls_path.rsplit(".", 1)
			module = __import__(module_path, fromlist=[class_name])
			cls = getattr(module, class_name)
			return cls
		except ImportError as e:
			log.error(f"Error importing engine class: {e}")
			raise e
		except AttributeError as e:
			log.error(f"Error getting engine class: {e}")
			raise e


providers = [
	Provider(
		id="anthropic",
		name="Anthropic",
		api_type=ProviderAPIType.ANTHROPIC,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="ANTHROPIC_API_KEY",
		env_var_name_organization_key="ANTHROPIC_ORG_KEY",
		engine_cls_path="basilisk.provider_engine.anthropic_engine.AnthropicEngine",
	),
	Provider(
		id="deepseek",
		name="DeepSeek",
		api_type=ProviderAPIType.OPENAI,
		base_url="https://api.deepseek.com/v1",
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="DEEPSEEK_API_KEY",
		env_var_name_organization_key=None,
		engine_cls_path="basilisk.provider_engine.deepseek_engine.DeepSeekAIEngine",
	),
	Provider(
		id="gemini",
		name="Gemini",
		base_url="https://generativelanguage.googleapis.com",
		api_type=ProviderAPIType.GEMINI,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="GOOGLE_API_KEY",
		engine_cls_path="basilisk.provider_engine.gemini_engine.GeminiEngine",
	),
	Provider(
		id="mistralai",
		name="MistralAI",
		base_url="https://api.mistral.ai/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="MISTRAL_API_KEY",
		engine_cls_path="basilisk.provider_engine.mistralai_engine.MistralAIEngine",
	),
	Provider(
		id="openai",
		name="OpenAI",
		base_url="https://api.openai.com/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=True,
		require_api_key=True,
		env_var_name_api_key="OPENAI_API_KEY",
		env_var_name_organization_key="OPENAI_ORG_KEY",
		engine_cls_path="basilisk.provider_engine.openai_engine.OpenAIEngine",
	),
	Provider(
		id="openrouter",
		name="OpenRouter",
		base_url="https://openrouter.ai/api/v1",
		api_type=ProviderAPIType.OPENAI,
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="OPENROUTER_API_KEY",
		engine_cls_path="basilisk.provider_engine.openrouter_engine.OpenRouterEngine",
	),
	Provider(
		id="xai",
		name="xAI",
		api_type=ProviderAPIType.OPENAI,
		base_url="https://api.x.ai/v1",
		organization_mode_available=False,
		require_api_key=True,
		env_var_name_api_key="XAI_API_KEY",
		env_var_name_organization_key=None,
		engine_cls_path="basilisk.provider_engine.xai_engine.XAIEngine",
	),
]


def get_providers(**kwargs: dict[str, Any]) -> Iterable[Provider]:
	"""
	Get provider by criteria
	"""
	match_providers = providers
	for k, v in kwargs.items():
		match_providers = filter(
			lambda x: getattr(x, k, None) == v, match_providers
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
