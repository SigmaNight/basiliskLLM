"""Presenter for HistoryMsgTextCtrl.

Owns message-navigation state, segment management, stream speaking,
citation formatting, and search lifecycle — keeping the view free of
business logic.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Optional

from basilisk.accessible_output import AccessibleOutputHandler
from basilisk.conversation.conversation_model import MessageBlock
from basilisk.message_segment_manager import (
	MessageSegmentManager,
	MessageSegmentType,
)

if TYPE_CHECKING:
	from basilisk.presenters.search_presenter import SearchPresenter
	from basilisk.services.search_service import SearchDirection
	from basilisk.views.history_msg_text_ctrl import HistoryMsgTextCtrl
	from basilisk.views.search_dialog import SearchDialog

import basilisk.config as config

log = logging.getLogger(__name__)


class HistoryPresenter:
	"""Presenter for HistoryMsgTextCtrl.

	Owns the segment manager, speak_response state, accessible output,
	and all non-UI logic for message navigation, citation display, and
	streaming.

	The view is accessed through its wx-style methods (e.g.
	``view.GetInsertionPoint()``).  A ``view.bell()`` thin wrapper is
	required on the view so the presenter never imports wx directly.

	Attributes:
		view: The HistoryMsgTextCtrl view this presenter drives.
		segment_manager: Manages message segment positions.
		speak_response: Whether to speak streaming responses aloud.
		a_output: Accessible output handler.
	"""

	def __init__(self, view: HistoryMsgTextCtrl) -> None:
		"""Initialize the presenter.

		Args:
			view: The HistoryMsgTextCtrl view.
		"""
		self.view = view
		self.segment_manager = MessageSegmentManager()
		self.speak_response: bool = True
		self.a_output = AccessibleOutputHandler()
		self._search_dialog: Optional[SearchDialog] = None
		self._search_presenter: Optional[SearchPresenter] = None

	# ------------------------------------------------------------------
	# Segment management
	# ------------------------------------------------------------------

	def clear(self) -> None:
		"""Clear the segment manager."""
		self.segment_manager.clear()

	def update_last_segment_length(self, last_position: int) -> None:
		"""Update the last content segment length to account for streamed text.

		Args:
			last_position: The current last position in the text control.
		"""
		if not self.segment_manager.segments:
			return
		last_content_index = len(self.segment_manager.segments) - 1
		while (
			last_content_index >= 0
			and self.segment_manager.segments[last_content_index].kind
			!= MessageSegmentType.CONTENT
		):
			last_content_index -= 1
		if last_content_index < 0:
			return
		expected_end = sum(seg.length for seg in self.segment_manager.segments)
		additional_length = last_position - expected_end
		if additional_length > 0:
			content_segment = self.segment_manager.segments[last_content_index]
			content_segment.length += additional_length

	# ------------------------------------------------------------------
	# Current message helpers
	# ------------------------------------------------------------------

	@property
	def current_msg_range(self) -> tuple[int, int]:
		"""Get the (start, end) range of the current message content.

		Returns:
			A tuple of (start, end) absolute positions.
		"""
		self.segment_manager.absolute_position = self.view.GetInsertionPoint()
		self.segment_manager.focus_content_block()
		return (self.segment_manager.start, self.segment_manager.end)

	@property
	def current_msg_block(self) -> Optional[MessageBlock]:
		"""Get the message block at the current cursor position.

		Returns:
			The current MessageBlock, or None if none is found.
		"""
		cursor_pos = self.view.GetInsertionPoint()
		self.segment_manager.absolute_position = cursor_pos
		return self.segment_manager.current_segment.message_block()

	@property
	def current_msg_content(self) -> str:
		"""Get the text content of the current message.

		Returns:
			The content string of the current message.
		"""
		return self.view.GetRange(*self.current_msg_range)

	# ------------------------------------------------------------------
	# Navigation
	# ------------------------------------------------------------------

	def navigate_message(self, previous: bool) -> None:
		"""Navigate to the previous or next message.

		Args:
			previous: If True navigate backward, otherwise forward.
		"""
		try:
			self.segment_manager.absolute_position = (
				self.view.GetInsertionPoint()
			)
		except ValueError:
			# No segments yet (empty control)
			self.view.bell()
			return
		try:
			if previous:
				self.segment_manager.previous(MessageSegmentType.CONTENT)
			else:
				self.segment_manager.next(MessageSegmentType.CONTENT)
		except IndexError:
			self.view.bell()
			return
		try:
			pos = self.segment_manager.start
		except IndexError:
			self.view.bell()
		else:
			self.view.SetInsertionPoint(pos)
			if config.conf().conversation.nav_msg_select:
				self.view.SetSelection(*self.current_msg_range)
			else:
				self.a_output.handle(
					self.current_msg_content, clear_for_speak=True
				)
				self.report_number_of_citations()

	def go_to_previous_message(self) -> None:
		"""Navigate to the previous message."""
		self.navigate_message(True)

	def go_to_next_message(self) -> None:
		"""Navigate to the next message."""
		self.navigate_message(False)

	# ------------------------------------------------------------------
	# Speak response
	# ------------------------------------------------------------------

	@property
	def should_speak_response(self) -> bool:
		"""Check whether the streaming response should be spoken.

		Returns:
			True when speak_response is on, the view (or its prompt) has
			focus, and the top-level window is visible.
		"""
		return (
			self.speak_response
			and (
				self.view.HasFocus()
				or self.view.GetParent().prompt_panel.prompt.HasFocus()
			)
			and self.view.GetTopLevelParent().IsShown()
		)

	def toggle_speak_response(self) -> None:
		"""Toggle speak_response and announce the new state."""
		self.speak_response = not self.speak_response
		self.a_output.handle(
			_("Response speaking %s")
			% (_("enabled") if self.speak_response else _("disabled")),
			braille=True,
			clear_for_speak=False,
		)

	# ------------------------------------------------------------------
	# Streaming
	# ------------------------------------------------------------------

	def handle_stream_chunk(self, text: str) -> None:
		"""Append a streamed chunk to the text control and buffer speech.

		Args:
			text: The chunk of text to append.
		"""
		pos = self.view.GetInsertionPoint()
		if self.should_speak_response:
			self.a_output.handle_stream_buffer(new_text=text)
		self.view.AppendText(text)
		self.view.SetInsertionPoint(pos)

	# ------------------------------------------------------------------
	# Citations
	# ------------------------------------------------------------------

	@staticmethod
	def format_citations(citations: list[dict[str, Any]]) -> str:
		"""Format a list of citations into a human-readable string.

		Args:
			citations: List of citation dicts from the API response.

		Returns:
			A formatted string with all citations separated by ``_--_``.
		"""
		citations_str = []
		for citation in citations:
			location_text = ""
			cited_text = citation.get("cited_text")
			document_index = citation.get("document_index")
			document_title = citation.get("document_title")
			match citation.get("type"):
				case "char_location":
					start_char_index = citation.get("start_char_index", 0)
					end_char_index = citation.get("end_char_index", 0)
					# Translators: This is a citation format for character locations
					location_text = _("C.{start} .. {end}").format(
						start=start_char_index, end=end_char_index
					)
				case "page_location":
					start_page_number = citation.get("start_page_number", 0)
					end_page_number = citation.get("end_page_number", 0)
					# Translators: This is a citation format for page locations
					location_text = _("P.{start} .. {end}").format(
						start=start_page_number, end=end_page_number
					)
				case _:
					# Translators: This is a citation format for unknown locations
					location_text = _("Unknown location")
					log.warning("Unknown citation type: %s", citation)
			if document_index is not None:
				if document_title:
					location_text = _(
						"{document_title} / {location_text}"
					).format(
						document_title=document_title,
						location_text=location_text,
					)
				else:
					location_text = _(
						"Document {document_index} / {location_text}"
					).format(
						document_index=document_index,
						location_text=location_text,
					)
			if cited_text:
				citations_str.append(
					# Translators: This is a citation format for a cited text
					_("{location_text}: \u201c{cited_text}\u201d").format(
						location_text=location_text,
						cited_text=cited_text.strip(),
					)
				)
		return "\n_--_\n".join(citations_str)

	def get_current_citations(self) -> list[dict[str, Any]]:
		"""Return citations for the message at the current cursor position.

		Returns:
			A list of citation dicts, or an empty list when none exist.
		"""
		try:
			block = self.current_msg_block
		except ValueError, IndexError:
			return []
		if not block or not block.response:
			return []
		return block.response.citations

	def report_number_of_citations(self) -> None:
		"""Update the status bar with the citation count for the current message."""
		try:
			block = self.current_msg_block
		except ValueError, IndexError:
			return
		if not block or not block.response:
			return
		citations = block.response.citations
		if not citations:
			return
		nb_citations = len(citations)
		self.view.GetParent().SetStatusText(
			# Translators: This is a status message for the number of citations in the current message
			_("%d citations in the current message") % nb_citations
		)

	def show_citations(self) -> None:
		"""Show a dialog with citations for the current message."""
		from basilisk.views.read_only_message_dialog import (
			ReadOnlyMessageDialog,
		)

		self.report_number_of_citations()
		citations = self.get_current_citations()
		if not citations:
			self.a_output.handle(
				# Translators: This message is emitted when there are no citations for the current message.
				_("No citations for this message"),
				braille=True,
			)
			self.view.bell()
			return
		citations_str = self.format_citations(citations)
		if not citations_str:
			self.view.bell()
			return
		dlg = ReadOnlyMessageDialog(
			self.view,
			# Translators: This is a title for message citations dialog
			_("Message citations"),
			citations_str,
		)
		dlg.ShowModal()
		dlg.Destroy()

	# ------------------------------------------------------------------
	# Search
	# ------------------------------------------------------------------

	def open_search(self, direction: SearchDirection) -> None:
		"""Open (or focus) the search dialog with the given direction.

		Lazily creates the SearchDialog and SearchPresenter on first call.

		Args:
			direction: The initial search direction.
		"""
		from basilisk.presenters.search_presenter import (
			SearchPresenter,
			SearchTargetAdapter,
		)
		from basilisk.views.search_dialog import SearchDialog

		if self._search_dialog is None:
			target = SearchTargetAdapter(self.view)
			self._search_presenter = SearchPresenter(view=None, target=target)
			self._search_dialog = SearchDialog(
				self.view.GetParent(), presenter=self._search_presenter
			)
			self._search_presenter.view = self._search_dialog
		self._search_presenter.search_direction = direction
		self._search_dialog.focus_search_input()
		self._search_dialog.ShowModal()

	def search_next(self) -> None:
		"""Search forward; open the dialog if not yet initialised."""
		from basilisk.services.search_service import SearchDirection

		if self._search_dialog is None:
			self.open_search(SearchDirection.FORWARD)
			return
		self._search_presenter.search_next()

	def search_previous(self) -> None:
		"""Search backward; open the dialog if not yet initialised."""
		from basilisk.services.search_service import SearchDirection

		if self._search_dialog is None:
			self.open_search(SearchDirection.BACKWARD)
			return
		self._search_presenter.search_previous()

	# ------------------------------------------------------------------
	# Cleanup
	# ------------------------------------------------------------------

	def cleanup(self) -> None:
		"""Destroy the search dialog if open and release all references."""
		if self._search_dialog is not None:
			self._search_dialog.Destroy()
			self._search_dialog = None
			self._search_presenter = None
