"""Base class for properties dialogs with section navigation (Page Up/Down)."""

from __future__ import annotations

from datetime import datetime

import wx
import wx.stc


def format_datetime(dt: datetime) -> str:
	"""Format datetime for display (consistent across properties dialogs)."""
	return dt.strftime("%Y-%m-%d %H:%M")


def section_header(title: str) -> list[str]:
	"""Return [title, underline] with underline length matching title."""
	return [title, "-" * len(title)]


class SectionedPropertiesDialog(wx.Dialog):
	"""Base dialog for read-only properties with section navigation.

	Subclasses provide (text, section_line_indices). Page Up/Down scroll between
	sections; Tab moves focus to/from the close button; Escape closes the dialog.
	Context menu: Previous/Next section, Copy all.
	"""

	def __init__(
		self,
		parent: wx.Window,
		title: str,
		text: str,
		sections: list[int],
		size: tuple[int, int] = (550, 450),
	):
		"""Initialize the dialog.

		Args:
			parent: Parent window.
			title: Dialog title.
			text: Read-only content to display.
			sections: Line indices of section headers for Page Up/Down navigation.
			size: Dialog size.
		"""
		super().__init__(
			parent,
			title=title,
			size=size,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._sections = sections

		self._text_ctrl = wx.stc.StyledTextCtrl(self, style=wx.BORDER_NONE)
		self._text_ctrl.SetValue(text)
		self._text_ctrl.SetEditable(False)
		self._text_ctrl.SetWrapMode(wx.stc.STC_WRAP_WORD)
		self._text_ctrl.SetMarginWidth(0, 0)
		self._text_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
		self._text_ctrl.Bind(wx.EVT_CONTEXT_MENU, self._on_context_menu)

		# EVT_CHAR_HOOK: fired before any other key events, propagates upward to parent.
		# By not calling Skip() we prevent wxEVT_KEY_DOWN from being generated, so the
		# STC never receives Page Up/Down and won't scroll (per wx.KeyEvent docs).
		self.Bind(wx.EVT_CHAR_HOOK, self._on_char_hook)

		# Accelerator for Copy all
		self._copy_all_id = wx.NewId()
		self.Bind(
			wx.EVT_MENU,
			lambda e: self._copy_all_to_clipboard(),
			id=self._copy_all_id,
		)
		self.SetAcceleratorTable(
			wx.AcceleratorTable(
				[(wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("C"), self._copy_all_id)]
			)
		)

		vbox = wx.BoxSizer(wx.VERTICAL)
		vbox.Add(
			self._text_ctrl, proportion=1, flag=wx.EXPAND | wx.ALL, border=10
		)
		self._close_btn = wx.Button(self, id=wx.ID_CLOSE)
		self._close_btn.Bind(wx.EVT_BUTTON, lambda _: self.Close())
		self._close_btn.Bind(wx.EVT_KEY_DOWN, self._on_key_down)
		vbox.Add(
			self._close_btn,
			proportion=0,
			flag=wx.ALIGN_CENTER | wx.ALL,
			border=10,
		)
		self.SetSizer(vbox)

	def _section_at_cursor(self) -> tuple[int, int]:
		"""Return (section_index, current_line) for cursor position."""
		current_line = self._text_ctrl.LineFromPosition(
			self._text_ctrl.GetCurrentPos()
		)
		idx = 0
		for i, line in enumerate(self._sections):
			if line <= current_line:
				idx = i
			else:
				break
		return idx, current_line

	def _scroll_to_section(self, index: int) -> None:
		"""Scroll to the given section, move cursor there, and give focus."""
		doc_line = self._sections[index]
		visible_line = self._text_ctrl.VisibleFromDocLine(doc_line)
		self._text_ctrl.SetFirstVisibleLine(visible_line)
		pos = self._text_ctrl.PositionFromLine(doc_line)
		if pos >= 0:
			self._text_ctrl.SetCurrentPos(pos)
			self._text_ctrl.SetSelection(pos, pos)
		self._text_ctrl.SetFocus()

	def _navigate_section(self, delta: int) -> None:
		"""Navigate by delta sections (-1 prev, +1 next). Bell when at boundary.

		Uses current cursor position. Page Up: if inside a section, go to its
		header first; only then to previous section.
		"""
		if not self._sections:
			return
		idx, current_line = self._section_at_cursor()

		if delta < 0:  # Page Up
			header_line = self._sections[idx]
			if current_line > header_line:
				# Inside section: go to section header
				self._scroll_to_section(idx)
				return
			# At header: go to previous section
			idx += delta
		else:  # Page Down
			idx += delta

		if 0 <= idx < len(self._sections):
			self._scroll_to_section(idx)
		else:
			wx.Bell()

	def _go_previous_section(self) -> None:
		self._navigate_section(-1)

	def _go_next_section(self) -> None:
		self._navigate_section(1)

	def _copy_all_to_clipboard(self) -> None:
		"""Copy all properties text to the clipboard."""
		text = self._text_ctrl.GetValue()
		if text and wx.TheClipboard.Open():
			try:
				wx.TheClipboard.SetData(wx.TextDataObject(text))
			finally:
				wx.TheClipboard.Close()

	def _on_char_hook(self, event: wx.KeyEvent) -> None:
		"""Intercept Page Up/Down, Tab, and Escape before child controls receive them.

		EVT_CHAR_HOOK is generated before wxEVT_KEY_DOWN. By not calling Skip(),
		we prevent the STC from receiving Page Up/Down, so it won't scroll.
		STC consumes Tab by default; we forward Tab/Shift+Tab for focus traversal.
		"""
		key = event.GetKeyCode()
		if key == wx.WXK_ESCAPE:
			self.Close()
		elif key == wx.WXK_TAB:
			focused = wx.Window.FindFocus()
			if focused == self._text_ctrl:
				self._close_btn.SetFocus()
			elif focused == self._close_btn:
				self._text_ctrl.SetFocus()
			else:
				event.Skip()
		elif self._sections and key == wx.WXK_PAGEDOWN:
			self._go_next_section()
		elif self._sections and key == wx.WXK_PAGEUP:
			self._go_previous_section()
		else:
			event.Skip()

	def _on_key_down(self, event: wx.KeyEvent) -> None:
		"""Handle Escape to close when focus is on STC or close button."""
		if event.GetKeyCode() == wx.WXK_ESCAPE:
			self.Close()
		else:
			event.Skip()

	def _on_context_menu(self, event: wx.ContextMenuEvent) -> None:
		"""Show context menu with section navigation and copy actions."""
		menu = wx.Menu()

		prev_item = menu.Append(wx.ID_ANY, _("Previous section") + "\tPage Up")
		next_item = menu.Append(wx.ID_ANY, _("Next section") + "\tPage Down")
		menu.AppendSeparator()
		copy_item = menu.Append(
			wx.ID_ANY, _("Copy all properties to clipboard") + "\tCtrl+Shift+C"
		)

		# Use PopupMenu + EVT_MENU; GetPopupMenuSelectionFromUser fails with STC on some platforms.
		prev_id = prev_item.GetId()
		next_id = next_item.GetId()
		copy_id = copy_item.GetId()
		self.Bind(
			wx.EVT_MENU, lambda _: self._go_previous_section(), id=prev_id
		)
		self.Bind(wx.EVT_MENU, lambda _: self._go_next_section(), id=next_id)
		self.Bind(
			wx.EVT_MENU, lambda _: self._copy_all_to_clipboard(), id=copy_id
		)

		self.PopupMenu(menu)
		menu.Destroy()

		self.Unbind(wx.EVT_MENU, id=prev_id)
		self.Unbind(wx.EVT_MENU, id=next_id)
		self.Unbind(wx.EVT_MENU, id=copy_id)
