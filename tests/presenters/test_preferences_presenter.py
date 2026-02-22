"""Tests for PreferencesPresenter."""

import sys
from unittest.mock import MagicMock, patch

import pytest

from basilisk.presenters.preferences_presenter import PreferencesPresenter


def _make_presenter(mock_locales=None):
	"""Build a PreferencesPresenter with mocked dependencies.

	Args:
		mock_locales: List of locale mocks to return from get_supported_locales.

	Returns:
		A tuple of (presenter, mock_conf) for assertions.
	"""
	if mock_locales is None:
		mock_locales = []
	mock_conf = MagicMock()
	view = MagicMock()
	with (
		patch(
			"basilisk.presenters.preferences_presenter.config"
		) as mock_config,
		patch(
			"basilisk.presenters.preferences_presenter.get_supported_locales",
			return_value=mock_locales,
		),
		patch("basilisk.presenters.preferences_presenter.get_app_locale"),
	):
		mock_config.conf.return_value = mock_conf
		presenter = PreferencesPresenter(view)
	return presenter, mock_conf


class TestBuildLanguages:
	"""Tests for PreferencesPresenter._build_languages."""

	def test_auto_is_first_key(self):
		"""The first language key must be 'auto'."""
		presenter, _ = _make_presenter()

		keys = list(presenter.languages.keys())

		assert keys[0] == "auto"

	def test_adds_supported_locales(self):
		"""Supported locales should be added after 'auto'."""
		mock_locale = MagicMock()
		mock_locale.__str__ = MagicMock(return_value="fr_FR")
		mock_locale.get_display_name.return_value = "french"

		presenter, _ = _make_presenter(mock_locales=[mock_locale])

		assert "fr_FR" in presenter.languages
		assert len(presenter.languages) == 2

	def test_auto_label_is_translated(self):
		"""The 'auto' entry should use the translatable system default label."""
		presenter, _ = _make_presenter()

		# builtins._ is a passthrough in tests
		assert presenter.languages["auto"] == "System default (auto)"


@pytest.fixture
def mock_view():
	"""Return a mock view with all required widget accessors."""
	view = MagicMock()
	view.log_level.GetSelection.return_value = 0
	view.language.GetSelection.return_value = 0
	view.release_channel.GetSelection.return_value = 0
	view.auto_update_mode.GetSelection.return_value = 0
	view.quit_on_close.GetValue.return_value = True
	view.advanced_mode.GetValue.return_value = False
	view.role_label_user.GetValue.return_value = "You"
	view.role_label_assistant.GetValue.return_value = "AI"
	view.nav_msg_select.GetValue.return_value = True
	view.shift_enter_mode.GetValue.return_value = False
	view.use_accessible_output.GetValue.return_value = False
	view.focus_history_checkbox.GetValue.return_value = False
	view.auto_save_to_db.GetValue.return_value = True
	view.auto_save_draft.GetValue.return_value = False
	view.reopen_last_conversation.GetValue.return_value = False
	view.image_resize.GetValue.return_value = True
	view.image_max_height.GetValue.return_value = 800
	view.image_max_width.GetValue.return_value = 1200
	view.image_quality.GetValue.return_value = 85
	view.use_system_cert_store.GetValue.return_value = False
	view.server_enable.GetValue.return_value = False
	view.server_port.GetValue.return_value = "8080"
	return view


class TestOnOk:
	"""Tests for PreferencesPresenter.on_ok."""

	def test_saves_config_and_closes(self, mock_view):
		"""on_ok should save config and call EndModal(wx.ID_OK)."""
		mock_conf = MagicMock()
		mock_wx = MagicMock()
		with (
			patch(
				"basilisk.presenters.preferences_presenter.config"
			) as mock_config,
			patch(
				"basilisk.presenters.preferences_presenter.get_supported_locales",
				return_value=[],
			),
			patch("basilisk.presenters.preferences_presenter.get_app_locale"),
			patch("basilisk.presenters.preferences_presenter.set_log_level"),
			patch.dict(sys.modules, {"wx": mock_wx}),
		):
			mock_config.conf.return_value = mock_conf
			presenter = PreferencesPresenter(mock_view)
			presenter.on_ok()

		mock_conf.save.assert_called_once()
		mock_view.EndModal.assert_called_once_with(mock_wx.ID_OK)

	def test_server_port_cast_to_int(self, mock_view):
		"""on_ok should cast server_port value to int."""
		mock_conf = MagicMock()
		mock_wx = MagicMock()
		mock_view.server_port.GetValue.return_value = "9090"
		with (
			patch(
				"basilisk.presenters.preferences_presenter.config"
			) as mock_config,
			patch(
				"basilisk.presenters.preferences_presenter.get_supported_locales",
				return_value=[],
			),
			patch("basilisk.presenters.preferences_presenter.get_app_locale"),
			patch("basilisk.presenters.preferences_presenter.set_log_level"),
			patch.dict(sys.modules, {"wx": mock_wx}),
		):
			mock_config.conf.return_value = mock_conf
			presenter = PreferencesPresenter(mock_view)
			presenter.on_ok()

		assert mock_conf.server.port == 9090

	def test_calls_set_log_level(self, mock_view):
		"""on_ok should call set_log_level with the log level name."""
		mock_conf = MagicMock()
		mock_wx = MagicMock()
		with (
			patch(
				"basilisk.presenters.preferences_presenter.config"
			) as mock_config,
			patch(
				"basilisk.presenters.preferences_presenter.get_supported_locales",
				return_value=[],
			),
			patch("basilisk.presenters.preferences_presenter.get_app_locale"),
			patch(
				"basilisk.presenters.preferences_presenter.set_log_level"
			) as mock_set_log,
			patch.dict(sys.modules, {"wx": mock_wx}),
		):
			mock_config.conf.return_value = mock_conf
			presenter = PreferencesPresenter(mock_view)
			presenter.on_ok()

		mock_set_log.assert_called_once_with(mock_conf.general.log_level.name)
