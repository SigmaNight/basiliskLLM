"""Tests for conversation profile presenters."""

from unittest.mock import MagicMock

import pytest

from basilisk.config import ConversationProfile
from basilisk.presenters.conversation_profile_presenter import (
	ConversationProfilePresenter,
	EditConversationProfilePresenter,
)


class TestEditConversationProfilePresenter:
	"""Tests for EditConversationProfilePresenter."""

	@pytest.fixture
	def mock_view(self):
		"""Return a mock view with required widget accessors."""
		view = MagicMock()
		view.profile_name_txt.GetValue.return_value = "Test Profile"
		view.system_prompt_txt.GetValue.return_value = "Be helpful"
		view.include_account_checkbox.GetValue.return_value = True
		view.current_account = MagicMock()
		view.current_account.provider.id = "openai"
		view.current_model = MagicMock()
		view.current_model.id = "gpt-4"
		view.current_model.default_temperature = 1.0
		view.max_tokens_spin_ctrl.GetValue.return_value = 100
		view.temperature_spinner.GetValue.return_value = 0.7
		view.top_p_spinner.GetValue.return_value = 0.9
		view.stream_mode.GetValue.return_value = True
		return view

	def test_validate_returns_none_on_empty_name(self, mock_view):
		"""Empty profile name should return None."""
		mock_view.profile_name_txt.GetValue.return_value = ""
		presenter = EditConversationProfilePresenter(view=mock_view)
		result = presenter.validate_and_build_profile()
		assert result is None

	def test_validate_builds_new_profile(self, mock_view):
		"""Valid inputs should build and return a profile."""
		mock_view.include_account_checkbox.GetValue.return_value = False
		presenter = EditConversationProfilePresenter(view=mock_view)
		result = presenter.validate_and_build_profile()
		assert result is not None
		assert result.name == "Test Profile"
		assert result.system_prompt == "Be helpful"
		assert result.stream_mode is True

	def test_validate_updates_existing_profile(self, mock_view):
		"""Editing an existing profile should update it in place."""
		mock_view.include_account_checkbox.GetValue.return_value = False
		existing = ConversationProfile(name="Old Name")
		presenter = EditConversationProfilePresenter(
			view=mock_view, profile=existing
		)
		result = presenter.validate_and_build_profile()
		assert result is existing
		assert result.name == "Test Profile"

	def test_validate_clears_model_params_when_no_model(self, mock_view):
		"""No model selected should clear model-dependent params."""
		mock_view.current_account = None
		mock_view.current_model = None
		mock_view.include_account_checkbox.GetValue.return_value = False
		presenter = EditConversationProfilePresenter(view=mock_view)
		result = presenter.validate_and_build_profile()
		assert result is not None
		assert result.ai_model_info is None
		assert result.max_tokens is None
		assert result.temperature is None
		assert result.top_p is None

	def test_validate_excludes_account_when_unchecked(self, mock_view):
		"""Unchecked include_account should not include account."""
		mock_view.include_account_checkbox.GetValue.return_value = False
		presenter = EditConversationProfilePresenter(view=mock_view)
		result = presenter.validate_and_build_profile()
		assert result is not None
		assert result.account_info is None


class TestConversationProfilePresenter:
	"""Tests for ConversationProfilePresenter."""

	@pytest.fixture
	def mock_profiles(self):
		"""Return a mock ConversationProfileManager."""
		return MagicMock()

	@pytest.fixture
	def presenter(self, mock_profiles):
		"""Return a presenter with mock dependencies."""
		view = MagicMock()
		return ConversationProfilePresenter(view=view, profiles=mock_profiles)

	def test_add_profile(self, presenter, mock_profiles):
		"""Adding a profile should save and set menu_update."""
		profile = MagicMock()
		presenter.add_profile(profile)
		mock_profiles.add.assert_called_once_with(profile)
		mock_profiles.save.assert_called_once()
		assert presenter.menu_update is True

	def test_edit_profile(self, presenter, mock_profiles):
		"""Editing a profile should replace at index and save."""
		profile = MagicMock()
		presenter.edit_profile(2, profile)
		mock_profiles.__setitem__.assert_called_once_with(2, profile)
		mock_profiles.save.assert_called_once()
		assert presenter.menu_update is True

	def test_remove_profile(self, presenter, mock_profiles):
		"""Removing a profile should remove and save."""
		profile = MagicMock()
		presenter.remove_profile(profile)
		mock_profiles.remove.assert_called_once_with(profile)
		mock_profiles.save.assert_called_once()
		assert presenter.menu_update is True

	def test_set_default(self, presenter, mock_profiles):
		"""Setting default should delegate to profiles and save."""
		profile = MagicMock()
		presenter.set_default(profile)
		mock_profiles.set_default_profile.assert_called_once_with(profile)
		mock_profiles.save.assert_called_once()

	def test_menu_update_initially_false(self, mock_profiles):
		"""menu_update should be False initially."""
		view = MagicMock()
		p = ConversationProfilePresenter(view=view, profiles=mock_profiles)
		assert p.menu_update is False
