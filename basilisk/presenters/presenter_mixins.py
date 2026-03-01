"""Reusable mixins and decorators shared across presenters.

Provides:
- ``_guard_destroying``: decorator that makes a presenter callback a no-op
  while the view is being destroyed.
- ``DestroyGuardMixin``: exposes ``_guard_destroying`` on presenter classes.
- ``ManagerCrudMixin``: common add/edit/remove/save pattern for presenters
  that manage a list-based manager with persistence.
"""

from __future__ import annotations

import functools
from typing import Callable


def _guard_destroying(method: Callable) -> Callable:
	"""Decorator: no-op if ``self.view._is_destroying`` is True.

	Apply to presenter callbacks that must not run after the view
	has started its teardown sequence.

	Args:
		method: The presenter callback to protect.

	Returns:
		A wrapped callable that returns None immediately when destroying.
	"""

	@functools.wraps(method)
	def wrapper(self, *args, **kwargs):
		if self.view._is_destroying:
			return
		return method(self, *args, **kwargs)

	return wrapper


class DestroyGuardMixin:
	"""Mixin that exposes ``_guard_destroying`` to presenter subclasses.

	Inherit this mixin and decorate callbacks with
	``@DestroyGuardMixin._guard_destroying`` (or the module-level
	``_guard_destroying``) to skip execution after the view is torn down.
	"""

	_guard_destroying = staticmethod(_guard_destroying)


class ManagerCrudMixin:
	"""Mixin for presenters managing a list-based manager with persistence.

	Subclasses must expose a ``manager`` property returning the backing
	manager object.  The manager must support:

	- ``manager.add(item)``
	- ``manager[index] = item``
	- ``manager[index]`` (read)
	- ``manager.remove(item)``
	- ``manager.save()``

	Call ``_init_crud()`` in ``__init__`` if ``menu_update`` bookkeeping
	is required.  When ``menu_update`` is not set, the flag logic is
	silently skipped.
	"""

	def _init_crud(self) -> None:
		"""Initialize the ``menu_update`` flag to False."""
		self.menu_update: bool = False

	def _before_edit(self, index: int, item) -> None:
		"""Hook called before replacing an item.  Override for side effects.

		Args:
			index: Position of the item to be replaced.
			item: The new item value.
		"""

	def _before_remove(self, index: int, item) -> None:
		"""Hook called before removing an item.  Override for side effects.

		Args:
			index: Position of the item to be removed.
			item: The item about to be removed.
		"""

	def add_item(self, item) -> None:
		"""Add an item, persist, and mark menu as needing update.

		Args:
			item: The item to add.
		"""
		self.manager.add(item)
		self.manager.save()
		if hasattr(self, "menu_update"):
			self.menu_update = True

	def edit_item(self, index: int, item) -> None:
		"""Replace the item at *index*, persist, and mark menu for update.

		Calls ``_before_edit`` before replacing.

		Args:
			index: Position of the item to replace.
			item: The replacement item.
		"""
		self._before_edit(index, item)
		self.manager[index] = item
		self.manager.save()
		if hasattr(self, "menu_update"):
			self.menu_update = True

	def remove_item(self, item) -> None:
		"""Remove *item* directly, persist, and mark menu for update.

		Args:
			item: The item to remove.
		"""
		self.manager.remove(item)
		self.manager.save()
		if hasattr(self, "menu_update"):
			self.menu_update = True

	def remove_item_by_index(self, index: int) -> None:
		"""Look up item by *index*, then remove it, persist, and mark menu.

		Calls ``_before_remove`` before removing.

		Args:
			index: Position of the item to remove.
		"""
		item = self.manager[index]
		self._before_remove(index, item)
		self.manager.remove(item)
		self.manager.save()
		if hasattr(self, "menu_update"):
			self.menu_update = True
