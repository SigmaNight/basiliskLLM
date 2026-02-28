"""Tests for presenter_mixins: DestroyGuardMixin and ManagerCrudMixin."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.presenter_mixins import (
	DestroyGuardMixin,
	ManagerCrudMixin,
	_guard_destroying,
)

# ---------------------------------------------------------------------------
# _guard_destroying decorator
# ---------------------------------------------------------------------------


class TestGuardDestroyingDecorator:
	"""Tests for the _guard_destroying standalone decorator."""

	def _make_presenter(self, is_destroying: bool):
		"""Build a minimal presenter-like object with the guard applied.

		Args:
			is_destroying: Value to set on the view's _is_destroying flag.

		Returns:
			The presenter instance.
		"""

		class FakePresenter:
			def __init__(self, destroying):
				self.view = MagicMock()
				self.view._is_destroying = destroying
				self.called = False

			@_guard_destroying
			def callback(self):
				self.called = True
				return "result"

		return FakePresenter(is_destroying)

	def test_runs_when_not_destroying(self):
		"""Callback executes normally when view is not destroying."""
		p = self._make_presenter(False)
		result = p.callback()
		assert p.called is True
		assert result == "result"

	def test_returns_none_when_destroying(self):
		"""Callback returns None immediately when view is destroying."""
		p = self._make_presenter(True)
		result = p.callback()
		assert p.called is False
		assert result is None

	def test_preserves_function_name(self):
		"""Decorated function keeps its original __name__."""

		class P:
			view = MagicMock()
			view._is_destroying = False

			@_guard_destroying
			def my_callback(self):
				"""Docstring."""

		assert P.my_callback.__name__ == "my_callback"

	def test_with_args(self):
		"""Callback receives positional and keyword arguments unchanged."""
		received = {}

		class P:
			view = MagicMock()
			view._is_destroying = False

			@_guard_destroying
			def callback(self, x, y=0):
				received["x"] = x
				received["y"] = y

		P().callback(1, y=2)
		assert received == {"x": 1, "y": 2}


# ---------------------------------------------------------------------------
# DestroyGuardMixin
# ---------------------------------------------------------------------------


class TestDestroyGuardMixin:
	"""Tests for DestroyGuardMixin."""

	def test_mixin_guard_is_same_function(self):
		"""DestroyGuardMixin._guard_destroying is the module-level decorator."""
		assert DestroyGuardMixin._guard_destroying is _guard_destroying

	def test_subclass_can_use_guard(self):
		"""Presenter subclass can decorate callbacks via the mixin attribute."""

		class MyPresenter(DestroyGuardMixin):
			def __init__(self, destroying):
				self.view = MagicMock()
				self.view._is_destroying = destroying
				self.called = False

			@DestroyGuardMixin._guard_destroying
			def on_event(self):
				self.called = True

		p_alive = MyPresenter(False)
		p_alive.on_event()
		assert p_alive.called is True

		p_dead = MyPresenter(True)
		p_dead.on_event()
		assert p_dead.called is False


# ---------------------------------------------------------------------------
# ManagerCrudMixin
# ---------------------------------------------------------------------------


class TestManagerCrudMixin:
	"""Tests for ManagerCrudMixin add/edit/remove operations."""

	@pytest.fixture
	def mock_manager(self):
		"""Return a mock manager supporting add/remove/save/__setitem__/__getitem__.

		Returns:
			A MagicMock manager.
		"""
		manager = MagicMock()
		manager.__getitem__ = MagicMock(return_value=MagicMock())
		return manager

	@pytest.fixture
	def presenter_with_menu(self, mock_manager):
		"""Return a ManagerCrudMixin subclass with menu_update initialised.

		Args:
			mock_manager: The mock manager fixture.

		Returns:
			The presenter instance.
		"""

		class P(ManagerCrudMixin):
			"""Test presenter with menu_update."""

			@property
			def manager(self):
				return mock_manager

		p = P()
		p._init_crud()
		return p

	@pytest.fixture
	def presenter_no_menu(self, mock_manager):
		"""Return a ManagerCrudMixin subclass without menu_update.

		Args:
			mock_manager: The mock manager fixture.

		Returns:
			The presenter instance.
		"""

		class P(ManagerCrudMixin):
			"""Test presenter without menu_update."""

			@property
			def manager(self):
				return mock_manager

		return P()

	# -- add_item --

	def test_add_item_calls_add_and_save(
		self, presenter_with_menu, mock_manager
	):
		"""add_item should call manager.add() then manager.save()."""
		item = MagicMock()
		presenter_with_menu.add_item(item)
		mock_manager.add.assert_called_once_with(item)
		mock_manager.save.assert_called_once()

	def test_add_item_sets_menu_update(self, presenter_with_menu):
		"""add_item should set menu_update to True."""
		presenter_with_menu.add_item(MagicMock())
		assert presenter_with_menu.menu_update is True

	def test_add_item_no_menu_update_attr(self, presenter_no_menu):
		"""add_item without menu_update attribute should not raise."""
		presenter_no_menu.add_item(MagicMock())
		assert not hasattr(presenter_no_menu, "menu_update")

	# -- edit_item --

	def test_edit_item_calls_setitem_and_save(
		self, presenter_with_menu, mock_manager
	):
		"""edit_item should replace item at index and save."""
		item = MagicMock()
		presenter_with_menu.edit_item(2, item)
		mock_manager.__setitem__.assert_called_once_with(2, item)
		mock_manager.save.assert_called_once()

	def test_edit_item_calls_before_edit_hook(self, mock_manager):
		"""edit_item should call _before_edit before replacing."""
		hook_args = []

		class P(ManagerCrudMixin):
			"""Test presenter with _before_edit hook."""

			@property
			def manager(self):
				return mock_manager

			def _before_edit(self, index, item):
				hook_args.append((index, item))

		p = P()
		item = MagicMock()
		p.edit_item(5, item)
		assert hook_args == [(5, item)]

	def test_edit_item_sets_menu_update(self, presenter_with_menu):
		"""edit_item should set menu_update to True."""
		presenter_with_menu.edit_item(0, MagicMock())
		assert presenter_with_menu.menu_update is True

	# -- remove_item --

	def test_remove_item_calls_remove_and_save(
		self, presenter_with_menu, mock_manager
	):
		"""remove_item should call manager.remove() and save."""
		item = MagicMock()
		presenter_with_menu.remove_item(item)
		mock_manager.remove.assert_called_once_with(item)
		mock_manager.save.assert_called_once()

	def test_remove_item_sets_menu_update(self, presenter_with_menu):
		"""remove_item should set menu_update to True."""
		presenter_with_menu.remove_item(MagicMock())
		assert presenter_with_menu.menu_update is True

	# -- remove_item_by_index --

	def test_remove_item_by_index_looks_up_and_removes(
		self, presenter_with_menu, mock_manager
	):
		"""remove_item_by_index should fetch item by index and remove it."""
		sentinel = MagicMock()
		mock_manager.__getitem__ = MagicMock(return_value=sentinel)
		presenter_with_menu.remove_item_by_index(3)
		mock_manager.__getitem__.assert_called_once_with(3)
		mock_manager.remove.assert_called_once_with(sentinel)
		mock_manager.save.assert_called_once()

	def test_remove_item_by_index_calls_before_remove_hook(self, mock_manager):
		"""remove_item_by_index should call _before_remove before removing."""
		hook_args = []
		sentinel = MagicMock()
		mock_manager.__getitem__ = MagicMock(return_value=sentinel)

		class P(ManagerCrudMixin):
			"""Test presenter with _before_remove hook."""

			@property
			def manager(self):
				return mock_manager

			def _before_remove(self, index, item):
				hook_args.append((index, item))

		p = P()
		p.remove_item_by_index(7)
		assert hook_args == [(7, sentinel)]

	def test_remove_item_by_index_sets_menu_update(
		self, presenter_with_menu, mock_manager
	):
		"""remove_item_by_index should set menu_update to True."""
		presenter_with_menu.remove_item_by_index(0)
		assert presenter_with_menu.menu_update is True

	def test_remove_item_by_index_no_menu_attr(
		self, presenter_no_menu, mock_manager
	):
		"""remove_item_by_index without menu_update should not raise."""
		presenter_no_menu.remove_item_by_index(0)
		assert not hasattr(presenter_no_menu, "menu_update")

	# -- _init_crud --

	def test_init_crud_sets_menu_update_false(self):
		"""_init_crud should initialise menu_update to False."""

		class P(ManagerCrudMixin):
			"""Test presenter."""

			manager = MagicMock()

		p = P()
		p._init_crud()
		assert p.menu_update is False
