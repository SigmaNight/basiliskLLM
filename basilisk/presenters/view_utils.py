"""Shared view utilities for conversation presenters.

Helpers to avoid duplication across ConversationPresenter, EditBlockPresenter, etc.
"""

from __future__ import annotations

from typing import Any


def view_has_web_search_control(view: Any) -> bool:
	"""Return True if view has web search checkbox and it is shown.

	Args:
		view: View with optional web_search_mode widget.

	Returns:
		True when web search control exists and is visible.
	"""
	return hasattr(view, "web_search_mode") and view.web_search_mode.IsShown()


def view_get_web_search_value(view: Any) -> bool:
	"""Get web search checkbox value. Returns False if control absent or hidden.

	Args:
		view: View with optional web_search_mode widget.

	Returns:
		True when web search is enabled, else False.
	"""
	if not view_has_web_search_control(view):
		return False
	return view.web_search_mode.GetValue()
