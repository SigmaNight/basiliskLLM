import logging
import time
import httpx
from functools import cached_property
from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)


class OpenRouterEngine(OpenAIEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		models = []
		log.debug("Getting openRouter models")
		start_time = time.time()
		url = "https://openrouter.ai/api/v1/models"
		response = httpx.get(url, headers={"User-Agent": self.get_user_agent()})
		if response.status_code == 200:
			data = response.json()
			for model in sorted(data["data"], key=lambda m: m["name"].lower()):
				models.append(
					ProviderAIModel(
						id=model["id"],
						name=model["name"],
						description=model["description"],
						context_window=int(model["context_length"]),
						max_output_tokens=model.get("top_provider").get(
							"max_completion_tokens"
						)
						or -1,
						max_temperature=2,
						vision="#multimodal" in model['description'],
						preview="-preview" in model['id'],
						extra_info={
							k: v
							for k, v in model.items()
							if k
							not in (
								"id",
								"name",
								"description",
								"context_length",
								"top_provider",
							)
						},
					)
				)
			log.debug(
				f"Got {len(models)} models in {time.time() - start_time:.2f} seconds"
			)
		else:
			log.error(
				f"Failed to get models from {url}. Response: {response.text}"
			)
		return models
