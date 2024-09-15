import logging
import time
from datetime import datetime
from decimal import Decimal, getcontext
from functools import cached_property

import httpx

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

log = logging.getLogger(__name__)

getcontext().prec = 20


class OpenRouterEngine(OpenAIEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	def summarize_pricing(self, pricing: dict[str, dict[str, str]]) -> str:
		if not isinstance(pricing, dict):
			return ""
		out = "\n"
		for usage_type, price in pricing.items():
			if price is None or price == '0':
				continue
			if usage_type == "image":
				price_1k = round(Decimal(price) * Decimal(1000), 3)
				if price_1k == 0:
					continue
				out += f"  {usage_type}: ${price_1k}/K input imgs (${price}/input img)\n"
			else:
				price_1m = round(Decimal(price) * Decimal(1000000), 2)
				out += (
					f"  {usage_type}: ${price_1m}/M tokens (${price}/token)\n"
				)
		return out.rstrip()

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
				extra_info = {}
				for k, v in sorted(model.items()):
					match k:
						case (
							"id"
							| "name"
							| "description"
							| "context_length"
							| "top_provider"
						):
							continue
						case "pricing":
							summary = self.summarize_pricing(v)
							if summary:
								extra_info["Pricing"] = summary
						case "created":
							extra_info[k] = datetime.fromtimestamp(v).strftime(
								"%Y-%m-%d %H:%M:%S"
							)
						case _:
							if v is None:
								continue
							extra_info[k.replace('_', ' ')] = v
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
						max_temperature=2.0,
						vision="text+image->text"
						in model.get("architecture", {}).get("modality", ''),
						extra_info=extra_info,
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
