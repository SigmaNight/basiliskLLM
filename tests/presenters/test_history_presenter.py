"""Tests for HistoryPresenter."""

from unittest.mock import MagicMock, patch

from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)
from basilisk.presenters.history_presenter import HistoryPresenter

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_view(insertion_point: int = 0, text: str = ""):
	"""Return a mock HistoryMsgTextCtrl view.

	Args:
		insertion_point: Value returned by GetInsertionPoint().
		text: Value returned by GetValue().

	Returns:
		A MagicMock configured with sensible defaults.
	"""
	view = MagicMock()
	view.GetInsertionPoint.return_value = insertion_point
	view.GetValue.return_value = text
	view.HasFocus.return_value = False
	view.GetTopLevelParent.return_value.IsShown.return_value = True
	view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = (
		False
	)
	return view


def make_presenter(insertion_point: int = 0) -> HistoryPresenter:
	"""Return a HistoryPresenter wired to a mock view.

	Args:
		insertion_point: Cursor position to simulate.

	Returns:
		A fresh HistoryPresenter instance.
	"""
	return HistoryPresenter(make_view(insertion_point=insertion_point))


def _add_content_segment(
	presenter: HistoryPresenter, length: int = 10
) -> MessageSegment:
	"""Append a CONTENT segment of the given length to the presenter.

	Args:
		presenter: The HistoryPresenter to modify.
		length: The segment length.

	Returns:
		The appended MessageSegment.
	"""
	block_ref = MagicMock()
	seg = MessageSegment(
		length=length, kind=MessageSegmentType.CONTENT, message_block=block_ref
	)
	presenter.segment_manager.append(seg)
	return seg


# ---------------------------------------------------------------------------
# Initialisation
# ---------------------------------------------------------------------------


class TestHistoryPresenterInit:
	"""Tests for HistoryPresenter initial state."""

	def test_speak_response_defaults_to_true(self):
		"""speak_response is True after construction."""
		assert make_presenter().speak_response is True

	def test_segment_manager_created(self):
		"""segment_manager is a fresh MessageSegmentManager."""
		p = make_presenter()
		assert isinstance(p.segment_manager, MessageSegmentManager)
		assert p.segment_manager.segments == []

	def test_a_output_created(self):
		"""a_output is not None after construction."""
		assert make_presenter().a_output is not None

	def test_search_dialog_initially_none(self):
		"""_search_dialog is None before first search."""
		assert make_presenter()._search_dialog is None

	def test_search_presenter_initially_none(self):
		"""_search_presenter is None before first search."""
		assert make_presenter()._search_presenter is None


# ---------------------------------------------------------------------------
# clear()
# ---------------------------------------------------------------------------


class TestHistoryPresenterClear:
	"""Tests for HistoryPresenter.clear()."""

	def test_clear_empties_segment_manager(self):
		"""clear() removes all segments from the segment manager."""
		p = make_presenter()
		_add_content_segment(p)
		assert len(p.segment_manager.segments) == 1
		p.clear()
		assert p.segment_manager.segments == []


# ---------------------------------------------------------------------------
# update_last_segment_length()
# ---------------------------------------------------------------------------


class TestUpdateLastSegmentLength:
	"""Tests for HistoryPresenter.update_last_segment_length()."""

	def test_no_segments_does_not_raise(self):
		"""Calling with no segments should be a no-op."""
		p = make_presenter()
		p.update_last_segment_length(100)  # must not raise

	def test_updates_content_segment_with_extra_text(self):
		"""Additional streamed text is added to the last CONTENT segment."""
		p = make_presenter()
		seg = _add_content_segment(p, length=10)
		# Simulate 5 extra chars streamed after the segment was created
		p.update_last_segment_length(15)
		assert seg.length == 15

	def test_no_update_when_not_extra(self):
		"""Length is not changed when last_position equals expected_end."""
		p = make_presenter()
		seg = _add_content_segment(p, length=10)
		p.update_last_segment_length(10)
		assert seg.length == 10

	def test_skips_trailing_suffix_segments(self):
		"""Update finds the last CONTENT segment even with trailing SUFFIXes."""
		p = make_presenter()
		content_seg = _add_content_segment(p, length=10)
		suffix_seg = MessageSegment(
			length=2, kind=MessageSegmentType.SUFFIX, message_block=MagicMock()
		)
		p.segment_manager.append(suffix_seg)
		# expected_end = 10 + 2 = 12; last_position = 17 → extra = 5
		p.update_last_segment_length(17)
		assert content_seg.length == 15
		assert suffix_seg.length == 2  # suffix unchanged


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class TestNavigationDelegation:
	"""Tests for go_to_previous_message and go_to_next_message."""

	def test_go_to_previous_calls_navigate_with_true(self):
		"""go_to_previous_message() calls navigate_message(True)."""
		p = make_presenter()
		p.navigate_message = MagicMock()
		p.go_to_previous_message()
		p.navigate_message.assert_called_once_with(True)

	def test_go_to_next_calls_navigate_with_false(self):
		"""go_to_next_message() calls navigate_message(False)."""
		p = make_presenter()
		p.navigate_message = MagicMock()
		p.go_to_next_message()
		p.navigate_message.assert_called_once_with(False)


