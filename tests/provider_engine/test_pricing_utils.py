"""Tests for generic pricing utilities."""

from unittest.mock import MagicMock

from basilisk.provider_engine.pricing_utils import (
	ModelPricing,
	apply_block_cost_and_pricing,
	compute_cost_breakdown,
	compute_cost_from_usage,
	get_price_at,
	merge_pricing_into_conversation,
	parse_pricing_from_json,
)


class TestParsePricingFromJson:
	"""Tests for parse_pricing_from_json."""

	def test_parses_openrouter_style_pricing(self):
		"""Parse OpenRouter-style pricing from model JSON."""
		item = {
			"id": "test-model",
			"pricing": {
				"prompt": "0.000008",
				"completion": "0.000024",
				"image": "0",
				"request": "0",
				"input_cache_read": "0.000002",
			},
		}
		pricing = parse_pricing_from_json(item)
		assert pricing is not None
		assert pricing.prompt == 0.000008
		assert pricing.completion == 0.000024
		assert pricing.input_cache_read == 0.000002
		assert pricing.image == 0.0
		assert pricing.request == 0.0

	def test_returns_none_when_no_pricing(self):
		"""Return None when pricing key is absent."""
		item = {"id": "test", "name": "Test Model"}
		assert parse_pricing_from_json(item) is None

	def test_returns_none_when_pricing_empty(self):
		"""Return None when all prices are zero."""
		item = {"pricing": {"prompt": "0", "completion": "0"}}
		assert parse_pricing_from_json(item) is None

	def test_returns_none_when_pricing_invalid(self):
		"""Return None when pricing is not a dict."""
		item = {"pricing": "invalid"}
		assert parse_pricing_from_json(item) is None


class TestModelPricing:
	"""Tests for ModelPricing."""

	def test_has_usable_pricing_true_when_prompt(self):
		"""has_usable_pricing True when prompt > 0."""
		p = ModelPricing(prompt=0.000001)
		assert p.has_usable_pricing() is True

	def test_has_usable_pricing_true_when_completion(self):
		"""has_usable_pricing True when completion > 0."""
		p = ModelPricing(completion=0.000002)
		assert p.has_usable_pricing() is True

	def test_has_usable_pricing_false_when_all_zero(self):
		"""has_usable_pricing False when all token prices zero."""
		p = ModelPricing()
		assert p.has_usable_pricing() is False


class TestComputeCostFromUsage:
	"""Tests for compute_cost_from_usage."""

	def test_basic_prompt_completion(self):
		"""Compute cost from prompt and completion tokens."""
		pricing = ModelPricing(prompt=0.000001, completion=0.000002)
		cost = compute_cost_from_usage(
			pricing, input_tokens=1000, output_tokens=500
		)
		assert cost == 1000 * 0.000001 + 500 * 0.000002
		assert cost == 0.002

	def test_with_cached_tokens(self):
		"""Cached tokens use input_cache_read when available."""
		pricing = ModelPricing(
			prompt=0.00001, completion=0.00002, input_cache_read=0.000001
		)
		cost = compute_cost_from_usage(
			pricing,
			input_tokens=1000,
			output_tokens=100,
			cached_input_tokens=200,
		)
		# 800 fresh * 0.00001 + 200 cached * 0.000001 + 100 * 0.00002
		expected = 800 * 0.00001 + 200 * 0.000001 + 100 * 0.00002
		assert abs(cost - expected) < 1e-10


class TestComputeCostBreakdown:
	"""Tests for compute_cost_breakdown."""

	def test_basic_input_output(self):
		"""Breakdown includes input and output when present."""
		pricing = ModelPricing(prompt=0.000001, completion=0.000002)
		result = compute_cost_breakdown(
			pricing, input_tokens=1000, output_tokens=500
		)
		assert result["input"] == 1000 * 0.000001
		assert result["output"] == 500 * 0.000002

	def test_reasoning_tokens_separate(self):
		"""Reasoning tokens get separate entry from text output."""
		pricing = ModelPricing(completion=0.000002)
		result = compute_cost_breakdown(
			pricing, input_tokens=0, output_tokens=100, reasoning_tokens=30
		)
		assert result["output"] == 70 * 0.000002
		assert result["reasoning"] == 30 * 0.000002

	def test_cached_and_cache_write(self):
		"""Cached and cache_write use respective prices."""
		pricing = ModelPricing(
			prompt=0.00001,
			input_cache_read=0.000001,
			input_cache_write=0.000005,
		)
		result = compute_cost_breakdown(
			pricing,
			input_tokens=200,
			output_tokens=0,
			cached_input_tokens=50,
			cache_write_tokens=30,
		)
		# fresh = 200 - 50 - 30 = 120
		assert result["input"] == 120 * 0.00001
		assert result["cached"] == 50 * 0.000001
		assert result["cache_write"] == 30 * 0.000005

	def test_request_fee_included(self):
		"""Request fee included when pricing.request > 0."""
		pricing = ModelPricing(prompt=0.000001, request=0.002)
		result = compute_cost_breakdown(
			pricing, input_tokens=100, output_tokens=0
		)
		assert result["request"] == 0.002

	def test_image_count(self):
		"""Image count uses image price."""
		pricing = ModelPricing(image=0.01)
		result = compute_cost_breakdown(
			pricing, input_tokens=0, output_tokens=0, image_count=3
		)
		assert result["image"] == 3 * 0.01


