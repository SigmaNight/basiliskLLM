"""Tests for HistoryPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)
from basilisk.presenters.history_presenter import HistoryPresenter
from basilisk.services.search_service import SearchDirection


@pytest.fixture
def mock_view():
	"""Return a mock HistoryMsgTextCtrl view with sensible defaults."""
	view = MagicMock()
	view.GetInsertionPoint.return_value = 0
	view.GetValue.return_value = ""
	view.HasFocus.return_value = False
	view.GetTopLevelParent.return_value.IsShown.return_value = True
	view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = (
		False
	)
	return view


@pytest.fixture
def presenter(mock_view):
	"""Return a HistoryPresenter wired to mock_view."""
	return HistoryPresenter(mock_view)


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


class TestHistoryPresenterInit:
	"""Tests for HistoryPresenter initial state."""

	def test_speak_response_defaults_to_true(self, presenter):
		"""speak_response is True after construction."""
		assert presenter.speak_response is True

	def test_segment_manager_created(self, presenter):
		"""segment_manager is a fresh MessageSegmentManager."""
		assert isinstance(presenter.segment_manager, MessageSegmentManager)
		assert presenter.segment_manager.segments == []

	def test_a_output_created(self, presenter):
		"""a_output is not None after construction."""
		assert presenter.a_output is not None

	def test_search_dialog_initially_none(self, presenter):
		"""_search_dialog is None before first search."""
		assert presenter._search_dialog is None

	def test_search_presenter_initially_none(self, presenter):
		"""_search_presenter is None before first search."""
		assert presenter._search_presenter is None


class TestHistoryPresenterClear:
	"""Tests for HistoryPresenter.clear()."""

	def test_clear_empties_segment_manager(self, presenter):
		"""clear() removes all segments from the segment manager."""
		_add_content_segment(presenter)
		assert len(presenter.segment_manager.segments) == 1
		presenter.clear()
		assert presenter.segment_manager.segments == []


class TestUpdateLastSegmentLength:
	"""Tests for HistoryPresenter.update_last_segment_length()."""

	def test_no_segments_does_not_raise(self, presenter):
		"""Calling with no segments should be a no-op."""
		presenter.update_last_segment_length(100)  # must not raise

	def test_updates_content_segment_with_extra_text(self, presenter):
		"""Additional streamed text is added to the last CONTENT segment."""
		seg = _add_content_segment(presenter, length=10)
		# Simulate 5 extra chars streamed after the segment was created
		presenter.update_last_segment_length(15)
		assert seg.length == 15

	def test_no_update_when_not_extra(self, presenter):
		"""Length is not changed when last_position equals expected_end."""
		seg = _add_content_segment(presenter, length=10)
		presenter.update_last_segment_length(10)
		assert seg.length == 10

	def test_skips_trailing_suffix_segments(self, presenter):
		"""Update finds the last CONTENT segment even with trailing SUFFIXes."""
		content_seg = _add_content_segment(presenter, length=10)
		suffix_seg = MessageSegment(
			length=2, kind=MessageSegmentType.SUFFIX, message_block=MagicMock()
		)
		presenter.segment_manager.append(suffix_seg)
		# expected_end = 10 + 2 = 12; last_position = 17 → extra = 5
		presenter.update_last_segment_length(17)
		assert content_seg.length == 15
		assert suffix_seg.length == 2  # suffix unchanged


class TestNavigationDelegation:
	"""Tests for go_to_previous_message and go_to_next_message."""

	def test_go_to_previous_calls_navigate_with_true(self, presenter):
		"""go_to_previous_message() calls navigate_message(True)."""
		presenter.navigate_message = MagicMock()
		presenter.go_to_previous_message()
		presenter.navigate_message.assert_called_once_with(True)

	def test_go_to_next_calls_navigate_with_false(self, presenter):
		"""go_to_next_message() calls navigate_message(False)."""
		presenter.navigate_message = MagicMock()
		presenter.go_to_next_message()
		presenter.navigate_message.assert_called_once_with(False)


class TestNavigateMessage:
	"""Tests for HistoryPresenter.navigate_message()."""

	def test_rings_bell_when_no_segments(self, presenter, mock_view):
		"""navigate_message rings the bell when there are no segments."""
		# segment_manager is empty → IndexError on previous/next
		presenter.navigate_message(False)
		mock_view.bell.assert_called_once()

	def test_rings_bell_at_last_message_forward(self, presenter, mock_view):
		"""navigate_message rings bell when already at the last CONTENT block."""
		mock_view.GetInsertionPoint.return_value = 5
		_add_content_segment(presenter, length=10)
		# Only one segment; next() will raise IndexError
		presenter.navigate_message(False)
		mock_view.bell.assert_called_once()

	def test_sets_insertion_point_on_success(
		self, presenter, mock_view, mocker
	):
		"""navigate_message moves cursor to start of next CONTENT segment."""
		mock_view.GetInsertionPoint.return_value = 0
		# Two CONTENT segments: first [0..10), second [10..15)
		block_ref = MagicMock(return_value=MagicMock())
		seg1 = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		seg2 = MessageSegment(
			length=5, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		presenter.segment_manager.append(seg1)
		presenter.segment_manager.append(seg2)

		mock_conf = mocker.patch("basilisk.config.conf")
		mock_conf.return_value.conversation.nav_msg_select = False
		mocker.patch.object(
			type(presenter),
			"current_msg_content",
			new_callable=lambda: property(lambda self: "content"),
		)
		presenter.navigate_message(False)

		# SetInsertionPoint should have been called (to position 10)
		mock_view.SetInsertionPoint.assert_called()


class TestSpeakResponse:
	"""Tests for speak_response toggle."""

	def test_toggle_flips_state(self, presenter, mocker):
		"""toggle_speak_response alternates speak_response."""
		assert presenter.speak_response is True
		mocker.patch.object(presenter.a_output, "handle")
		presenter.toggle_speak_response()
		assert presenter.speak_response is False
		presenter.toggle_speak_response()
		assert presenter.speak_response is True

	@pytest.mark.parametrize(
		("initial_speak", "en_word", "fr_word"),
		[(False, "enabled", "activé"), (True, "disabled", "désactivé")],
		ids=["announces_enabled", "announces_disabled"],
	)
	def test_toggle_announces_state(
		self, presenter, mocker, initial_speak, en_word, fr_word
	):
		"""toggle_speak_response announces the new state."""
		presenter.speak_response = initial_speak
		mock_handle = mocker.patch.object(presenter.a_output, "handle")
		presenter.toggle_speak_response()
		mock_handle.assert_called_once()
		announced = mock_handle.call_args[0][0]
		assert en_word in announced.lower() or fr_word in announced.lower()


class TestShouldSpeakResponse:
	"""Tests for should_speak_response property."""

	@pytest.mark.parametrize(
		("speak_response", "has_focus", "prompt_focus", "shown", "expected"),
		[
			(False, True, False, True, False),
			(True, False, False, True, False),
			(True, True, False, True, True),
			(True, False, True, True, True),
			(True, True, False, False, False),
		],
		ids=[
			"speak_off",
			"no_focus",
			"view_focused",
			"prompt_focused",
			"top_hidden",
		],
	)
	def test_should_speak_response(
		self,
		presenter,
		mock_view,
		speak_response,
		has_focus,
		prompt_focus,
		shown,
		expected,
	):
		"""should_speak_response reflects speak settings and focus state."""
		presenter.speak_response = speak_response
		mock_view.HasFocus.return_value = has_focus
		mock_view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = prompt_focus
		mock_view.GetTopLevelParent.return_value.IsShown.return_value = shown
		assert presenter.should_speak_response is expected


class TestHandleStreamChunk:
	"""Tests for HistoryPresenter.handle_stream_chunk()."""

	def test_appends_text_to_view(self, presenter, mock_view):
		"""handle_stream_chunk appends text to the view."""
		presenter.speak_response = False
		presenter.handle_stream_chunk("hello")
		mock_view.AppendText.assert_called_once_with("hello")

	def test_preserves_insertion_point(self, presenter, mock_view):
		"""handle_stream_chunk restores the insertion point."""
		mock_view.GetInsertionPoint.return_value = 5
		presenter.speak_response = False
		presenter.handle_stream_chunk("world")
		mock_view.SetInsertionPoint.assert_called_with(5)

	def test_buffers_speech_when_speak_response_on(
		self, presenter, mock_view, mocker
	):
		"""handle_stream_chunk feeds speech buffer when speak_response is True."""
		mock_view.HasFocus.return_value = True
		mock_view.GetTopLevelParent.return_value.IsShown.return_value = True
		presenter.speak_response = True
		mock_buf = mocker.patch.object(
			presenter.a_output, "handle_stream_buffer"
		)
		presenter.handle_stream_chunk("chunk")
		mock_buf.assert_called_once_with(new_text="chunk")

	def test_no_speech_buffer_when_no_focus(self, presenter, mock_view, mocker):
		"""handle_stream_chunk does not buffer speech when view has no focus."""
		mock_view.HasFocus.return_value = False
		mock_view.GetParent.return_value.prompt_panel.prompt.HasFocus.return_value = False
		presenter.speak_response = True
		mock_buf = mocker.patch.object(
			presenter.a_output, "handle_stream_buffer"
		)
		presenter.handle_stream_chunk("chunk")
		mock_buf.assert_not_called()


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


class TestGetCurrentCitations:
	"""Tests for HistoryPresenter.get_current_citations()."""

	def test_returns_empty_when_no_segments(self, presenter):
		"""Returns [] when the segment manager is empty (no cursor segment)."""
		assert presenter.get_current_citations() == []

	def test_returns_empty_when_block_has_no_response(
		self, presenter, mock_view
	):
		"""Returns [] when the current MessageBlock has no response."""
		mock_view.GetInsertionPoint.return_value = 5
		block = MagicMock()
		block.response = None
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		presenter.segment_manager.append(seg)
		assert presenter.get_current_citations() == []

	def test_returns_citations_from_block_response(self, presenter, mock_view):
		"""Returns the citations list from the current block's response."""
		mock_view.GetInsertionPoint.return_value = 5
		citations = [{"type": "char_location", "cited_text": "x"}]
		block = MagicMock()
		block.response.citations = citations
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		presenter.segment_manager.append(seg)
		assert presenter.get_current_citations() == citations


