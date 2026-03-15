"""Accessible wrappers for screen-reader support.

Provides wx.Accessible subclasses that implement GetDescription
(accDescription) so screen readers announce help text when controls
receive focus.
"""

from __future__ import annotations

import wx


class AccessibleWithHelp(wx.Accessible):
	"""Accessible wrapper providing name and help text for screen readers."""

	def __init__(
		self,
		win: wx.Window | None = None,
		name: str | None = None,
		help_text: str | None = None,
	):
		"""Initialize with optional window, name, and help text for accessibility."""
		super().__init__(win)
		self._name = name
		self._help_text = help_text

	def GetName(self, childId: int) -> tuple[int, str]:
		"""Return name for screen readers when childId is 0."""
		if self._name and childId == 0:
			return (wx.ACC_OK, self._name)
		return super().GetName(childId)

	def GetHelpText(self, childId: int) -> tuple[int, str]:
		"""Return help text for screen readers when childId is 0."""
		if self._help_text and childId == 0:
			return (wx.ACC_OK, self._help_text)
		return super().GetHelpText(childId)

	def GetDescription(self, childId: int) -> tuple[int, str]:
		"""Get description for screen readers (uses accDescription, not accHelp)."""
		if self._help_text and childId == 0:
			return (wx.ACC_OK, self._help_text)
		return super().GetDescription(childId)