class TestGetPriceAt:
	"""Tests for get_price_at."""

	def test_returns_price_at_or_before_iso(self):
		"""Uses largest key <= block_created_at_iso."""
		history = {
			"prompt": {
				"2026-01-01T00:00:00": 0.001,
				"2026-02-01T00:00:00": 0.002,
			}
		}
		result = get_price_at(history, "2026-01-15T12:00:00")
		assert result["prompt"] == 0.001

	def test_uses_exact_match(self):
		"""Exact ISO match returns that price."""
		history = {"prompt": {"2026-01-01T12:00:00": 0.001}}
		result = get_price_at(history, "2026-01-01T12:00:00")
		assert result["prompt"] == 0.001


class TestMergePricingIntoConversation:
	"""Tests for merge_pricing_into_conversation."""

	def test_creates_model_entry(self):
		"""Adds model_id to pricing_snapshot with field history."""
		from basilisk.conversation import Conversation

		conv = Conversation()
		pricing = ModelPricing(prompt=0.000001, completion=0.000002)
		merge_pricing_into_conversation(
			conv, "anthropic/claude-3", pricing, "2026-01-01T12:00:00"
		)
		assert "anthropic/claude-3" in conv.pricing_snapshot
		assert "prompt" in conv.pricing_snapshot["anthropic/claude-3"]
		assert (
			conv.pricing_snapshot["anthropic/claude-3"]["prompt"][
				"2026-01-01T12:00:00"
			]
			== 0.000001
		)


class TestApplyBlockCostAndPricing:
	"""Tests for apply_block_cost_and_pricing."""

	def test_uses_provider_cost_when_available(self):
		"""block.cost set from usage.cost when provider reports it."""
		from basilisk.conversation import (
			Conversation,
			Message,
			MessageBlock,
			MessageRoleEnum,
		)
		from basilisk.conversation.conversation_model import TokenUsage
		from basilisk.provider_ai_model import AIModelInfo

		conv = Conversation()
		model_info = AIModelInfo(provider_id="openai", model_id="gpt-4")
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=model_info,
			usage=TokenUsage(input_tokens=100, output_tokens=50, cost=0.005),
		)
		conv.add_block(block)

		engine = MagicMock()
		engine.get_model.return_value = None

		apply_block_cost_and_pricing(block, conv, engine)
		assert block.cost == 0.005

	def test_computes_cost_when_no_provider_cost(self):
		"""Computes cost from pricing when usage.cost not set."""
		from basilisk.conversation import (
			Conversation,
			Message,
			MessageBlock,
			MessageRoleEnum,
		)
		from basilisk.conversation.conversation_model import TokenUsage
		from basilisk.provider_ai_model import AIModelInfo, ProviderAIModel

		conv = Conversation()
		model_info = AIModelInfo(provider_id="openai", model_id="gpt-4")
		req = Message(role=MessageRoleEnum.USER, content="q")
		resp = Message(role=MessageRoleEnum.ASSISTANT, content="a")
		block = MessageBlock(
			request=req,
			response=resp,
			model=model_info,
			usage=TokenUsage(input_tokens=1000, output_tokens=500),
		)
		conv.add_block(block)

		engine = MagicMock()
		engine.get_model.return_value = ProviderAIModel(
			id="gpt-4",
			pricing=ModelPricing(prompt=0.000001, completion=0.000002),
		)

		apply_block_cost_and_pricing(block, conv, engine)
		expected = 1000 * 0.000001 + 500 * 0.000002
		assert abs(block.cost - expected) < 1e-10
		assert "input" in block.cost_breakdown
		assert "output" in block.cost_breakdown
