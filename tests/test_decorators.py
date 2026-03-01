"""Tests for basilisk/decorators.py."""

from unittest.mock import MagicMock

from basilisk.decorators import require_list_selection


class TestRequireListSelection:
	"""Tests for the require_list_selection decorator."""

	def _make_list_ctrl_view(self, selection: int):
		"""Build a fake view with a ListCtrl-style widget (GetFirstSelected).

		Args:
			selection: The index that GetFirstSelected() returns.

		Returns:
			The fake view instance.
		"""

		class FakeView:
			"""Fake view with a ListCtrl widget."""

			def __init__(self, sel):
				self.widget = MagicMock()
				self.widget.GetFirstSelected.return_value = sel
				self.widget.spec = ["GetFirstSelected"]
				# ensure hasattr check works
				self.widget.GetFirstSelected = MagicMock(return_value=sel)
				self.called = False

			@require_list_selection("widget")
			def on_action(self, event=None):
				self.called = True
				return "ok"

		return FakeView(selection)

	def _make_combo_view(self, selection: int):
		"""Build a fake view with a ComboBox-style widget (GetSelection only).

		Args:
			selection: The index that GetSelection() returns.

		Returns:
			The fake view instance.
		"""

		class FakeView:
			"""Fake view with a ComboBox widget."""

			def __init__(self, sel):
				self.combo = MagicMock(spec=["GetSelection"])
				self.combo.GetSelection = MagicMock(return_value=sel)
				self.called = False

			@require_list_selection("combo")
			def on_action(self, event=None):
				self.called = True
				return "ok"

		return FakeView(selection)

	def test_listctrl_valid_selection_passes(self):
		"""Handler runs when GetFirstSelected() returns a non-negative index."""
		view = self._make_list_ctrl_view(0)
		result = view.on_action()
		assert view.called is True
		assert result == "ok"

	def test_listctrl_no_selection_blocks(self):
		"""Handler is skipped when GetFirstSelected() returns -1."""
		import wx

		view = self._make_list_ctrl_view(wx.NOT_FOUND)
		result = view.on_action()
		assert view.called is False
		assert result is None

	def test_combo_valid_selection_passes(self):
		"""Handler runs when GetSelection() returns a non-negative index."""
		view = self._make_combo_view(2)
		result = view.on_action()
		assert view.called is True
		assert result == "ok"

	def test_combo_no_selection_blocks(self):
		"""Handler is skipped when GetSelection() returns wx.NOT_FOUND."""
		import wx

		view = self._make_combo_view(wx.NOT_FOUND)
		result = view.on_action()
		assert view.called is False
		assert result is None

	def test_preserves_function_metadata(self):
		"""Decorated function keeps its original __name__ and __doc__."""

		class V:
			"""Fake view."""

			widget = MagicMock()
			widget.GetFirstSelected = MagicMock(return_value=0)

			@require_list_selection("widget")
			def on_special(self):
				"""Do something special."""

		assert V.on_special.__name__ == "on_special"
		assert "special" in V.on_special.__doc__

	def test_event_arg_forwarded(self):
		"""Event argument is forwarded to the wrapped handler."""
		received = {}

		class V:
			"""Fake view."""

			widget = MagicMock()
			widget.GetFirstSelected = MagicMock(return_value=1)

			@require_list_selection("widget")
			def on_action(self, event=None):
				received["event"] = event

		sentinel = object()
		V().on_action(sentinel)
		assert received["event"] is sentinel

	def test_negative_one_same_as_not_found(self):
		"""Index -1 is the same as wx.NOT_FOUND and blocks execution."""
		import wx

		assert wx.NOT_FOUND == -1  # sanity check
		view = self._make_list_ctrl_view(-1)
		result = view.on_action()
		assert view.called is False
		assert result is None
