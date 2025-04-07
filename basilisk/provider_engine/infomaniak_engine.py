from __future__ import annotations

import logging
from functools import cached_property
from typing import TYPE_CHECKING

import httpx
from httpx import HTTPError

from .base_engine import ProviderAIModel
from .openai_engine import OpenAIEngine, ProviderCapability

if TYPE_CHECKING:
	from openai import OpenAI

log = logging.getLogger(__name__)


class InfomaniakEngine(OpenAIEngine):
	capabilities: set[ProviderCapability] = {
		ProviderCapability.TEXT,
		ProviderCapability.IMAGE,
	}

	@cached_property
	def headers(self):
		return {
			"Authorization": f"Bearer {self.account.api_key.get_secret_value()}",
			"Content-Type": "application/json",
			"User-Agent": self.get_user_agent(),
		}

	@cached_property
	def product_id(self):
		log.debug("Getting product_id")
		response = httpx.get(
			self.account.provider.base_url, headers=self.headers
		)
		if response.status_code == 200:
			if len(response.json()["data"]) > 1:
				raise ValueError("Multiple products found")
			if (
				"data" in response.json()
				and "product_id" in response.json()["data"][0]
			):
				return response.json()["data"][0]["product_id"]
			raise KeyError(
				f"product_id not found in response\n{response.json()}"
			)
		raise HTTPError(response.status_code, response.text)

	@cached_property
	def client(self) -> OpenAI:
		client = super().client
		product_id = self.product_id
		client.base_url = (
			f"{self.account.provider.base_url}/{product_id}/openai/"
		)
		return client

	@cached_property
	def models(self) -> list[ProviderAIModel]:
		"""
		Get models
		"""
		log.debug("Getting openAI models")
		# See <https://www.infomaniak.com/en/hosting/ai-tools/open-source-models#llm>
		return [
			ProviderAIModel(
				id="llama3",
				name="LLama 3 70B",
				# Translators: This is a model description
				description=(
					"● "
					+ _(
						"Optimised to handle large amounts of text ensuring consistency across multiple sources"
					)
					+ '\n'
					"● "
					+ _(
						"Excellent in development, programming and academic research tasks"
					)
					+ '\n'
					"● "
					+ _(
						"High multilingual flexibility with more than 30 languages supported"
					)
					+ '\n'
					"● "
					+ _(
						"Suitable for artists and content creation, including storytelling"
					)
				),
				context_window=126000,
				max_output_tokens=8000,
				vision=False,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="mixtral8x22b",
				name="Mixtral 8x22B",
				# Translators: This is a model description
				description=(
					"● "
					+ _(
						"Larger training corpus than Mixtral 8x7B for more complex tasks"
					)
					+ '\n'
					"● "
					+ _(
						"Able to analyse unstructured data to support decision making and generate content"
					)
					+ '\n'
					"● "
					+ _(
						"Management of conversational subtleties to feed complex discussions"
					)
					+ '\n'
					"● "
					+ _(
						"Optimised for logical exploration (combining complex information) and generating ideas (scenarios, etc.)"
					)
				),
				context_window=23000,
				max_output_tokens=23000,
				vision=False,
				max_temperature=2.0,
			),
			ProviderAIModel(
				id="mixtral",
				name="Mixtral 8x7B",
				# Translators: This is a model description
				description=(
					"● "
					+ _("Economical and very fast for many common tasks")
					+ '\n'
					"● "
					+ _(
						"Ideal for summarising, moderating, calculating, coding and extracting data from unstructured sources"
					)
					+ '\n'
					"● "
					+ _(
						"Suitable for real-time interpretation of data and for logical reasoning"
					)
					+ '\n'
					"● "
					+ _(
						"Easy to adjust and contextualise in order to limit undesirable outcomes"
					)
				),
				context_window=30000,
				max_output_tokens=30000,
				vision=False,
				max_temperature=2.0,
			),
		]
