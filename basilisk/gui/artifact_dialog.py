"""Artifact management dialog for viewing and managing conversation artifacts.

This module provides a dialog window for displaying, copying, saving, and managing
artifacts extracted from conversation messages.
"""

from __future__ import annotations

import logging
import os
import tempfile
import weakref
from typing import TYPE_CHECKING, List, Optional

import wx

from basilisk.conversation.artifact import (
	Artifact,
	ArtifactManager,
	ArtifactType,
)
from .html_view_window import show_html_view_window

if TYPE_CHECKING:
	from .conversation_tab import ConversationTab

log = logging.getLogger(__name__)


class ArtifactListCtrl(wx.ListCtrl):
	"""Custom list control for displaying artifacts."""

	def __init__(self, parent: wx.Window):
		"""Initialize the artifact list control.

		Args:
			parent: Parent window
		"""
		super().__init__(
			parent, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_SUNKEN
		)

		# Add columns
		self.AppendColumn(_("Title"), width=300)
		self.AppendColumn(_("Type"), width=100)
		self.AppendColumn(_("Language"), width=80)
		self.AppendColumn(_("Size"), width=80)

		self.artifacts: List[Artifact] = []

	def update_artifacts(self, artifacts: List[Artifact]) -> None:
		"""Update the list with new artifacts.

		Args:
			artifacts: List of artifacts to display
		"""
		self.artifacts = artifacts
		self.DeleteAllItems()

		for i, artifact in enumerate(artifacts):
			index = self.InsertItem(i, artifact.title)
			self.SetItem(
				index, 1, artifact.type.value.replace('_', ' ').title()
			)
			self.SetItem(index, 2, artifact.language or "-")
			self.SetItem(index, 3, f"{len(artifact.content)} chars")
			self.SetItemData(index, i)

	def get_selected_artifact(self) -> Optional[Artifact]:
		"""Get the currently selected artifact.

		Returns:
			Selected artifact or None if nothing selected
		"""
		selection = self.GetFirstSelected()
		if selection == -1:
			return None

		item_data = self.GetItemData(selection)
		if 0 <= item_data < len(self.artifacts):
			return self.artifacts[item_data]
		return None


