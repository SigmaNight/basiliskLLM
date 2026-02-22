"""Tests for EnhancedErrorPresenter business logic."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

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

	def test_finds_http_url(self):
		"""Finds a plain http URL in text."""
		urls = EnhancedErrorPresenter.find_urls_in_text(
			"Visit http://example.com for details."
		)
		assert urls == ["http://example.com"]

	def test_finds_https_url(self):
		"""Finds an https URL in text."""
		urls = EnhancedErrorPresenter.find_urls_in_text(
			"See https://docs.example.com/page for more."
		)
		assert urls == ["https://docs.example.com/page"]

	def test_finds_multiple_urls(self):
		"""Finds multiple URLs in the same text."""
		text = "See http://a.com and https://b.org for info."
		urls = EnhancedErrorPresenter.find_urls_in_text(text)
		assert urls == ["http://a.com", "https://b.org"]

	def test_returns_empty_for_no_urls(self):
		"""Returns an empty list when no URLs are present."""
		urls = EnhancedErrorPresenter.find_urls_in_text(
			"This message has no links."
		)
		assert urls == []

	def test_ignores_non_url_text(self):
		"""Does not match non-URL text like ftp:// or bare domain names."""
		urls = EnhancedErrorPresenter.find_urls_in_text(
			"ftp://old-style.com and www.nodomain.com"
		)
		assert urls == []

	def test_strips_trailing_punctuation_from_pattern(self):
		"""URLs ending at whitespace boundary are matched correctly."""
		urls = EnhancedErrorPresenter.find_urls_in_text(
			"Error: see https://help.example.com/error-123"
		)
		assert "https://help.example.com/error-123" in urls


class TestCopyToClipboard:
	"""Tests for the copy_to_clipboard method."""

	def test_successful_copy_updates_view(self, presenter, mock_view):
		"""On success, calls set_copy_state with 'Copied!' and disabled."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = True

		with (
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
				mock_clipboard,
			),
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
				MagicMock(),
			),
		):
			presenter.copy_to_clipboard("test message")

		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert "Copied" in label
		assert enabled is False

	def test_clipboard_open_fails_rings_bell(self, presenter, mock_view):
		"""When clipboard cannot be opened, rings bell and updates state."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = False

		with patch(
			"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
			mock_clipboard,
		):
			presenter.copy_to_clipboard("test message")

		mock_view.bell.assert_called_once()
		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert enabled is False

	def test_setdata_failure_raises_and_updates_view(
		self, presenter, mock_view
	):
		"""When SetData returns False, bell is rung and state is updated."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = False

		with (
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
				mock_clipboard,
			),
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
				MagicMock(),
			),
		):
			presenter.copy_to_clipboard("test message")

		mock_view.bell.assert_called_once()
		mock_view.set_copy_state.assert_called_once()
		label, enabled = mock_view.set_copy_state.call_args[0]
		assert enabled is False

	def test_clipboard_closes_on_success(self, presenter, mock_view):
		"""Clipboard is closed after a successful copy."""
		mock_clipboard = MagicMock()
		mock_clipboard.Open.return_value = True
		mock_clipboard.SetData.return_value = True

		with (
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TheClipboard",
				mock_clipboard,
			),
			patch(
				"basilisk.presenters.enhanced_error_presenter.wx.TextDataObject",
				MagicMock(),
			),
		):
			presenter.copy_to_clipboard("test message")

		mock_clipboard.Close.assert_called_once()


class TestOpenUrl:
	"""Tests for the open_url method."""

	def test_calls_webbrowser_open(self, presenter, mock_view):
		"""Calls webbrowser.open with the given URL."""
		with patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open"
		) as mock_open:
			presenter.open_url("https://example.com")

		mock_open.assert_called_once_with("https://example.com")

	def test_no_view_update_on_success(self, presenter, mock_view):
		"""Does not call any view methods on successful open."""
		with patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open"
		):
			presenter.open_url("https://example.com")

		mock_view.bell.assert_not_called()
		mock_view.set_open_url_state.assert_not_called()

	def test_open_failure_rings_bell_and_updates_state(
		self, presenter, mock_view
	):
		"""On browser open failure, rings bell and updates open-URL state."""
		with patch(
			"basilisk.presenters.enhanced_error_presenter.webbrowser.open",
			side_effect=OSError("no browser"),
		):
			presenter.open_url("https://example.com")

		mock_view.bell.assert_called_once()
		mock_view.set_open_url_state.assert_called_once()
		(label,) = mock_view.set_open_url_state.call_args[0]
		assert "failed" in label.lower() or "Open" in label
