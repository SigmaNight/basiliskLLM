"""Dialog for browsing and managing conversation history."""

import logging

import wx

from basilisk.presenters.conversation_history_presenter import (
	ConversationHistoryPresenter,
)

log = logging.getLogger(__name__)

# Debounce delay for search input in milliseconds
SEARCH_DEBOUNCE_MS = 300
# Number of conversations loaded per page
PAGE_SIZE = 100


class ConversationHistoryDialog(wx.Dialog):
	"""Dialog to browse, search, open, and delete saved conversations."""

	def __init__(self, parent: wx.Window):
		"""Initialize the conversation history dialog.

		Args:
			parent: The parent window.
		"""
		super().__init__(
			parent,
			# Translators: Title of the conversation history dialog
			title=_("Conversation history"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
			size=(600, 400),
		)
		self.presenter = ConversationHistoryPresenter(
			self, conv_db_getter=lambda: wx.GetApp().conv_db
		)
		self.selected_conv_id: int | None = None
		self._search_timer = wx.Timer(self)
		self._conversations: list[dict] = []
		self._offset: int = 0

		self._init_ui()
		self._bind_events()
		self._refresh_list()
		self.CenterOnParent()

	def _init_ui(self):
		"""Initialize the dialog UI components."""
		sizer = wx.BoxSizer(wx.VERTICAL)

		# Search
		search_label = wx.StaticText(
			self,
			# Translators: Label for the search field in conversation history
			label=_("&Search:"),
		)
		sizer.Add(search_label, flag=wx.EXPAND | wx.ALL, border=5)
		self.search_ctrl = wx.TextCtrl(self)
		sizer.Add(
			self.search_ctrl, flag=wx.EXPAND | wx.LEFT | wx.RIGHT, border=5
		)

		# Conversation list
		list_label = wx.StaticText(
			self,
			# Translators: Label for the conversation list in history dialog
			label=_("&Conversations:"),
		)
		sizer.Add(list_label, flag=wx.EXPAND | wx.ALL, border=5)
		self.list_ctrl = wx.ListCtrl(
			self, style=wx.LC_REPORT | wx.LC_SINGLE_SEL
		)
		self.list_ctrl.AppendColumn(
			# Translators: Column header for conversation title
			_("Title"),
			width=250,
		)
		self.list_ctrl.AppendColumn(
			# Translators: Column header for message count
			_("Messages"),
			width=80,
		)
		self.list_ctrl.AppendColumn(
			# Translators: Column header for last update time
			_("Last updated"),
			width=150,
		)
		sizer.Add(
			self.list_ctrl,
			proportion=1,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT,
			border=5,
		)

		# Count label
		# Translators: Shows how many conversations are currently displayed
		self.count_label = wx.StaticText(self, label="")
		sizer.Add(
			self.count_label,
			flag=wx.EXPAND | wx.LEFT | wx.RIGHT | wx.TOP,
			border=5,
		)

		# Buttons
		btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
		self.open_btn = wx.Button(
			self,
			wx.ID_OPEN,
			# Translators: Button to open a conversation from history
			_("&Open"),
		)
		self.open_btn.SetDefault()
		self.open_btn.Enable(False)
		btn_sizer.Add(self.open_btn, flag=wx.RIGHT, border=5)

		self.delete_btn = wx.Button(
			self,
			wx.ID_DELETE,
			# Translators: Button to delete a conversation from history
			_("&Delete"),
		)
		self.delete_btn.Enable(False)
		btn_sizer.Add(self.delete_btn, flag=wx.RIGHT, border=5)

		# Translators: Button to load more conversations in history dialog
		self.load_more_btn = wx.Button(self, label=_("Load &more"))
		self.load_more_btn.Enable(False)
		btn_sizer.Add(self.load_more_btn, flag=wx.RIGHT, border=5)

		close_btn = wx.Button(self, wx.ID_CANCEL, _("&Close"))
		btn_sizer.Add(close_btn)

		sizer.Add(btn_sizer, flag=wx.ALIGN_RIGHT | wx.ALL, border=10)

		self.SetSizer(sizer)

	def _bind_events(self):
		"""Bind event handlers."""
		self.search_ctrl.Bind(wx.EVT_TEXT, self._on_search_text)
		self.Bind(wx.EVT_TIMER, self._on_search_timer, self._search_timer)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_item_selected)
		self.list_ctrl.Bind(
			wx.EVT_LIST_ITEM_DESELECTED, self._on_item_deselected
		)
		self.list_ctrl.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_open)
		self.list_ctrl.Bind(wx.EVT_KEY_DOWN, self._on_list_key)
		self.open_btn.Bind(wx.EVT_BUTTON, self._on_open)
		self.delete_btn.Bind(wx.EVT_BUTTON, self._on_delete)
		self.load_more_btn.Bind(wx.EVT_BUTTON, self._on_load_more)

	def _on_search_text(self, event):
		"""Handle search text changes with debounce."""
		self._search_timer.Stop()
		self._search_timer.StartOnce(SEARCH_DEBOUNCE_MS)

	def _on_search_timer(self, event):
		"""Execute search after debounce delay."""
		self._refresh_list()

	def _on_item_selected(self, event):
		"""Enable delete button when an item is selected."""
		enable_btn = self.list_ctrl.GetSelectedItemCount() >= 1
		self.open_btn.Enable(enable_btn)
		self.delete_btn.Enable(enable_btn)

	def _on_item_deselected(self, event):
		"""Defer button-state update so selection changes settle first."""
		wx.CallAfter(self._update_buttons_state)

	def _update_buttons_state(self):
		"""Enable or disable Open/Delete based on current selection count."""
		has_selection = self.list_ctrl.GetSelectedItemCount() >= 1
		self.open_btn.Enable(has_selection)
		self.delete_btn.Enable(has_selection)

	def _on_list_key(self, event):
		"""Handle keyboard shortcuts in the list."""
		keycode = event.GetKeyCode()
		if keycode == wx.WXK_DELETE:
			self._on_delete(event)
		else:
			event.Skip()

	def _on_open(self, event):
		"""Open the selected conversation."""
		index = self.list_ctrl.GetFirstSelected()
		if index == -1:
			return
		self.selected_conv_id = self._conversations[index]["id"]
		self.EndModal(wx.ID_OK)

	def _on_delete(self, event):
		"""Delete the selected conversation after confirmation."""
		index = self.list_ctrl.GetFirstSelected()
		if index == -1:
			return

		conv = self._conversations[index]
		title = conv["title"] or _("Untitled conversation")
		result = wx.MessageBox(
			# Translators: Confirmation message for deleting a conversation
			_('Are you sure you want to delete "%s"?') % title,
			# Translators: Title of the delete confirmation dialog
			_("Confirm deletion"),
			wx.YES_NO | wx.NO_DEFAULT | wx.ICON_WARNING,
			self,
		)
		if result != wx.YES:
			return

		if self.presenter.delete_conversation(conv["id"]):
			self._refresh_list()
		else:
			wx.MessageBox(
				# Translators: Error message shown when a conversation cannot be deleted
				_("Failed to delete conversation"),
				# Translators: Title of the error dialog when deletion fails
				_("Error"),
				wx.OK | wx.ICON_ERROR,
				self,
			)

	def _on_load_more(self, event):
		"""Load the next page of conversations."""
		self._offset += PAGE_SIZE
		self._refresh_list(reset=False)

	def _refresh_list(self, reset: bool = True):
		"""Refresh the conversation list from the database.

		Args:
			reset: If True, clear existing items and reset offset before
				fetching. If False, append newly fetched items to the list.
		"""
		if reset:
			self._offset = 0
			self.list_ctrl.DeleteAllItems()
			self._conversations = []

		search = self.search_ctrl.GetValue().strip() or None
		new_convs = self.presenter.load_conversations(
			search=search, limit=PAGE_SIZE, offset=self._offset
		)
		total = self.presenter.get_conversation_count(search)

		self._conversations.extend(new_convs)
		for conv in new_convs:
			index = self.list_ctrl.GetItemCount()
			title = conv["title"] or _("Untitled conversation")
			self.list_ctrl.InsertItem(index, title)
			self.list_ctrl.SetItem(index, 1, str(conv["message_count"]))
			updated = conv["updated_at"]
			if updated:
				self.list_ctrl.SetItem(
					index, 2, updated.strftime("%Y-%m-%d %H:%M")
				)

		shown = len(self._conversations)
		# Translators: Status showing how many conversations are visible vs total
		self.count_label.SetLabel(
			_("Showing %d of %d conversations") % (shown, total)
		)
		self.load_more_btn.Enable(shown < total)
		self.open_btn.Enable(False)
		self.delete_btn.Enable(False)

	def Destroy(self):
		"""Clean up timer before destroying the dialog."""
		self._search_timer.Stop()
		return super().Destroy()
