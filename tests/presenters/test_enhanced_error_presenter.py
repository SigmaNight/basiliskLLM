"""Tests for EnhancedErrorPresenter business logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.enhanced_error_presenter import EnhancedErrorPresenter


@pytest.fixture
def mock_view():
	"""Provide a mock view for EnhancedErrorPresenter tests."""
	return MagicMock()


@pytest.fixture
def presenter(mock_view):
	"""Provide an EnhancedErrorPresenter with a mock view."""
	return EnhancedErrorPresenter(mock_view)


class TestFindUrlsInText:
	"""Tests for the find_urls_in_text static method."""

	@pytest.mark.parametrize(
		("text", "expected"),
		[
			("Visit http://example.com for details.", ["http://example.com"]),
			(
				"See https://docs.example.com/page for more.",
				["https://docs.example.com/page"],
			),
			(
				"See http://a.com and https://b.org for info.",
				["http://a.com", "https://b.org"],
			),
			("This message has no links.", []),
			("ftp://old-style.com and www.nodomain.com", []),
			(
				"Error: see https://help.example.com/error-123",
				["https://help.example.com/error-123"],
			),
		],
		ids=["http", "https", "multiple", "none", "non-url", "no-punct"],
	)
	def test_find_urls(self, text, expected):
		"""find_urls_in_text correctly extracts URLs from various text inputs."""
		assert EnhancedErrorPresenter.find_urls_in_text(text) == expected


class TestCopyToClipboard:
	"""Tests for the copy_to_clipboard method."""

	def test_successful_copy_updates_view(self, presenter, mock_view, mocker):
		"""On success, calls set_copy_state with 'Copied!' and disabled."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = True

		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
			mock_clipboard,
		)
		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
			MagicMock(),
		)
		presenter.copy_to_clipboard("test message")

		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert "Copied" in label
		assert enabled is False

	def test_clipboard_open_fails_rings_bell(
		self, presenter, mock_view, mocker
	):
		"""When clipboard cannot be opened, rings bell and updates state."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = False

		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
			mock_clipboard,
		)
		presenter.copy_to_clipboard("test message")

		mock_view.bell.assert_called_once()
		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert enabled is False

	def test_setdata_failure_raises_and_updates_view(
		self, presenter, mock_view, mocker
	):
		"""When SetData returns False, bell is rung and state is updated."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = False

		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
			mock_clipboard,
		)
		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
			MagicMock(),
		)
		presenter.copy_to_clipboard("test message")

		mock_view.bell.assert_called_once()
		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert enabled is False

	def test_clipboard_closes_on_success(self, presenter, mock_view, mocker):
		"""Clipboard is closed after a successful copy."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = True

		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
			mock_clipboard,
		)
		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
			MagicMock(),
		)
		presenter.copy_to_clipboard("test message")

		mock_clipboard.Close.assert_called_once()


class TestOpenUrl:
	"""Tests for the open_url method."""

	def test_calls_webbrowser_open(self, presenter, mock_view, mocker):
		"""Calls webbrowser.open with the given URL."""
		mock_open = mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open"
		)
		presenter.open_url("https://example.com")
		mock_open.assert_called_once_with("https://example.com")

	def test_no_view_update_on_success(self, presenter, mock_view, mocker):
		"""Does not call any view methods on successful open."""
		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open"
		)
		presenter.open_url("https://example.com")

		mock_view.bell.assert_not_called()
		mock_view.set_open_url_state.assert_not_called()

	def test_open_failure_rings_bell_and_updates_state(
		self, presenter, mock_view, mocker
	):
		"""On browser open failure, rings bell and updates open-URL state."""
		mocker.patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open",
			side_effect=OSError("no browser"),
		)
		presenter.open_url("https://example.com")

		mock_view.bell.assert_called_once()
		mock_view.set_open_url_state.assert_called_once()
		(label,) = mock_view.set_open_url_state.call_args[0]
		assert "failed" in label.lower()