class TestNavigateMessage:
	"""Tests for HistoryPresenter.navigate_message()."""

	def test_rings_bell_when_no_segments(self):
		"""navigate_message rings the bell when there are no segments."""
		view = make_view(insertion_point=0)
		p = HistoryPresenter(view)
		# segment_manager is empty → IndexError on previous/next
		p.navigate_message(False)
		view.bell.assert_called_once()

	def test_rings_bell_at_last_message_forward(self):
		"""navigate_message rings bell when already at the last CONTENT block."""
		view = make_view(insertion_point=5)
		p = HistoryPresenter(view)
		_add_content_segment(p, length=10)
		# Only one segment; next() will raise IndexError
		p.navigate_message(False)
		view.bell.assert_called_once()

	def test_sets_insertion_point_on_success(self):
		"""navigate_message moves cursor to start of next CONTENT segment."""
		view = make_view(insertion_point=0)
		p = HistoryPresenter(view)
		# Two CONTENT segments: first [0..10), second [10..15)
		# cursor at 0 → inside first segment; navigate forward lands at seg2
		block_ref = MagicMock(return_value=MagicMock())
		seg1 = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		seg2 = MessageSegment(
			length=5, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		p.segment_manager.append(seg1)
		p.segment_manager.append(seg2)

		with patch("basilisk.config.conf") as mock_conf:
			mock_conf.return_value.conversation.nav_msg_select = False
			# Patch current_msg_content so a_output.handle doesn't fail
			with patch.object(
				type(p),
				"current_msg_content",
				new_callable=lambda: property(lambda self: "content"),
			):
				p.navigate_message(False)

		# SetInsertionPoint should have been called (to position 10)
		view.SetInsertionPoint.assert_called()


# ---------------------------------------------------------------------------
# Speak response
# ---------------------------------------------------------------------------


class TestSpeakResponse:
	"""Tests for speak_response toggle."""

	def test_toggle_flips_state(self):
		"""toggle_speak_response alternates speak_response."""
		p = make_presenter()
		assert p.speak_response is True
		with patch.object(p.a_output, "handle"):
			p.toggle_speak_response()
		assert p.speak_response is False
		with patch.object(p.a_output, "handle"):
			p.toggle_speak_response()
		assert p.speak_response is True

	def test_toggle_announces_enabled(self):
		"""toggle_speak_response announces 'enabled' when turned on."""
		p = make_presenter()
		p.speak_response = False
		with patch.object(p.a_output, "handle") as mock_handle:
			p.toggle_speak_response()
		mock_handle.assert_called_once()
		announced = mock_handle.call_args[0][0]
		assert "enabled" in announced.lower() or "activé" in announced.lower()

	def test_toggle_announces_disabled(self):
		"""toggle_speak_response announces 'disabled' when turned off."""
		p = make_presenter()
		assert p.speak_response is True
		with patch.object(p.a_output, "handle") as mock_handle:
			p.toggle_speak_response()
		announced = mock_handle.call_args[0][0]
		assert (
			"disabled" in announced.lower() or "désactivé" in announced.lower()
		)


class TestShouldSpeakResponse:
	"""Tests for should_speak_response property."""

	def test_false_when_speak_response_off(self):
		"""should_speak_response is False when speak_response is False."""
		view = make_view()
		view.HasFocus.return_value = True
		view.GetTopLevelParent.return_value.IsShown.return_value = True
		p = HistoryPresenter(view)
		p.speak_response = False
		assert p.should_speak_response is False

	def test_false_when_no_focus(self):
		"""should_speak_response is False when neither view nor prompt has focus."""
		view = make_view()
		view.HasFocus.return_value = False
		view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = False
		p = HistoryPresenter(view)
		assert p.should_speak_response is False

	def test_true_when_view_focused_and_shown(self):
		"""should_speak_response is True when view has focus and parent is shown."""
		view = make_view()
		view.HasFocus.return_value = True
		view.GetTopLevelParent.return_value.IsShown.return_value = True
		p = HistoryPresenter(view)
		assert p.should_speak_response is True

	def test_true_when_prompt_focused_and_shown(self):
		"""should_speak_response is True when prompt has focus and parent is shown."""
		view = make_view()
		view.HasFocus.return_value = False
		view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = True
		view.GetTopLevelParent.return_value.IsShown.return_value = True
		p = HistoryPresenter(view)
		assert p.should_speak_response is True

	def test_false_when_top_level_hidden(self):
		"""should_speak_response is False when the top-level window is hidden."""
		view = make_view()
		view.HasFocus.return_value = True
		view.GetTopLevelParent.return_value.IsShown.return_value = False
		p = HistoryPresenter(view)
		assert p.should_speak_response is False


# ---------------------------------------------------------------------------
# handle_stream_chunk()
# ---------------------------------------------------------------------------


class TestHandleStreamChunk:
	"""Tests for HistoryPresenter.handle_stream_chunk()."""

	def test_appends_text_to_view(self):
		"""handle_stream_chunk appends text to the view."""
		view = make_view(insertion_point=0)
		p = HistoryPresenter(view)
		p.speak_response = False
		p.handle_stream_chunk("hello")
		view.AppendText.assert_called_once_with("hello")

	def test_preserves_insertion_point(self):
		"""handle_stream_chunk restores the insertion point."""
		view = make_view(insertion_point=5)
		p = HistoryPresenter(view)
		p.speak_response = False
		p.handle_stream_chunk("world")
		view.SetInsertionPoint.assert_called_with(5)

	def test_buffers_speech_when_speak_response_on(self):
		"""handle_stream_chunk feeds speech buffer when speak_response is True."""
		view = make_view(insertion_point=0)
		view.HasFocus.return_value = True
		view.GetTopLevelParent.return_value.IsShown.return_value = True
		p = HistoryPresenter(view)
		p.speak_response = True
		with patch.object(p.a_output, "handle_stream_buffer") as mock_buf:
			p.handle_stream_chunk("chunk")
		mock_buf.assert_called_once_with(new_text="chunk")

	def test_no_speech_buffer_when_no_focus(self):
		"""handle_stream_chunk does not buffer speech when view has no focus."""
		view = make_view(insertion_point=0)
		view.HasFocus.return_value = False
		view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = False
		p = HistoryPresenter(view)
		p.speak_response = True
		with patch.object(p.a_output, "handle_stream_buffer") as mock_buf:
			p.handle_stream_chunk("chunk")
		mock_buf.assert_not_called()


# ---------------------------------------------------------------------------
# format_citations()
# ---------------------------------------------------------------------------


class TestFormatCitations:
	"""Tests for HistoryPresenter.format_citations() (static method)."""

	def test_empty_list_returns_empty_string(self):
		"""format_citations([]) returns an empty string."""
		assert HistoryPresenter.format_citations([]) == ""

	def test_char_location_citation(self):
		"""Char-location citations include 'C.' prefix and cited text."""
		citations = [
			{
				"type": "char_location",
				"start_char_index": 0,
				"end_char_index": 10,
				"cited_text": "hello",
			}
		]
		result = HistoryPresenter.format_citations(citations)
		assert "hello" in result
		assert "C." in result

	def test_page_location_citation(self):
		"""Page-location citations include 'P.' prefix and cited text."""
		citations = [
			{
				"type": "page_location",
				"start_page_number": 1,
				"end_page_number": 3,
				"cited_text": "world",
			}
		]
		result = HistoryPresenter.format_citations(citations)
		assert "world" in result
		assert "P." in result

	def test_unknown_type_returns_unknown_location(self):
		"""Unknown citation type includes 'Unknown location' text."""
		citations = [{"type": "weird_type", "cited_text": "something"}]
		result = HistoryPresenter.format_citations(citations)
		assert "Unknown location" in result

	def test_multiple_citations_joined_with_separator(self):
		"""Multiple citations are joined with '_--_' separator."""
		citations = [
			{
				"type": "char_location",
				"start_char_index": 0,
				"end_char_index": 5,
				"cited_text": "one",
			},
			{
				"type": "char_location",
				"start_char_index": 10,
				"end_char_index": 15,
				"cited_text": "two",
			},
		]
		result = HistoryPresenter.format_citations(citations)
		assert "_--_" in result
		assert "one" in result
		assert "two" in result

	def test_document_title_included_in_location(self):
		"""Document title appears in the location text when present."""
		citations = [
			{
				"type": "char_location",
				"start_char_index": 0,
				"end_char_index": 5,
				"document_index": 0,
				"document_title": "MyDoc",
				"cited_text": "text",
			}
		]
		result = HistoryPresenter.format_citations(citations)
		assert "MyDoc" in result

	def test_document_index_without_title(self):
		"""Document index appears when there is no title."""
		citations = [
			{
				"type": "char_location",
				"start_char_index": 0,
				"end_char_index": 5,
				"document_index": 2,
				"cited_text": "text",
			}
		]
		result = HistoryPresenter.format_citations(citations)
		assert "2" in result

	def test_citation_without_cited_text_is_skipped(self):
		"""A citation with no cited_text does not appear in the output."""
		citations = [
			{
				"type": "char_location",
				"start_char_index": 0,
				"end_char_index": 5,
			}
		]
		result = HistoryPresenter.format_citations(citations)
		assert result == ""


# ---------------------------------------------------------------------------
# get_current_citations()
# ---------------------------------------------------------------------------


class TestGetCurrentCitations:
	"""Tests for HistoryPresenter.get_current_citations()."""

	def test_returns_empty_when_no_segments(self):
		"""Returns [] when the segment manager is empty (no cursor segment)."""
		view = make_view(insertion_point=0)
		p = HistoryPresenter(view)
		assert p.get_current_citations() == []

	def test_returns_empty_when_block_has_no_response(self):
		"""Returns [] when the current MessageBlock has no response."""
		view = make_view(insertion_point=5)
		p = HistoryPresenter(view)
		block = MagicMock()
		block.response = None
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		p.segment_manager.append(seg)
		assert p.get_current_citations() == []

	def test_returns_citations_from_block_response(self):
		"""Returns the citations list from the current block's response."""
		view = make_view(insertion_point=5)
		p = HistoryPresenter(view)
		citations = [{"type": "char_location", "cited_text": "x"}]
		block = MagicMock()
		block.response.citations = citations
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		p.segment_manager.append(seg)
		assert p.get_current_citations() == citations


# ---------------------------------------------------------------------------
# report_number_of_citations()
# ---------------------------------------------------------------------------


class TestReportNumberOfCitations:
	"""Tests for HistoryPresenter.report_number_of_citations()."""

	def test_no_op_when_no_segments(self):
		"""Does nothing when there are no segments (no ValueError propagated)."""
		view = make_view(insertion_point=0)
		p = HistoryPresenter(view)
		p.report_number_of_citations()  # must not raise
		view.GetParent.return_value.SetStatusText.assert_not_called()

	def test_sets_status_text_with_citation_count(self):
		"""Sets status text with the count when citations exist."""
		view = make_view(insertion_point=5)
		p = HistoryPresenter(view)
		citations = [{"type": "char_location", "cited_text": "a"}] * 3
		block = MagicMock()
		block.response.citations = citations
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		p.segment_manager.append(seg)
		p.report_number_of_citations()
		view.GetParent.return_value.SetStatusText.assert_called_once()
		args = view.GetParent.return_value.SetStatusText.call_args[0]
		assert "3" in args[0]


# ---------------------------------------------------------------------------
# Search management
# ---------------------------------------------------------------------------


class TestSearchManagement:
	"""Tests for search_next() and search_previous()."""

	def test_search_next_opens_dialog_when_none(self):
		"""search_next() calls open_search(FORWARD) when no dialog exists."""
		p = make_presenter()
		p.open_search = MagicMock()
		p.search_next()
		from basilisk.services.search_service import SearchDirection

		p.open_search.assert_called_once_with(SearchDirection.FORWARD)

	def test_search_previous_opens_dialog_when_none(self):
		"""search_previous() calls open_search(BACKWARD) when no dialog exists."""
		p = make_presenter()
		p.open_search = MagicMock()
		p.search_previous()
		from basilisk.services.search_service import SearchDirection

		p.open_search.assert_called_once_with(SearchDirection.BACKWARD)

	def test_search_next_delegates_to_search_presenter(self):
		"""search_next() delegates to _search_presenter when dialog exists."""
		p = make_presenter()
		mock_sp = MagicMock()
		p._search_dialog = MagicMock()
		p._search_presenter = mock_sp
		p.search_next()
		mock_sp.search_next.assert_called_once()

	def test_search_previous_delegates_to_search_presenter(self):
		"""search_previous() delegates to _search_presenter when dialog exists."""
		p = make_presenter()
		mock_sp = MagicMock()
		p._search_dialog = MagicMock()
		p._search_presenter = mock_sp
		p.search_previous()
		mock_sp.search_previous.assert_called_once()
