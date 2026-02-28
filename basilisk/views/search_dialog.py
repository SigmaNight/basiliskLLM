"""Search dialog for searching text in a wx.TextCtrl."""

from __future__ import annotations

from typing import TYPE_CHECKING

import wx

from basilisk.services.search_service import SearchDirection, SearchMode
from basilisk.views.view_mixins import ErrorDisplayMixin

if TYPE_CHECKING:
	from basilisk.presenters.search_presenter import SearchPresenter


class SearchDialog(wx.Dialog, ErrorDisplayMixin):
	"""Dialog for searching text in a wx.TextCtrl."""

	def __init__(
		self,
		parent: wx.Window,
		presenter: SearchPresenter,
		# Translators: Search dialog title
		title: str = _("Search"),
	) -> None:
		"""Initialize the dialog.

		Args:
			parent: The parent window.
			presenter: The SearchPresenter that owns search state and logic.
			title: The dialog title.
		"""
		super().__init__(
			parent,
			title=title,
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)
		self.presenter = presenter
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
		"""Apply presenter state to the dialog controls."""
		self.apply_direction(self.presenter.search_direction)
		self._mode_radio_plain.SetValue(
			self.presenter.search_mode == SearchMode.PLAIN_TEXT
		)
		self._mode_radio_extended.SetValue(
			self.presenter.search_mode == SearchMode.EXTENDED
		)
		self._mode_radio_regex.SetValue(
			self.presenter.search_mode == SearchMode.REGEX
		)
		self._case_sensitive_checkbox.SetValue(self.presenter.case_sensitive)
		self._search_dot_all_checkbox.SetValue(self.presenter.search_dot_all)
		self.update_dot_all_visible(
			self.presenter.search_mode == SearchMode.REGEX
		)
		self.sync_history(self.presenter.search_list, None)

	# ------------------------------------------------------------------
	# View interface — called by SearchPresenter
	# ------------------------------------------------------------------

	def get_search_text(self) -> str:
		"""Return the current combo text, stripped of whitespace.

		Returns:
			The search text entered by the user.
		"""
		return self._search_combo.GetValue().strip()

	def get_direction(self) -> SearchDirection:
		"""Return the currently selected search direction.

		Returns:
			The selected SearchDirection.
		"""
		return (
			SearchDirection.BACKWARD
			if self._dir_radio_backward.GetValue()
			else SearchDirection.FORWARD
		)

	def get_mode(self) -> SearchMode:
		"""Return the currently selected search mode.

		Returns:
			The selected SearchMode.
		"""
		if self._mode_radio_plain.GetValue():
			return SearchMode.PLAIN_TEXT
		if self._mode_radio_extended.GetValue():
			return SearchMode.EXTENDED
		return SearchMode.REGEX

	def get_case_sensitive(self) -> bool:
		"""Return whether the case-sensitive checkbox is checked.

		Returns:
			True if case-sensitive is enabled.
		"""
		return self._case_sensitive_checkbox.GetValue()

	def get_dot_all(self) -> bool:
		"""Return whether the dot-all checkbox is checked.

		Returns:
			True if dot-all is enabled.
		"""
		return self._search_dot_all_checkbox.GetValue()

	def apply_direction(self, direction: SearchDirection) -> None:
		"""Update radio buttons to reflect the given direction.

		Args:
			direction: The direction to select.
		"""
		self._dir_radio_forward.SetValue(direction == SearchDirection.FORWARD)
		self._dir_radio_backward.SetValue(direction == SearchDirection.BACKWARD)

	def show_not_found(self, text: str) -> None:
		"""Show a 'not found' message to the user.

		Args:
			text: The search text that was not found.
		"""
		wx.MessageBox(
			# Translators: Search dialog message when text is not found
			_('"{search_text}" not found.').format(search_text=text),
			# Translators: Search dialog result title
			_("Search Result"),
			wx.OK | wx.ICON_INFORMATION,
		)

	def sync_history(
		self, search_list: list[str], current_text: str | None
	) -> None:
		"""Refresh the combo items to match search_list.

		Args:
			search_list: The updated history list.
			current_text: The item to select, or None.
		"""
		self._search_combo.Clear()
		self._search_combo.AppendItems(search_list)
		if current_text is not None and current_text in search_list:
			self._search_combo.SetSelection(search_list.index(current_text))

	def update_dot_all_visible(self, show: bool) -> None:
		"""Show or hide the dot-all checkbox.

		Args:
			show: True to show the checkbox, False to hide it.
		"""
		if show:
			self._search_dot_all_checkbox.Show()
		else:
			self._search_dot_all_checkbox.Hide()
		self.Layout()

	def dismiss_modal(self) -> None:
		"""End the modal loop if the dialog is currently modal."""
		if self.IsModal():
			self.EndModal(wx.ID_OK)

	def focus_search_input(self) -> None:
		"""Set focus to the search combo and select all text."""
		self._search_combo.SetFocus()
		self._search_combo.SelectAll()

	# ------------------------------------------------------------------
	# Event handlers — delegate to presenter
	# ------------------------------------------------------------------

	def _on_find(self, event: wx.Event) -> None:
		"""Handle the find button click event.

		Args:
			event: The event object.
		"""
		self.presenter.on_find()

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
		self.presenter.on_mode_changed(self.get_mode())

	def search_previous(self) -> None:
		"""Search for the previous match via the presenter."""
		self.presenter.search_previous()

	def search_next(self) -> None:
		"""Search for the next match via the presenter."""
		self.presenter.search_next()