class TestReportNumberOfCitations:
	"""Tests for HistoryPresenter.report_number_of_citations()."""

	def test_no_op_when_no_segments(self, presenter, mock_view):
		"""Does nothing when there are no segments (no ValueError propagated)."""
		presenter.report_number_of_citations()  # must not raise
		mock_view.GetParent.return_value.SetStatusText.assert_not_called()

	def test_sets_status_text_with_citation_count(self, presenter, mock_view):
		"""Sets status text with the count when citations exist."""
		mock_view.GetInsertionPoint.return_value = 5
		citations = [{"type": "char_location", "cited_text": "a"}] * 3
		block = MagicMock()
		block.response.citations = citations
		block_ref = MagicMock(return_value=block)
		seg = MessageSegment(
			length=10, kind=MessageSegmentType.CONTENT, message_block=block_ref
		)
		presenter.segment_manager.append(seg)
		presenter.report_number_of_citations()
		mock_view.GetParent.return_value.SetStatusText.assert_called_once()
		args = mock_view.GetParent.return_value.SetStatusText.call_args[0]
		assert "3" in args[0]


class TestSearchManagement:
	"""Tests for search_next() and search_previous()."""

	def test_search_next_opens_dialog_when_none(self, presenter):
		"""search_next() calls open_search(FORWARD) when no dialog exists."""
		presenter.open_search = MagicMock()
		presenter.search_next()
		presenter.open_search.assert_called_once_with(SearchDirection.FORWARD)

	def test_search_previous_opens_dialog_when_none(self, presenter):
		"""search_previous() calls open_search(BACKWARD) when no dialog exists."""
		presenter.open_search = MagicMock()
		presenter.search_previous()
		presenter.open_search.assert_called_once_with(SearchDirection.BACKWARD)

	def test_search_next_delegates_to_search_presenter(self, presenter):
		"""search_next() delegates to _search_presenter when dialog exists."""
		mock_sp = MagicMock()
		presenter._search_dialog = MagicMock()
		presenter._search_presenter = mock_sp
		presenter.search_next()
		mock_sp.search_next.assert_called_once()

	def test_search_previous_delegates_to_search_presenter(self, presenter):
		"""search_previous() delegates to _search_presenter when dialog exists."""
		mock_sp = MagicMock()
		presenter._search_dialog = MagicMock()
		presenter._search_presenter = mock_sp
		presenter.search_previous()
		mock_sp.search_previous.assert_called_once()
