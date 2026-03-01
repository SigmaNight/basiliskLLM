"""Shared fixtures for presenter tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def base_mock_view():
	"""Minimal view mock: _is_destroying + error display + accessible output."""
	view = MagicMock()
	view._is_destroying = False
	return view


@pytest.fixture
def mock_account():
	"""Mock account with provider.id and provider.engine_cls."""
	account = MagicMock()
	account.provider.id = "openai"
	account.provider.engine_cls.capabilities = set()
	return account


@pytest.fixture
def mock_model():
	"""Mock AI model."""
	model = MagicMock()
	model.id = "gpt-4"
	model.default_temperature = 1.0
	return model


@pytest.fixture
def mock_engine():
	"""Mock provider engine with empty capabilities."""
	engine = MagicMock()
	engine.capabilities = set()
	return engine


@pytest.fixture
def conversation_view_base():
	"""Mock view with widgets shared by ConversationTab and EditBlockDialog."""
	view = MagicMock()
	view._is_destroying = False
	view.prompt_panel.prompt_text = ""
	view.prompt_panel.attachment_files = []
	view.prompt_panel.check_attachments_valid.return_value = True
	view.system_prompt_txt.GetValue.return_value = ""
	view.temperature_spinner.GetValue.return_value = 0.5
	view.top_p_spinner.GetValue.return_value = 1.0
	view.max_tokens_spin_ctrl.GetValue.return_value = 100
	view.stream_mode.GetValue.return_value = True
	view.current_account.provider.id = "openai"
	view.current_account.provider.engine_cls.capabilities = set()
	view.current_model.id = "gpt-4"
	view.current_engine.capabilities = set()
	return view
