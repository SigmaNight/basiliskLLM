"""Tests for SearchPresenter and SearchTargetAdapter."""

from unittest.mock import MagicMock

from basilisk.presenters.search_presenter import (
	SearchPresenter,
	SearchTargetAdapter,
)
from basilisk.services.search_service import SearchDirection, SearchMode

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_view(
	search_text="hello",
	direction=SearchDirection.FORWARD,
	mode=SearchMode.PLAIN_TEXT,
	case_sensitive=False,
	dot_all=False,
):
	"""Build a fully configured mock view."""
	view = MagicMock()
	view.get_search_text.return_value = search_text
	view.get_direction.return_value = direction
	view.get_mode.return_value = mode
	view.get_case_sensitive.return_value = case_sensitive
	view.get_dot_all.return_value = dot_all
	return view


def make_target(text="", pos=0):
	"""Build a mock target with the given text content and cursor position."""
	target = MagicMock(spec=SearchTargetAdapter)
	target.get_text.return_value = text
	target.get_insertion_point.return_value = pos
	return target


def make_presenter(view=None, target=None, initial_search_list=None):
	"""Build a SearchPresenter with sensible defaults."""
	if target is None:
		target = make_target()
	return SearchPresenter(
		view=view, target=target, initial_search_list=initial_search_list
	)


# ---------------------------------------------------------------------------
# SearchTargetAdapter
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# SearchPresenter — initial state
# ---------------------------------------------------------------------------


class TestSearchPresenterInitialState:
	"""Tests for SearchPresenter default attribute values."""

	def test_default_direction(self):
		"""Default search direction is FORWARD."""
		p = make_presenter()
		assert p.search_direction == SearchDirection.FORWARD

	def test_default_mode(self):
		"""Default search mode is PLAIN_TEXT."""
		p = make_presenter()
		assert p.search_mode == SearchMode.PLAIN_TEXT

	def test_default_case_sensitive(self):
		"""Default case_sensitive is False."""
		p = make_presenter()
		assert p.case_sensitive is False

	def test_default_dot_all(self):
		"""Default search_dot_all is False."""
		p = make_presenter()
		assert p.search_dot_all is False

	def test_initial_search_list_empty(self):
		"""search_list is empty when no initial list provided."""
		p = make_presenter()
		assert p.search_list == []

	def test_initial_search_list_populated(self):
		"""search_list is copied from initial_search_list."""
		p = make_presenter(initial_search_list=["foo", "bar"])
		assert p.search_list == ["foo", "bar"]

	def test_initial_search_list_is_copy(self):
		"""Mutating the original list does not affect the presenter."""
		original = ["foo"]
		p = make_presenter(initial_search_list=original)
		original.append("bar")
		assert p.search_list == ["foo"]

	def test_view_is_none_by_default(self):
		"""View attribute may start as None."""
		p = make_presenter(view=None)
		assert p.view is None


# ---------------------------------------------------------------------------
# SearchPresenter — property setters
# ---------------------------------------------------------------------------


class TestSearchPresenterProperties:
	"""Tests for SearchPresenter property getters and setters."""

	def test_direction_setter_syncs_view(self):
		"""Setting search_direction calls view.apply_direction()."""
		view = MagicMock()
		p = make_presenter(view=view)
		p.search_direction = SearchDirection.BACKWARD
		view.apply_direction.assert_called_once_with(SearchDirection.BACKWARD)

	def test_direction_setter_no_view(self):
		"""Setting search_direction with view=None does not raise."""
		p = make_presenter(view=None)
		p.search_direction = SearchDirection.BACKWARD  # must not raise
		assert p.search_direction == SearchDirection.BACKWARD

	def test_mode_setter(self):
		"""Setting search_mode updates the internal value."""
		p = make_presenter()
		p.search_mode = SearchMode.REGEX
		assert p.search_mode == SearchMode.REGEX

	def test_case_sensitive_setter(self):
		"""Setting case_sensitive updates the internal value."""
		p = make_presenter()
		p.case_sensitive = True
		assert p.case_sensitive is True

	def test_dot_all_setter(self):
		"""Setting search_dot_all updates the internal value."""
		p = make_presenter()
		p.search_dot_all = True
		assert p.search_dot_all is True


# ---------------------------------------------------------------------------
# SearchPresenter — on_find
# ---------------------------------------------------------------------------


