"""Tests for SearchPresenter and SearchTargetAdapter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.search_presenter import (
	SearchPresenter,
	SearchTargetAdapter,
)
from basilisk.services.search_service import SearchDirection, SearchMode


def _make_view(
	search_text="hello",
	direction=SearchDirection.FORWARD,
	mode=SearchMode.PLAIN_TEXT,
	case_sensitive=False,
	dot_all=False,
):
	"""Build a fully configured mock view.

	Args:
		search_text: Text to search for.
		direction: Search direction (FORWARD or BACKWARD).
		mode: Search mode (PLAIN_TEXT, EXTENDED, or REGEX).
		case_sensitive: Whether search is case-sensitive.
		dot_all: Whether dot matches newline in REGEX mode.
	"""
	view = MagicMock()
	view.get_search_text.return_value = search_text
	view.get_direction.return_value = direction
	view.get_mode.return_value = mode
	view.get_case_sensitive.return_value = case_sensitive
	view.get_dot_all.return_value = dot_all
	return view


def _make_target(text="", pos=0):
	"""Build a mock target with the given text content and cursor position.

	Args:
		text: Full text content of the target control.
		pos: Cursor insertion point.
	"""
	target = MagicMock(spec=SearchTargetAdapter)
	target.get_text.return_value = text
	target.get_insertion_point.return_value = pos
	return target


@pytest.fixture
def mock_view():
	"""Build a mock view with sensible defaults."""
	return _make_view()


@pytest.fixture
def mock_target():
	"""Build a mock target with empty text and cursor at 0."""
	return _make_target()


@pytest.fixture
def presenter(mock_target):
	"""Build a SearchPresenter with no view and default target."""
	return SearchPresenter(view=None, target=mock_target)


class TestSearchTargetAdapter:
	"""Tests for SearchTargetAdapter."""

	def test_get_text_delegates(self):
		"""get_text() returns the ctrl's GetValue()."""
		ctrl = MagicMock()
		ctrl.GetValue.return_value = "content"
		assert SearchTargetAdapter(ctrl).get_text() == "content"

	def test_get_insertion_point_delegates(self):
		"""get_insertion_point() returns the ctrl's GetInsertionPoint()."""
		ctrl = MagicMock()
		ctrl.GetInsertionPoint.return_value = 7
		assert SearchTargetAdapter(ctrl).get_insertion_point() == 7

	def test_set_selection_selects_and_focuses(self):
		"""set_selection() calls SetSelection then SetFocus."""
		ctrl = MagicMock()
		SearchTargetAdapter(ctrl).set_selection(3, 9)
		ctrl.SetSelection.assert_called_once_with(3, 9)
		ctrl.SetFocus.assert_called_once()


class TestSearchPresenterInitialState:
	"""Tests for SearchPresenter default attribute values."""

	def test_default_direction(self, presenter):
		"""Default search direction is FORWARD."""
		assert presenter.search_direction == SearchDirection.FORWARD

	def test_default_mode(self, presenter):
		"""Default search mode is PLAIN_TEXT."""
		assert presenter.search_mode == SearchMode.PLAIN_TEXT

	def test_default_case_sensitive(self, presenter):
		"""Default case_sensitive is False."""
		assert presenter.case_sensitive is False

	def test_default_dot_all(self, presenter):
		"""Default search_dot_all is False."""
		assert presenter.search_dot_all is False

	def test_initial_search_list_empty(self, presenter):
		"""search_list is empty when no initial list provided."""
		assert presenter.search_list == []

	def test_initial_search_list_populated(self, mock_target):
		"""search_list is copied from initial_search_list."""
		p = SearchPresenter(
			view=None, target=mock_target, initial_search_list=["foo", "bar"]
		)
		assert p.search_list == ["foo", "bar"]

	def test_initial_search_list_is_copy(self, mock_target):
		"""Mutating the original list does not affect the presenter."""
		original = ["foo"]
		p = SearchPresenter(
			view=None, target=mock_target, initial_search_list=original
		)
		original.append("bar")
		assert p.search_list == ["foo"]

	def test_view_is_none_by_default(self, presenter):
		"""View attribute may start as None."""
		assert presenter.view is None


class TestSearchPresenterProperties:
	"""Tests for SearchPresenter property getters and setters."""

	def test_direction_setter_syncs_view(self, mock_target):
		"""Setting search_direction calls view.apply_direction()."""
		view = MagicMock()
		p = SearchPresenter(view=view, target=mock_target)
		p.search_direction = SearchDirection.BACKWARD
		view.apply_direction.assert_called_once_with(SearchDirection.BACKWARD)

	def test_direction_setter_no_view(self, presenter):
		"""Setting search_direction with view=None does not raise."""
		presenter.search_direction = SearchDirection.BACKWARD  # must not raise
		assert presenter.search_direction == SearchDirection.BACKWARD

	def test_mode_setter(self, presenter):
		"""Setting search_mode updates the internal value."""
		presenter.search_mode = SearchMode.REGEX
		assert presenter.search_mode == SearchMode.REGEX

	def test_case_sensitive_setter(self, presenter):
		"""Setting case_sensitive updates the internal value."""
		presenter.case_sensitive = True
		assert presenter.case_sensitive is True

	def test_dot_all_setter(self, presenter):
		"""Setting search_dot_all updates the internal value."""
		presenter.search_dot_all = True
		assert presenter.search_dot_all is True


