"""Search dialog for searching text in a wx.TextCtrl."""

import enum
import re
from typing import List

import wx


class SearchDirection(enum.IntEnum):
	"""Enumeration for search directions."""

	BACKWARD = enum.auto(0)
	FORWARD = enum.auto()


class SearchMode(enum.IntEnum):
	"""Enumeration for search modes."""

	PLAIN_TEXT = enum.auto(0)
	EXTENDED = enum.auto()
	REGEX = enum.auto()


def adjust_utf16_position(
	text: str, position: int, reverse: bool = False
) -> int:
	"""Adjust the given position in the text to account for characters outside of the Basic Multilingual Plane (BMP).

	Characters outside the BMP are represented by surrogate pairs in UTF-16, taking up two positions instead of one.
	This function adjusts the given position to account for these surrogate pairs.

	Args:
		text: The input string.
		position: The original position in the string.
		reverse: If True, the function will adjust the position in the reverse direction.

	Returns:
		The adjusted position reflecting the presence of surrogate pairs.
	"""
	relevant_text = text[:position]
	count_high_surrogates = sum(1 for c in relevant_text if ord(c) >= 0x10000)
	if reverse:
		count_high_surrogates -= count_high_surrogates
	count_line_breaks = sum(1 for c in relevant_text if c == "\n")
	if reverse:
		count_line_breaks -= count_line_breaks
	return position + count_high_surrogates + count_line_breaks