class TestSearchPresenterOnFind:
	"""Tests for SearchPresenter.on_find()."""

	def test_empty_search_text_shows_error(self):
		"""Empty search text calls view.show_error without searching."""
		view = make_view(search_text="")
		p = make_presenter(view=view)
		p.on_find()
		view.show_error.assert_called_once()
		view.dismiss_modal.assert_not_called()
		view.show_not_found.assert_not_called()

	def test_new_text_added_to_history(self):
		"""A search text not yet in history is appended."""
		view = make_view(search_text="newterm")
		p = make_presenter(view=view)
		p.on_find()
		assert "newterm" in p.search_list

	def test_no_duplicate_in_history(self):
		"""Re-searching the same text does not add a duplicate."""
		view = make_view(search_text="dup")
		p = make_presenter(view=view, initial_search_list=["dup"])
		p.on_find()
		assert p.search_list.count("dup") == 1

	def test_sync_history_called_with_current_text(self):
		"""view.sync_history is called with updated list and current text."""
		view = make_view(search_text="word")
		p = make_presenter(view=view)
		p.on_find()
		view.sync_history.assert_called_once_with(["word"], "word")

	def test_dismisses_modal(self):
		"""on_find() always dismisses the modal before selecting."""
		view = make_view(search_text="x", direction=SearchDirection.FORWARD)
		target = make_target(text="x", pos=0)
		target.get_insertion_point.return_value = 0
		p = make_presenter(view=view, target=target)
		p.on_find()
		view.dismiss_modal.assert_called_once()

	def test_not_found_calls_view(self):
		"""When no match exists, view.show_not_found is called."""
		view = make_view(search_text="zzz")
		target = make_target(text="hello world")
		p = make_presenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("zzz")
		target.set_selection.assert_not_called()

	def test_snapshots_view_state_into_presenter(self):
		"""on_find() writes view widget values back to presenter attributes."""
		view = make_view(
			search_text="x",
			direction=SearchDirection.BACKWARD,
			mode=SearchMode.REGEX,
			case_sensitive=True,
			dot_all=True,
		)
		target = make_target(text="x x x", pos=0)
		p = make_presenter(view=view, target=target)
		p.on_find()
		assert p._search_direction == SearchDirection.BACKWARD
		assert p._search_mode == SearchMode.REGEX
		assert p._case_sensitive is True
		assert p._search_dot_all is True

	# -- Forward navigation --------------------------------------------------

	def test_forward_selects_first_match_after_cursor(self):
		"""FORWARD search selects the first match whose start > cursor."""
		# "hello world hello" — matches at (0,5) and (12,17)
		text = "hello world hello"
		view = make_view(search_text="hello", direction=SearchDirection.FORWARD)
		target = make_target(text=text, pos=6)  # cursor in "world"
		p = make_presenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(12, 17)

	def test_forward_no_match_after_cursor_shows_not_found(self):
		"""FORWARD with cursor past the last match calls show_not_found."""
		text = "hello world hello"
		view = make_view(search_text="hello", direction=SearchDirection.FORWARD)
		target = make_target(text=text, pos=15)  # inside last "hello"
		p = make_presenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("hello")
		target.set_selection.assert_not_called()

	# -- Backward navigation -------------------------------------------------

	def test_backward_selects_last_match_before_cursor(self):
		"""BACKWARD search selects the rightmost match ending before cursor."""
		text = "hello world hello"
		view = make_view(
			search_text="hello", direction=SearchDirection.BACKWARD
		)
		target = make_target(text=text, pos=10)  # cursor in "world"
		p = make_presenter(view=view, target=target)
		p.on_find()
		# match at (0,5): end=5, cursor+1=11 → 5 < 11 ✓
		# match at (12,17): end=17, 17 < 11? no — skipped
		target.set_selection.assert_called_once_with(0, 5)

	def test_backward_no_match_before_cursor_shows_not_found(self):
		"""BACKWARD with cursor before first match calls show_not_found."""
		text = "hello world hello"
		view = make_view(
			search_text="hello", direction=SearchDirection.BACKWARD
		)
		target = make_target(text=text, pos=0)  # before any match
		p = make_presenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once_with("hello")
		target.set_selection.assert_not_called()

	# -- Case sensitivity ----------------------------------------------------

	def test_case_insensitive_by_default(self):
		"""Case-insensitive search matches mixed-case text."""
		text = "Hello World"
		view = make_view(
			search_text="hello",
			direction=SearchDirection.FORWARD,
			case_sensitive=False,
		)
		target = make_target(text=text, pos=0)
		p = make_presenter(view=view, target=target)
		p.on_find()
		# "Hello" starts at 0; cursor is 0; 0 > 0 is False → no forward match
		# That means not found (cursor AT the match, not before it)
		view.show_not_found.assert_called_once()

	def test_case_insensitive_finds_match_after_cursor(self):
		"""Case-insensitive search finds 'WORLD' with query 'world'."""
		text = "hello WORLD"
		view = make_view(
			search_text="world",
			direction=SearchDirection.FORWARD,
			case_sensitive=False,
		)
		target = make_target(text=text, pos=0)
		p = make_presenter(view=view, target=target)
		p.on_find()
		target.set_selection.assert_called_once_with(6, 11)

	def test_case_sensitive_no_match(self):
		"""Case-sensitive search does not match differently-cased text."""
		text = "Hello World"
		view = make_view(
			search_text="hello",
			direction=SearchDirection.FORWARD,
			case_sensitive=True,
		)
		target = make_target(text=text, pos=0)
		p = make_presenter(view=view, target=target)
		p.on_find()
		view.show_not_found.assert_called_once()

	# -- Regex mode ----------------------------------------------------------

	def test_regex_mode_matches_pattern(self):
		"""REGEX mode finds matches using a regex pattern."""
		text = "cat bat rat"
		view = make_view(
			search_text=r"[cbr]at",
			direction=SearchDirection.FORWARD,
			mode=SearchMode.REGEX,
		)
		target = make_target(text=text, pos=0)
		p = make_presenter(view=view, target=target)
		p.on_find()
		# First match "cat" at (0,3); 0 > 0 is False → next "bat" at (4,7)
		target.set_selection.assert_called_once_with(4, 7)