class TestSearchPresenterOnFind:
	"""Tests for SearchPresenter.on_find()."""

	def test_empty_search_text_shows_error(self):
		"""Empty search text calls view.show_error without searching."""
		view = _make_view(search_text="")
		p = SearchPresenter(view=view, target=_make_target())
		p.on_find()
		view.show_error.assert_called_once()
		view.dismiss_modal.assert_not_called()
		view.show_not_found.assert_not_called()

	def test_new_text_added_to_history(self):
		"""A search text not yet in history is appended."""
		view = _make_view(search_text="newterm")
		p = SearchPresenter(view=view, target=_make_target())
		p.on_find()
		assert "newterm" in p.search_list

	def test_no_duplicate_in_history(self):
		"""Re-searching the same text does not add a duplicate."""
		view = _make_view(search_text="dup")
		p = SearchPresenter(
			view=view, target=_make_target(), initial_search_list=["dup"]
		)
		p.on_find()
		assert p.search_list.count("dup") == 1

	def test_sync_history_called_with_current_text(self):
		"""view.sync_history is called with updated list and current text."""
		view = _make_view(search_text="word")
		p = SearchPresenter(view=view, target=_make_target())
		p.on_find()
		view.sync_history.assert_called_once_with(["word"], "word")

	def test_dismisses_modal(self):
		"""on_find() always dismisses the modal before selecting."""
		view = _make_view(search_text="x", direction=SearchDirection.FORWARD)
		target = _make_target(text="x", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.dismiss_modal.assert_called_once()

	def test_not_found_calls_view(self):
		"""When no match exists, view.show_not_found is called."""
		view = _make_view(search_text="zzz")
		target = _make_target(text="hello world")
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("zzz")
		target.set_selection.assert_not_called()

	def test_snapshots_view_state_into_presenter(self):
		"""on_find() writes view widget values back to presenter attributes."""
		view = _make_view(
			search_text="x",
			direction=SearchDirection.BACKWARD,
			mode=SearchMode.REGEX,
			case_sensitive=True,
			dot_all=True,
		)
		target = _make_target(text="x x x", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		assert p._search_direction == SearchDirection.BACKWARD
		assert p._search_mode == SearchMode.REGEX
		assert p._case_sensitive is True
		assert p._search_dot_all is True

	def test_forward_selects_first_match_after_cursor(self):
		"""FORWARD search selects the first match whose start > cursor."""
		text = "hello world hello"
		view = _make_view(
			search_text="hello", direction=SearchDirection.FORWARD
		)
		target = _make_target(text=text, pos=6)  # cursor in "world"
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(12, 17)

	def test_forward_no_match_after_cursor_shows_not_found(self):
		"""FORWARD with cursor past the last match calls show_not_found."""
		text = "hello world hello"
		view = _make_view(
			search_text="hello", direction=SearchDirection.FORWARD
		)
		target = _make_target(text=text, pos=15)  # inside last "hello"
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("hello")
		target.set_selection.assert_not_called()

	def test_backward_selects_last_match_before_cursor(self):
		"""BACKWARD search selects the rightmost match ending before cursor."""
		text = "hello world hello"
		view = _make_view(
			search_text="hello", direction=SearchDirection.BACKWARD
		)
		target = _make_target(text=text, pos=10)  # cursor in "world"
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(0, 5)

	def test_backward_no_match_before_cursor_shows_not_found(self):
		"""BACKWARD with cursor before first match calls show_not_found."""
		text = "hello world hello"
		view = _make_view(
			search_text="hello", direction=SearchDirection.BACKWARD
		)
		target = _make_target(text=text, pos=0)  # before any match
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("hello")
		target.set_selection.assert_not_called()

	def test_case_insensitive_by_default(self):
		"""Case-insensitive search matches mixed-case text."""
		text = "Hello World"
		view = _make_view(
			search_text="hello",
			direction=SearchDirection.FORWARD,
			case_sensitive=False,
		)
		target = _make_target(text=text, pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once()

	def test_case_insensitive_finds_match_after_cursor(self):
		"""Case-insensitive search finds 'WORLD' with query 'world'."""
		text = "hello WORLD"
		view = _make_view(
			search_text="world",
			direction=SearchDirection.FORWARD,
			case_sensitive=False,
		)
		target = _make_target(text=text, pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(6, 11)

	def test_case_sensitive_no_match(self):
		"""Case-sensitive search does not match differently-cased text."""
		text = "Hello World"
		view = _make_view(
			search_text="hello",
			direction=SearchDirection.FORWARD,
			case_sensitive=True,
		)
		target = _make_target(text=text, pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once()

	def test_regex_mode_matches_pattern(self):
		"""REGEX mode finds matches using a regex pattern."""
		text = "cat bat rat"
		view = _make_view(
			search_text=r"[cbr]at",
			direction=SearchDirection.FORWARD,
			mode=SearchMode.REGEX,
		)
		target = _make_target(text=text, pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(4, 7)


class TestSearchPresenterNavigation:
	"""Tests for search_next() and search_previous()."""

	def test_search_next_sets_forward_and_calls_find(self):
		"""search_next() applies FORWARD direction and triggers on_find."""
		text = "aa bb aa"
		view = _make_view(search_text="aa", direction=SearchDirection.FORWARD)
		target = _make_target(text=text, pos=0)
		p = SearchPresenter(view=view, target=target)
		p.search_next()
		view.apply_direction.assert_called_with(SearchDirection.FORWARD)
		assert p._search_direction == SearchDirection.FORWARD
		target.set_selection.assert_called_once_with(6, 8)

	def test_search_previous_sets_backward_and_calls_find(self):
		"""search_previous() applies BACKWARD direction and triggers on_find."""
		text = "aa bb aa"
		view = _make_view(search_text="aa", direction=SearchDirection.BACKWARD)
		target = _make_target(text=text, pos=7)  # inside last "aa"
		p = SearchPresenter(view=view, target=target)
		p.search_previous()
		view.apply_direction.assert_called_with(SearchDirection.BACKWARD)
		assert p._search_direction == SearchDirection.BACKWARD
		target.set_selection.assert_called_once_with(0, 2)

	def test_search_next_no_view(self):
		"""search_next() with view=None does not raise."""
		target = _make_target(text="hello", pos=0)
		p = SearchPresenter(view=None, target=target)
		view = _make_view(search_text="hello")
		p.view = view
		p.search_next()  # must not raise
		view.apply_direction.assert_called_with(SearchDirection.FORWARD)


class TestSearchPresenterModeChange:
	"""Tests for on_mode_changed()."""

	def test_regex_mode_shows_dot_all(self, presenter):
		"""on_mode_changed(REGEX) calls view.update_dot_all_visible(True)."""
		view = MagicMock()
		presenter.view = view
		presenter.on_mode_changed(SearchMode.REGEX)
		view.update_dot_all_visible.assert_called_once_with(True)
		assert presenter.search_mode == SearchMode.REGEX

	def test_plain_mode_hides_dot_all(self, presenter):
		"""on_mode_changed(PLAIN_TEXT) calls view.update_dot_all_visible(False)."""
		view = MagicMock()
		presenter.view = view
		presenter.on_mode_changed(SearchMode.PLAIN_TEXT)
		view.update_dot_all_visible.assert_called_once_with(False)

	def test_mode_change_no_view(self, presenter):
		"""on_mode_changed() with view=None does not raise."""
		presenter.on_mode_changed(SearchMode.REGEX)  # must not raise
		assert presenter.search_mode == SearchMode.REGEX


class TestSearchPresenterInvalidRegex:
	"""Tests for re.error handling in on_find()."""

	def test_invalid_regex_calls_show_error(self):
		"""on_find() calls view.show_error for an invalid regex pattern."""
		view = _make_view(search_text="[invalid", mode=SearchMode.REGEX)
		target = _make_target(text="some text", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_error.assert_called_once()
		error_msg = view.show_error.call_args[0][0]
		assert (
			"invalid" in error_msg.lower() or "expression" in error_msg.lower()
		)

	def test_invalid_regex_does_not_select(self):
		"""on_find() does not call set_selection when regex is invalid."""
		view = _make_view(search_text="(?P<", mode=SearchMode.REGEX)
		target = _make_target(text="some text", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_not_called()

	def test_invalid_regex_does_not_show_not_found(self):
		"""on_find() does not call show_not_found when regex is invalid."""
		view = _make_view(search_text="*bad", mode=SearchMode.REGEX)
		target = _make_target(text="some text", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_not_called()

	def test_valid_regex_is_not_affected(self):
		"""on_find() works normally for a valid regex pattern."""
		view = _make_view(search_text=r"\d+", mode=SearchMode.REGEX)
		target = _make_target(text="price: 42 items", pos=0)
		p = SearchPresenter(view=view, target=target)
		p.on_find()
		view.show_error.assert_not_called()
		target.set_selection.assert_called_once()
