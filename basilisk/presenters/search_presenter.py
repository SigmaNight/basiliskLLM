"""Presenter for SearchDialog.

Extracts state and search logic from SearchDialog, leaving the view
responsible only for widget management.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

from basilisk.services.search_service import (
	SearchDirection,
	SearchMode,
	SearchService,
	adjust_utf16_position,
)

if TYPE_CHECKING:
	from basilisk.views.search_dialog import SearchDialog

log = logging.getLogger(__name__)


class SearchTargetAdapter:
	"""Adapter that exposes a wx.TextCtrl as a search target.

	Wraps a wx.TextCtrl (or compatible) to provide a plain Python
	interface usable by SearchPresenter without importing wx.
	"""

	def __init__(self, ctrl) -> None:
		"""Initialise the adapter.

		Args:
			ctrl: A wx.TextCtrl or compatible widget.
		"""
		self._ctrl = ctrl

	def get_text(self) -> str:
		"""Return the full text content of the control.

		Returns:
			The text content.
		"""
		return self._ctrl.GetValue()

	def get_insertion_point(self) -> int:
		"""Return the current cursor position.

		Returns:
			The current insertion point.
		"""
		return self._ctrl.GetInsertionPoint()

	def set_selection(self, start: int, end: int) -> None:
		"""Select the given range and focus the control.

		Args:
			start: Start position of the selection.
			end: End position of the selection.
		"""
		self._ctrl.SetSelection(start, end)
		self._ctrl.SetFocus()


class SearchPresenter:
	"""Presenter for SearchDialog.

	Owns search state and business logic; delegates all widget access to
	the view.

	Attributes:
		view: The SearchDialog view instance (may be None until wired).
		target: The SearchTargetAdapter wrapping the searched TextCtrl.
		search_list: History of search strings.
		search_direction: Current search direction.
		search_mode: Current search mode.
		case_sensitive: Whether search is case-sensitive.
		search_dot_all: Whether '.' matches all characters.
	"""

	def __init__(
		self,
		view: SearchDialog | None,
		target: SearchTargetAdapter,
		initial_search_list: list[str] | None = None,
	) -> None:
		"""Initialise the presenter.

		Args:
			view: The SearchDialog (may be set later via assignment).
			target: Adapter wrapping the text control being searched.
			initial_search_list: Pre-populated search history.
		"""
		self.view = view
		self.target = target
		self.search_list: list[str] = list(initial_search_list or [])
		self._search_direction = SearchDirection.FORWARD
		self._search_mode = SearchMode.PLAIN_TEXT
		self._case_sensitive = False
		self._search_dot_all = False

	# ------------------------------------------------------------------
	# Properties
	# ------------------------------------------------------------------

	@property
	def search_direction(self) -> SearchDirection:
		"""Get the current search direction.

		Returns:
			The current search direction.
		"""
		return self._search_direction

	@search_direction.setter
	def search_direction(self, value: SearchDirection) -> None:
		"""Set the search direction and sync the view.

		Args:
			value: The new search direction.
		"""
		self._search_direction = value
		if self.view is not None:
			self.view.apply_direction(value)

	@property
	def search_mode(self) -> SearchMode:
		"""Get the current search mode.

		Returns:
			The current search mode.
		"""
		return self._search_mode

	@search_mode.setter
	def search_mode(self, value: SearchMode) -> None:
		"""Set the search mode.

		Args:
			value: The new search mode.
		"""
		self._search_mode = value

	@property
	def case_sensitive(self) -> bool:
		"""Get whether search is case-sensitive.

		Returns:
			True if case-sensitive.
		"""
		return self._case_sensitive

	@case_sensitive.setter
	def case_sensitive(self, value: bool) -> None:
		"""Set whether search is case-sensitive.

		Args:
			value: True for case-sensitive search.
		"""
		self._case_sensitive = value

	@property
	def search_dot_all(self) -> bool:
		"""Get whether '.' matches all characters.

		Returns:
			True if dot-all mode is enabled.
		"""
		return self._search_dot_all

	@search_dot_all.setter
	def search_dot_all(self, value: bool) -> None:
		"""Set whether '.' matches all characters.

		Args:
			value: True to enable dot-all mode.
		"""
		self._search_dot_all = value

	# ------------------------------------------------------------------
	# Public interface
	# ------------------------------------------------------------------

	def on_find(self) -> None:
		"""Execute a search using the current view state.

		Reads widget values from the view, validates the input, updates
		history, calls SearchService, and navigates to the nearest match.
		Notifies the view when no match is found.
		"""
		search_text = self.view.get_search_text()
		if not search_text:
			self.view.show_error(
				# Translators: Search dialog error message
				_("Please enter text to search for.")
			)
			return

		if search_text not in self.search_list:
			self.search_list.append(search_text)
		self.view.sync_history(self.search_list, search_text)

		self._sync_state_from_view()
		self.view.dismiss_modal()

		text = self.target.get_text()
		matches = self._find_matches(text, search_text)
		if matches is None:
			return
		self._navigate_to_match(text, matches, search_text)

	def _sync_state_from_view(self) -> None:
		"""Snapshot current widget values into presenter state."""
		self._case_sensitive = self.view.get_case_sensitive()
		self._search_dot_all = self.view.get_dot_all()
		self._search_direction = self.view.get_direction()
		self._search_mode = self.view.get_mode()

	def _find_matches(
		self, text: str, search_text: str
	) -> list[re.Match] | None:
		"""Run the search and return all matches, or None on regex error.

		Args:
			text: The full text to search within.
			search_text: The raw pattern entered by the user.

		Returns:
			A (possibly empty) list of matches, or None if the pattern
			is an invalid regular expression.
		"""
		try:
			return SearchService.find_all_matches(
				text,
				search_text,
				self._search_mode,
				self._case_sensitive,
				self._search_dot_all,
			)
		except re.error as e:
			self.view.show_error(
				# Translators: Error shown when the user enters an invalid regular expression
				_("Invalid regular expression: %s") % e
			)
			return None

	def _navigate_to_match(
		self, text: str, matches: list[re.Match], search_text: str
	) -> None:
		"""Select the nearest match to the cursor, or report not found.

		Args:
			text: The full text that was searched.
			matches: All matches returned by the search service.
			search_text: The raw pattern, used for the not-found message.
		"""
		if not matches:
			self.view.show_not_found(search_text)
			return

		cursor_pos = self.target.get_insertion_point()
		cursor_pos = adjust_utf16_position(text, cursor_pos, reverse=True)
		match_positions = [(m.start(), m.end()) for m in matches]

		if self._search_direction == SearchDirection.FORWARD:
			for start, end in match_positions:
				adj_start = adjust_utf16_position(text, start)
				adj_end = adjust_utf16_position(text, end)
				if adj_start > cursor_pos:
					self.target.set_selection(adj_start, adj_end)
					return
		else:
			cursor_pos += 1
			for start, end in reversed(match_positions):
				adj_start = adjust_utf16_position(text, start)
				adj_end = adjust_utf16_position(text, end)
				if adj_end < cursor_pos:
					self.target.set_selection(adj_start, adj_end)
					return

		self.view.show_not_found(search_text)

	def on_mode_changed(self, mode: SearchMode) -> None:
		"""Handle search mode change.

		Updates internal state and tells the view to toggle dot-all
		visibility.

		Args:
			mode: The newly selected search mode.
		"""
		self._search_mode = mode
		if self.view is not None:
			self.view.update_dot_all_visible(mode == SearchMode.REGEX)

	def search_next(self) -> None:
		"""Search for the next occurrence (forward direction)."""
		self.search_direction = SearchDirection.FORWARD
		self.on_find()

	def search_previous(self) -> None:
		"""Search for the previous occurrence (backward direction)."""
		self.search_direction = SearchDirection.BACKWARD
		self.on_find()
