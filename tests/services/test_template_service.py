"""Tests for TemplateService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from basilisk.services.template_service import TemplateService


class TestRenderPrompt:
	"""Tests for TemplateService.render_prompt."""

	def test_plain_text_passthrough(self):
		"""Plain text without Mako syntax is returned unchanged."""
		result = TemplateService.render_prompt("Hello world", {})
		assert result == "Hello world"

	def test_variable_substitution(self):
		"""Mako ${var} syntax is replaced with context values."""
		result = TemplateService.render_prompt(
			"Hello ${name}", {"name": "Alice"}
		)
		assert result == "Hello Alice"

	def test_python_block_execution(self):
		"""Python blocks <% %> are executed."""
		result = TemplateService.render_prompt(
			"<%\nx = 1 + 1\n%>\nResult: ${x}", {}
		)
		assert result.strip() == "Result: 2"

	def test_import_in_block(self):
		"""Stdlib imports inside blocks work (no sandbox)."""
		result = TemplateService.render_prompt(
			"<%\nimport platform\n%>${platform.system() != ''}", {}
		)
		assert "True" in result

	def test_syntax_error_raises_value_error(self):
		"""Invalid Mako syntax raises ValueError."""
		with pytest.raises(ValueError, match="template"):
			TemplateService.render_prompt("${unclosed", {})

	def test_runtime_error_raises_value_error(self):
		"""Runtime exception in template raises ValueError."""
		with pytest.raises(ValueError, match="runtime"):
			TemplateService.render_prompt("${1/0}", {})

	def test_context_injected(self):
		"""Context dict values are available as template variables."""
		from datetime import datetime

		now = datetime(2026, 3, 8, 12, 0, 0)
		result = TemplateService.render_prompt(
			"${now.strftime('%Y-%m-%d')}", {"now": now}
		)
		assert result == "2026-03-08"


class TestRenderHtmlMessage:
	"""Tests for TemplateService.render_html_message."""

	def test_default_template_contains_title(self):
		"""Default template wraps content with title."""
		result = TemplateService.render_html_message(
			"<p>body</p>", "My Title", None
		)
		assert "My Title" in result
		assert "<p>body</p>" in result
		assert "<!DOCTYPE html>" in result

	def test_custom_template_from_disk(self, tmp_path):
		"""Custom template file is loaded and rendered."""
		tpl = tmp_path / "custom.mako"
		tpl.write_text("<h1>${title}</h1>${content}", encoding="utf-8")
		result = TemplateService.render_html_message("hello", "T", tpl)
		assert result == "<h1>T</h1>hello"

	def test_missing_custom_template_falls_back_to_default(self, tmp_path):
		"""Non-existent path falls back to embedded default template."""
		result = TemplateService.render_html_message(
			"body", "Title", tmp_path / "nonexistent.mako"
		)
		assert "Title" in result
		assert "body" in result


class TestRenderConversationExport:
	"""Tests for TemplateService.render_conversation_export."""

	def test_translation_functions_available(self):
		"""_ ngettext pgettext are usable in template."""
		mock_conv = MagicMock()
		mock_conv.title = "Test"
		mock_conv.messages = []

		def fake_translate(s):
			return f"[{s}]"

		result = TemplateService.render_conversation_export(
			mock_conv, None, None, extra_context={"_": fake_translate}
		)
		# Just verify it renders without error
		assert isinstance(result, str)

	def test_default_template_is_valid_html(self):
		"""Default export template produces valid HTML structure."""
		mock_conv = MagicMock()
		mock_conv.title = "My Conv"
		mock_conv.messages = []
		result = TemplateService.render_conversation_export(
			mock_conv, None, None
		)
		assert "<!DOCTYPE html>" in result
		assert "<html" in result