class ArtifactDialog(wx.Dialog):
	"""Dialog for managing conversation artifacts."""

	def __init__(self, parent: wx.Window, conversation_tab: 'ConversationTab'):
		"""Initialize the artifact dialog.

		Args:
			parent: Parent window
			conversation_tab: The conversation tab that owns this dialog
		"""
		super().__init__(
			parent,
			title=_("Conversation Artifacts"),
			size=(800, 600),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
		)

		self.conversation_tab = weakref.ref(conversation_tab)
		self.artifact_manager = conversation_tab.artifact_manager

		self._init_ui()
		self._bind_events()
		self._update_artifact_list()

	def _init_ui(self) -> None:
		"""Initialize the user interface."""
		panel = wx.Panel(self)

		# Create the artifact list
		self.artifact_list = ArtifactListCtrl(panel)

		# Create buttons
		self.view_button = wx.Button(panel, label=_("&View"))
		self.copy_button = wx.Button(panel, label=_("&Copy"))
		self.save_button = wx.Button(panel, label=_("&Save As..."))
		self.refresh_button = wx.Button(panel, label=_("&Refresh"))
		self.close_button = wx.Button(panel, wx.ID_CLOSE, label=_("&Close"))

		# Initially disable action buttons
		self.view_button.Enable(False)
		self.copy_button.Enable(False)
		self.save_button.Enable(False)

		# Layout
		button_sizer = wx.BoxSizer(wx.HORIZONTAL)
		button_sizer.Add(self.view_button, 0, wx.ALL, 5)
		button_sizer.Add(self.copy_button, 0, wx.ALL, 5)
		button_sizer.Add(self.save_button, 0, wx.ALL, 5)
		button_sizer.AddStretchSpacer()
		button_sizer.Add(self.refresh_button, 0, wx.ALL, 5)
		button_sizer.Add(self.close_button, 0, wx.ALL, 5)

		main_sizer = wx.BoxSizer(wx.VERTICAL)
		main_sizer.Add(
			wx.StaticText(panel, label=_("Artifacts found in conversation:")),
			0,
			wx.ALL,
			5,
		)
		main_sizer.Add(self.artifact_list, 1, wx.EXPAND | wx.ALL, 5)
		main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.ALL, 5)

		panel.SetSizer(main_sizer)

	def _bind_events(self) -> None:
		"""Bind UI events."""
		self.view_button.Bind(wx.EVT_BUTTON, self._on_view)
		self.copy_button.Bind(wx.EVT_BUTTON, self._on_copy)
		self.save_button.Bind(wx.EVT_BUTTON, self._on_save)
		self.refresh_button.Bind(wx.EVT_BUTTON, self._on_refresh)
		self.close_button.Bind(wx.EVT_BUTTON, self._on_close)

		self.artifact_list.Bind(
			wx.EVT_LIST_ITEM_SELECTED, self._on_selection_changed
		)
		self.artifact_list.Bind(
			wx.EVT_LIST_ITEM_DESELECTED, self._on_selection_changed
		)
		self.artifact_list.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._on_view)

	def _update_artifact_list(self) -> None:
		"""Update the artifact list display."""
		self.artifact_list.update_artifacts(self.artifact_manager.artifacts)

		# Update status
		count = len(self.artifact_manager.artifacts)
		if count == 0:
			self.SetTitle(_("Conversation Artifacts (No artifacts found)"))
		else:
			self.SetTitle(_("Conversation Artifacts ({} found)").format(count))

	def _on_selection_changed(self, event: wx.Event) -> None:
		"""Handle artifact selection changes."""
		has_selection = self.artifact_list.get_selected_artifact() is not None
		self.view_button.Enable(has_selection)
		self.copy_button.Enable(has_selection)
		self.save_button.Enable(has_selection)

	def _on_view(self, event: wx.Event) -> None:
		"""View the selected artifact in a separate window."""
		artifact = self.artifact_list.get_selected_artifact()
		if not artifact:
			return

		# Determine content format for viewing
		if artifact.type == ArtifactType.CODE_BLOCK:
			# For code blocks, wrap in markdown code fence
			content = f"```{artifact.language or ''}\n{artifact.content}\n```"
			format_type = "markdown"
		else:
			content = artifact.content
			format_type = (
				"markdown" if artifact.type == ArtifactType.MARKDOWN else "html"
			)

		show_html_view_window(
			parent=self,
			content=content,
			content_format=format_type,
			title=artifact.title,
		)

	def _on_copy(self, event: wx.Event) -> None:
		"""Copy the selected artifact to clipboard."""
		artifact = self.artifact_list.get_selected_artifact()
		if not artifact:
			return

		if wx.TheClipboard.Open():
			try:
				data = wx.TextDataObject(artifact.content)
				wx.TheClipboard.SetData(data)
				wx.MessageBox(
					_("Artifact copied to clipboard."),
					_("Copy Successful"),
					wx.OK | wx.ICON_INFORMATION,
				)
			finally:
				wx.TheClipboard.Close()
		else:
			wx.MessageBox(
				_("Failed to open clipboard."),
				_("Copy Error"),
				wx.OK | wx.ICON_ERROR,
			)

	def _on_save(self, event: wx.Event) -> None:
		"""Save the selected artifact to a file."""
		artifact = self.artifact_list.get_selected_artifact()
		if not artifact:
			return

		# Determine file extension based on artifact type
		if artifact.type == ArtifactType.CODE_BLOCK and artifact.language:
			ext_map = {
				'python': '.py',
				'javascript': '.js',
				'typescript': '.ts',
				'html': '.html',
				'css': '.css',
				'java': '.java',
				'cpp': '.cpp',
				'c': '.c',
				'php': '.php',
				'ruby': '.rb',
				'go': '.go',
				'rust': '.rs',
				'sql': '.sql',
				'json': '.json',
				'xml': '.xml',
				'yaml': '.yml',
			}
			default_ext = ext_map.get(artifact.language.lower(), '.txt')
		else:
			default_ext = '.txt'

		# Create safe filename from title
		safe_title = "".join(
			c for c in artifact.title if c.isalnum() or c in (' ', '-', '_')
		).strip()
		default_filename = f"{safe_title}{default_ext}"

		with wx.FileDialog(
			self,
			message=_("Save artifact as..."),
			defaultFile=default_filename,
			wildcard=_("All files (*.*)|*.*"),
			style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT,
		) as dialog:
			if dialog.ShowModal() == wx.ID_OK:
				filepath = dialog.GetPath()
				try:
					with open(filepath, 'w', encoding='utf-8') as f:
						f.write(artifact.content)

					wx.MessageBox(
						_("Artifact saved successfully."),
						_("Save Successful"),
						wx.OK | wx.ICON_INFORMATION,
					)
				except Exception as e:
					log.error("Failed to save artifact: %s", e)
					wx.MessageBox(
						_("Failed to save artifact: {}").format(str(e)),
						_("Save Error"),
						wx.OK | wx.ICON_ERROR,
					)

	def _on_refresh(self, event: wx.Event) -> None:
		"""Refresh the artifact list by re-scanning conversation."""
		conversation_tab = self.conversation_tab()
		if conversation_tab:
			conversation_tab.scan_for_artifacts()
			self._update_artifact_list()

	def _on_close(self, event: wx.Event) -> None:
		"""Close the dialog."""
		self.EndModal(wx.ID_CLOSE)


def show_artifact_dialog(
	parent: wx.Window, conversation_tab: 'ConversationTab'
) -> None:
	"""Show the artifact management dialog.

	Args:
		parent: Parent window
		conversation_tab: The conversation tab to manage artifacts for
	"""
	dialog = ArtifactDialog(parent, conversation_tab)
	dialog.ShowModal()
	dialog.Destroy()