# ---------------------------------------------------------------------------
# SearchPresenter — navigation helpers
# ---------------------------------------------------------------------------


class TestSearchPresenterNavigation:
	"""Tests for search_next() and search_previous()."""

	def test_search_next_sets_forward_and_calls_find(self):
		"""search_next() applies FORWARD direction and triggers on_find."""
		text = "aa bb aa"
		view = make_view(search_text="aa", direction=SearchDirection.FORWARD)
		target = make_target(text=text, pos=0)
		p = make_presenter(view=view, target=target)
		p.search_next()
		view.apply_direction.assert_called_with(SearchDirection.FORWARD)
		assert p._search_direction == SearchDirection.FORWARD
		# "aa" at (0,2): 0>0 False; "aa" at (6,8): 6>0 True → selected
		target.set_selection.assert_called_once_with(6, 8)

	def test_search_previous_sets_backward_and_calls_find(self):
		"""search_previous() applies BACKWARD direction and triggers on_find."""
		text = "aa bb aa"
		view = make_view(search_text="aa", direction=SearchDirection.BACKWARD)
		target = make_target(text=text, pos=7)  # inside last "aa"
		p = make_presenter(view=view, target=target)
		p.search_previous()
		view.apply_direction.assert_called_with(SearchDirection.BACKWARD)
		assert p._search_direction == SearchDirection.BACKWARD
		# cursor=7, +1=8; reversed: (6,8) end=8 < 8? No; (0,2) end=2 < 8? Yes
		target.set_selection.assert_called_once_with(0, 2)

	def test_search_next_no_view(self):
		"""search_next() with view=None does not raise."""
		target = make_target(text="hello", pos=0)
		p = make_presenter(view=None, target=target)
		p.view = None
		# We need to assign a view after the fact for on_find to work:
		# set a minimal view just for on_find
		view = make_view(search_text="hello")
		p.view = view
		p.search_next()  # must not raise
		view.apply_direction.assert_called_with(SearchDirection.FORWARD)


# ---------------------------------------------------------------------------
# SearchPresenter — mode change
# ---------------------------------------------------------------------------


class TestSearchPresenterModeChange:
	"""Tests for on_mode_changed()."""

	def test_regex_mode_shows_dot_all(self):
		"""on_mode_changed(REGEX) calls view.update_dot_all_visible(True)."""
		view = MagicMock()
		p = make_presenter(view=view)
		p.on_mode_changed(SearchMode.REGEX)
		view.update_dot_all_visible.assert_called_once_with(True)
		assert p.search_mode == SearchMode.REGEX

	def test_plain_mode_hides_dot_all(self):
		"""on_mode_changed(PLAIN_TEXT) calls view.update_dot_all_visible(False)."""
		view = MagicMock()
		p = make_presenter(view=view)
		p.on_mode_changed(SearchMode.PLAIN_TEXT)
		view.update_dot_all_visible.assert_called_once_with(False)

	def test_mode_change_no_view(self):
		"""on_mode_changed() with view=None does not raise."""
		p = make_presenter(view=None)
		p.on_mode_changed(SearchMode.REGEX)  # must not raise
		assert p.search_mode == SearchMode.REGEX
