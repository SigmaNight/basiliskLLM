"""Tests for BaseConversationPresenter."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from basilisk.presenters.base_conversation_presenter import (
	BaseConversationPresenter,
)


@pytest.fixture
def presenter():
	"""Return a BaseConversationPresenter with a mock service."""
	return BaseConversationPresenter()


class TestRenderSystemPrompt:
	"""Tests for BaseConversationPresenter.render_system_prompt."""

	def test_empty_prompt_returns_empty(self, presenter):
		"""Empty system_prompt returns empty string without calling service."""
		profile = MagicMock()
		profile.system_prompt = ""
		result = presenter.render_system_prompt(profile, None, None)
		assert result == ""

	def test_plain_text_unchanged(self, presenter):
		"""Plain text (no Mako) passes through unchanged."""
		profile = MagicMock()
		profile.system_prompt = "You are helpful."
		result = presenter.render_system_prompt(profile, None, None)
		assert result == "You are helpful."

	def test_mako_variable_rendered(self, presenter):
		"""Mako ${now} variable is substituted."""
		profile = MagicMock()
		profile.system_prompt = "Date: ${now.year}"
		result = presenter.render_system_prompt(profile, None, None)
		assert str(datetime.now().year) in result

	def test_invalid_template_falls_back(self, presenter):
		"""Invalid template logs warning and returns original string."""
		profile = MagicMock()
		profile.system_prompt = "${unclosed"
		result = presenter.render_system_prompt(profile, None, None)
		assert result == "${unclosed"
