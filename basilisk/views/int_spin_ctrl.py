"""Integer spin control with screen-reader accessibility.

Uses FloatSpin internally (digits=0, increment=1) so we can set
accessible on the inner text control, unlike wx.SpinCtrl which
does not expose its inner edit for accessibility.
"""

from __future__ import annotations

import wx
from wx.lib.agw.floatspin import FloatSpin

from .accessible import AccessibleWithHelp


class IntSpinCtrl(FloatSpin):
	"""Integer spin control with accessibility support.

	SpinCtrl-compatible API (GetValue -> int, SetValue(int), SetMin, SetMax)
	built on FloatSpin so the inner text control can receive accessible
	help text for screen readers.
	"""

	def __init__(
		self,
		parent: wx.Window,
		value: int = 0,
		min_val: int = 0,
		max_val: int = 100,
		name: str = "IntSpinCtrl",
		help_text: str | None = None,
		label: str | None = None,
		**kwargs,
	):
		"""Create an integer spin control with accessibility.

		Args:
			parent: Parent window
			value: Initial value
			min_val: Minimum value
			max_val: Maximum value
			name: Control name
			help_text: Description for screen readers (accDescription)
			label: Accessible name (e.g. from associated label)
			**kwargs: Passed to FloatSpin (e.g. id, pos, size)
		"""
		super().__init__(
			parent,
			value=float(value),
			min_val=float(min_val),
			max_val=float(max_val),
			increment=1.0,
			digits=0,
			name=name,
			**kwargs,
		)
		acc_name = (label or "").replace("&", "")
		self._textctrl.SetAccessible(
			AccessibleWithHelp(
				win=self._textctrl, name=acc_name or None, help_text=help_text
			)
		)

	def GetValue(self) -> int:
		"""Return the value as an integer."""
		return int(super().GetValue())

	def SetValue(self, value: int | float) -> None:
		"""Set the value. Accepts int or float."""
		super().SetValue(float(value))

	def SetMin(self, min_val: int) -> None:
		"""Set minimum value."""
		super().SetMin(float(min_val))

	def SetMax(self, max_val: int) -> None:
		"""Set maximum value."""
		super().SetMax(float(max_val))