class SearchDialog(wx.Dialog):
	"""Dialog for searching text in a wx.TextCtrl."""

	def __init__(
		self,
		parent: wx.Window,
		text: wx.TextCtrl,
		# Translators: Search dialog title
		title: str = _("Search"),
		search_list: List[str] = [],
	) -> None:
		"""Initialize the dialog.

		Args:
			parent: The parent window.
			text: The text control to search in.
			title: The dialog title.
			search_list: The list of search strings.
		"""
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self._text = text
		self._search_list = search_list
		self._search_direction = SearchDirection.FORWARD
		self._search_mode = SearchMode.PLAIN_TEXT
		self._case_sensitive = False
		self._search_dot_all = False
		self._create_ui()
		self._bind_events()
		self._apply_initial_values()
		self._search_combo.SetFocus()

	def _create_ui(self) -> None:
		"""Create the dialog UI."""
		main_sizer = wx.BoxSizer(wx.VERTICAL)

		search_text_sizer = wx.BoxSizer(wx.HORIZONTAL)
		search_label = wx.StaticText(
			self,
			# Translators: Search dialog label
			label=_("&Search for:"),
		)
		self._search_combo = wx.ComboBox(self, style=wx.CB_DROPDOWN)
		search_text_sizer.Add(search_label, flag=wx.ALL | wx.CENTER, border=5)
		search_text_sizer.Add(
			self._search_combo, proportion=1, flag=wx.ALL | wx.EXPAND, border=5
		)
		main_sizer.Add(search_text_sizer, flag=wx.EXPAND)

		direction_box = wx.StaticBox(
			self,
			# Translators: Search dialog label
			label=_("Direction"),
		)
		direction_sizer = wx.StaticBoxSizer(direction_box, wx.HORIZONTAL)

		self._dir_radio_backward = wx.RadioButton(
			self,
			# Translators: Search dialog label
			label=_("&Backward"),
			style=wx.RB_GROUP,
		)
		self._dir_radio_forward = wx.RadioButton(
			self,
			# Translators: Search dialog label
			label=_("&Forward"),
		)

		direction_sizer.Add(self._dir_radio_backward, flag=wx.ALL, border=5)
		direction_sizer.Add(self._dir_radio_forward, flag=wx.ALL, border=5)

		main_sizer.Add(direction_sizer, flag=wx.ALL | wx.EXPAND, border=10)

		mode_box = wx.StaticBox(
			self,
			# Translators: Search dialog label
			label=_("Mode"),
		)
		mode_sizer = wx.StaticBoxSizer(mode_box, wx.HORIZONTAL)

		self._mode_radio_plain = wx.RadioButton(
			self,
			# Translators: Search dialog label
			label=_("&Plain Text"),
			# Translators: Search dialog label
			style=wx.RB_GROUP,
		)
		self._mode_radio_extended = wx.RadioButton(
			self,
			# Translators: Search dialog label
			label=_("E&xtended") + r" (\n, \t, \r...)",
		)
		self._mode_radio_regex = wx.RadioButton(
			self,
			# Translators: Search dialog label
			label=_("Re&gular Expression"),
		)

		mode_sizer.Add(self._mode_radio_plain, flag=wx.ALL, border=5)
		mode_sizer.Add(self._mode_radio_extended, flag=wx.ALL, border=5)
		mode_sizer.Add(self._mode_radio_regex, flag=wx.ALL, border=5)

		main_sizer.Add(mode_sizer, flag=wx.ALL | wx.EXPAND, border=10)

		self._search_dot_all_checkbox = wx.CheckBox(
			self,
			# Translators: Search dialog label
			label=_("Dot matches &all (.)"),
		)
		main_sizer.Add(
			self._search_dot_all_checkbox, flag=wx.ALL | wx.CENTER, border=5
		)
		self._search_dot_all_checkbox.Hide()

		self._case_sensitive_checkbox = wx.CheckBox(
			self,
			# Translators: Search dialog label
			label=_("&Case Sensitive"),
		)
		main_sizer.Add(
			self._case_sensitive_checkbox, flag=wx.ALL | wx.CENTER, border=5
		)

		button_sizer = wx.StdDialogButtonSizer()
		self._find_button = wx.Button(self, wx.ID_FIND)
		self._find_button.SetDefault()
		button_sizer.AddButton(self._find_button)
		self._close_button = wx.Button(self, wx.ID_CANCEL)
		button_sizer.AddButton(self._close_button)
		button_sizer.Realize()
		main_sizer.Add(button_sizer, flag=wx.ALL | wx.ALIGN_CENTER, border=5)

		self.SetSizerAndFit(main_sizer)

	def _bind_events(self) -> None:
		"""Bind events to the dialog controls."""
		self._find_button.Bind(wx.EVT_BUTTON, self._on_find)
		self._mode_radio_plain.Bind(wx.EVT_RADIOBUTTON, self._on_mode_change)
		self._mode_radio_extended.Bind(wx.EVT_RADIOBUTTON, self._on_mode_change)
		self._mode_radio_regex.Bind(wx.EVT_RADIOBUTTON, self._on_mode_change)
		self.Bind(wx.EVT_CLOSE, self._on_close)

	def _apply_initial_values(self) -> None:
		"""Apply the initial values to the dialog controls."""
		self._dir_radio_forward.SetValue(
			self._search_direction == SearchDirection.FORWARD
		)
		self._dir_radio_backward.SetValue(
			self._search_direction == SearchDirection.BACKWARD
		)
		self._mode_radio_plain.SetValue(
			self._search_mode == SearchMode.PLAIN_TEXT
		)
		self._mode_radio_extended.SetValue(
			self._search_mode == SearchMode.EXTENDED
		)
		self._mode_radio_regex.SetValue(self._search_mode == SearchMode.REGEX)
		self._case_sensitive_checkbox.SetValue(self._case_sensitive)
		self._search_dot_all_checkbox.SetValue(self._search_dot_all)
		self._update_dot_all_visibility()
		self._update_search_choice()

	def _update_search_choice(self) -> None:
		"""Update the search choice combo box."""
		self._search_combo.Clear()
		self._search_combo.AppendItems(self._search_list)

	def _update_dot_all_visibility(self) -> None:
		"""Update the visibility of the "Dot matches all" checkbox."""
		if self._mode_radio_regex.GetValue():
			self._search_dot_all_checkbox.Show()
		else:
			self._search_dot_all_checkbox.Hide()
		self.Layout()

	def _compile_search_pattern(self, query_text: str) -> re.Pattern:
		"""Compile the search pattern based on the search mode.

		Args:
			query_text: The search text to compile.
		"""
		flags = 0 if self._case_sensitive else re.IGNORECASE
		flags |= re.UNICODE
		if self._search_dot_all and self._search_mode == SearchMode.REGEX:
			flags |= re.DOTALL
		if self._search_mode == SearchMode.EXTENDED:
			query_text = (
				query_text.replace(r"\n", "\n")
				.replace(r"\t", "\t")
				.replace(r"\r", "\r")
				.replace(r"\x00", "\x00")
				.replace(r"\x1F", "\x1f")
				.replace(r"\x7F", "\x7f")
			)
		return re.compile(query_text, flags)

	def _find_matches(self, search_text: str) -> List[re.Match]:
		"""Find all matches of the search text in the text control.

		Args:
			search_text: The text to search for.

		Returns:
			List[re.Match]: A list of regex matches.
		"""
		text_content = self._text.GetValue()
		if not self._case_sensitive:
			text_content = text_content.lower()
			search_text = search_text.lower()

		if self._search_mode in {SearchMode.PLAIN_TEXT, SearchMode.EXTENDED}:
			search_pattern = (
				re.escape(search_text)
				if self._search_mode == SearchMode.PLAIN_TEXT
				else search_text
			)
		else:
			search_pattern = search_text

		pattern = self._compile_search_pattern(search_pattern)
		return list(pattern.finditer(text_content))

	def _select_text(self, start: int, end: int):
		"""Select the text in the text control.

		Args:
			start: The start position of the selection.
			end: The end position of the selection.
		"""
		self._text.SetSelection(start, end)
		self._text.SetFocus()

	def _on_find(self, event: wx.Event) -> None:
		"""Handle the find button click event.

		Args:
			event: The event object.
		"""
		if self.IsModal():
			self.EndModal(wx.ID_OK)

		search_text = self._search_combo.GetValue().strip()
		if not search_text:
			wx.MessageBox(
				# Translators: Search dialog error message
				_("Please enter text to search for."),
				# Translators: Search dialog error title
				_("Error"),
				wx.OK | wx.ICON_ERROR,
			)
			return

		if search_text not in self._search_list:
			self._search_list.append(search_text)
			self._search_combo.Append(search_text)
			self._search_combo.SetSelection(len(self._search_list) - 1)
		else:
			index = self._search_list.index(search_text)
			self._search_combo.SetSelection(index)
		self._case_sensitive = self._case_sensitive_checkbox.GetValue()
		self._search_dot_all = self._search_dot_all_checkbox.GetValue()
		self._search_direction = (
			SearchDirection.BACKWARD
			if self._dir_radio_backward.GetValue()
			else SearchDirection.FORWARD
		)
		self._search_mode = (
			SearchMode.PLAIN_TEXT
			if self._mode_radio_plain.GetValue()
			else SearchMode.EXTENDED
			if self._mode_radio_extended.GetValue()
			else SearchMode.REGEX
		)

		matches = self._find_matches(search_text)
		if not matches:
			wx.MessageBox(
				# Translators: Search dialog error message
				_('"{search_text}" not found.').format(search_text=search_text),
				# Translators: Search dialog error title
				_("Search Result"),
				wx.OK | wx.ICON_INFORMATION,
			)
			return

		cursor_pos = self._text.GetInsertionPoint()
		cursor_pos = adjust_utf16_position(
			self._text.GetValue(), cursor_pos, reverse=True
		)
		match_positions = [(match.start(), match.end()) for match in matches]

		if self._search_direction == SearchDirection.FORWARD:
			for start, end in match_positions:
				start = adjust_utf16_position(self._text.GetValue(), start)
				end = adjust_utf16_position(self._text.GetValue(), end)
				if start > cursor_pos:
					self._select_text(start, end)
					return
		else:
			cursor_pos += 1
			for start, end in reversed(match_positions):
				start = adjust_utf16_position(self._text.GetValue(), start)
				end = adjust_utf16_position(self._text.GetValue(), end)
				if end < cursor_pos:
					self._select_text(start, end)
					return

		wx.MessageBox(
			_('"{search_text}" not found.').format(search_text=search_text),
			_("Search Result"),
			wx.OK | wx.ICON_INFORMATION,
		)

	def _on_close(self, event: wx.Event) -> None:
		"""Handle the dialog close event.

		Args:
			event: The event object.
		"""
		self.EndModal(wx.ID_CANCEL)

	def _on_mode_change(self, event: wx.Event) -> None:
		"""Handle the search mode radio button change event.

		Args:
			event: The event object.
		"""
		self._update_dot_all_visibility()

	@property
	def search_direction(self) -> SearchDirection:
		"""Get the search direction.

		Returns:
			The search direction.
		"""
		return self._search_direction

	@search_direction.setter
	def search_direction(self, value: SearchDirection) -> None:
		"""Set the search direction.

		Args:
			value: The search direction.
		"""
		if value not in {SearchDirection.BACKWARD, SearchDirection.FORWARD}:
			raise ValueError("search_direction must be a SearchDirection")
		self._search_direction = value

	def search_previous(self) -> None:
		"""Search for the previous match."""
		self._dir_radio_backward.SetValue(True)
		self._on_find(None)

	def search_next(self) -> None:
		"""Search for the next match."""
		self._dir_radio_forward.SetValue(True)
		self._on_find(None)
