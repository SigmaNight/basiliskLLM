"""Test module for MessageSegmentManager class."""

import pytest

from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)


class TestMessagePositionManagerBasics:
	"""Tests for basic MessageSegmentManager functionality."""

	def test_initial_state(self, segment_manager):
		"""Test the initial state of the MessageSegmentManager."""
		assert segment_manager.position == 0
		assert segment_manager.absolute_position == 0

	def test_str_repr(self, segment_manager):
		"""Test string representation."""
		assert str(segment_manager) == "MessageBlockPosition(0/3)"
		assert repr(segment_manager) == "MessageBlockPosition(0/3)"

	def test_iteration_and_indexing(self, message_segments, segment_manager):
		"""Test iteration and indexing operations."""
		expected = message_segments[0]
		assert segment_manager[0] == expected
		assert len(segment_manager) == len(message_segments)
		for pos in segment_manager:
			assert pos in message_segments

	def test_current_segment(self, message_segments, segment_manager):
		"""Test current segment accessor."""
		assert segment_manager.current_segment == message_segments[0]
		segment_manager.next()
		assert segment_manager.current_segment == message_segments[1]

	def test_out_of_bounds_positions(self, segment_manager):
		"""Test position bounds checking."""
		with pytest.raises(ValueError):
			segment_manager.position = -1
		with pytest.raises(ValueError):
			segment_manager.position = len(segment_manager.segments)

	def test_empty_segments(self):
		"""Test operations on empty segment list."""
		manager = MessageSegmentManager([])
		with pytest.raises(IndexError):
			manager.next()
		with pytest.raises(IndexError):
			manager.previous()

	def test_single_segment(self):
		"""Test operations with single segment."""
		manager = MessageSegmentManager(
			[MessageSegment(length=7, kind=MessageSegmentType.CONTENT)]
		)
		# Test next() with single segment
		with pytest.raises(IndexError):
			manager.next()

		# Test previous() with single segment
		with pytest.raises(IndexError):
			manager.previous()


class TestNavigationMethods:
	"""Tests for MessageSegmentManager navigation methods."""

	def test_next_basic(self, segment_manager):
		"""Test the next() method for basic movement."""
		segment_manager.next()
		assert segment_manager.position == 1
		assert segment_manager.start == 7
		assert segment_manager.end == 7 + 14

	def test_next_with_type(self, segment_manager):
		"""Test the next() method with type filtering."""
		segment_manager.next(MessageSegmentType.CONTENT)
		assert segment_manager.position == 2
		assert segment_manager.start == 7 + 14
		assert segment_manager.end == 7 + 14 + 21

	def test_next_with_type_not_found(self, segment_manager):
		"""Test the next() method with non-existent type."""
		segment_manager.position = len(segment_manager.segments) - 1
		with pytest.raises(IndexError):
			segment_manager.next("nonexistent_type")

	def test_previous_basic(self, segment_manager):
		"""Test the previous() method for basic movement."""
		segment_manager.next()
		segment_manager.next()
		segment_manager.previous()
		assert segment_manager.position == 1
		assert segment_manager.start == 7
		assert segment_manager.end == 7 + 14

	def test_previous_with_type(self, segment_manager):
		"""Test the previous() method with type filtering."""
		segment_manager.next()
		segment_manager.next()
		segment_manager.previous(MessageSegmentType.PREFIX)
		assert segment_manager.position == 1
		assert segment_manager.start == 7
		assert segment_manager.end == 7 + 14

	def test_previous_with_type_not_found(self, segment_manager):
		"""Test the previous() method with non-existent type."""
		with pytest.raises(IndexError):
			segment_manager.previous("nonexistent_type")

	def test_absolute_position_setter(self, segment_manager):
		"""Test absolute position setter."""
		# Test setting to 0
		segment_manager.absolute_position = 0
		assert segment_manager.position == 0
		assert segment_manager.start == 0
		assert segment_manager.end == 7

		# Test setting to boundary
		segment_manager.absolute_position = 7
		assert segment_manager.position == 1
		assert segment_manager.start == 7
		assert segment_manager.end == 7 + 14

		# Test setting to middle of a segment
		segment_manager.absolute_position = 20
		assert segment_manager.position == 1
		assert segment_manager.start == 7
		assert segment_manager.end == 7 + 14

		# Test setting to end
		segment_manager.absolute_position = 7 + 14 + 21
		assert segment_manager.position == 2
		assert segment_manager.absolute_position == 42

		# Test invalid negative value
		with pytest.raises(ValueError):
			segment_manager.absolute_position = -1

		# Test too large value (should clamp to max)
		segment_manager.absolute_position = 1024
		assert segment_manager.absolute_position == 42

	def test_focus_content_block_prefix(self, segment_manager):
		"""Test focusing content block from prefix position."""
		segment_manager.position = 1  # PREFIX segment
		segment_manager.focus_content_block()
		assert segment_manager.position == 2  # Should move to next CONTENT

	def test_focus_content_block_suffix(self, segment_manager):
		"""Test focusing content block from suffix position."""
		# Add a suffix segment
		suffix_segment = MessageSegment(
			length=10, kind=MessageSegmentType.SUFFIX
		)
		segment_manager.append(suffix_segment)

		segment_manager.position = 3  # The new SUFFIX segment
		segment_manager.focus_content_block()
		assert segment_manager.position == 2  # Should move to previous CONTENT

	def test_focus_content_block_noop(self, segment_manager):
		"""Test focusing content block when already on content."""
		segment_manager.focus_content_block()
		assert segment_manager.position == 0  # Should stay on first CONTENT

	def test_multiple_content_segments(self):
		"""Test navigation with multiple content segments."""
		segments = [
			MessageSegment(length=7, kind=MessageSegmentType.CONTENT),
			MessageSegment(length=14, kind=MessageSegmentType.PREFIX),
			MessageSegment(length=21, kind=MessageSegmentType.CONTENT),
			MessageSegment(length=10, kind=MessageSegmentType.CONTENT),
		]
		manager = MessageSegmentManager(segments)

		manager.position = 1  # PREFIX segment
		manager.next(MessageSegmentType.CONTENT)
		assert manager.position == 2  # First CONTENT after PREFIX

		manager.next(MessageSegmentType.CONTENT)
		assert manager.position == 3  # Next CONTENT segment


class TestModificationMethods:
	"""Tests for MessageSegmentManager modification methods."""

	def test_insert(self, segment_manager):
		"""Test segment insertion."""
		new_position = MessageSegment(length=5, kind=MessageSegmentType.PREFIX)
		segment_manager.insert(2, new_position)

		assert segment_manager.segments[2] == new_position
		assert segment_manager.start == 0
		assert segment_manager.end == 7

		# The original third segment should now be fourth with updated offset
		assert segment_manager.segments[3].length == 7 + 14

		# Test position update after insertion
		segment_manager.position = 3
		assert segment_manager.start == 7 + 5 + 14
		assert segment_manager.end == 7 + 5 + 14 + 21

	def test_insert_at_beginning(self, segment_manager):
		"""Test insertion at start of list."""
		segment = MessageSegment(length=5, kind=MessageSegmentType.PREFIX)
		segment_manager.insert(0, segment)

		assert segment_manager[0] == segment
		assert segment_manager.position == 0
		assert segment_manager.absolute_position == 5

	def test_append(self, segment_manager):
		"""Test segment appending."""
		new_position = MessageSegment(length=28, kind=MessageSegmentType.PREFIX)
		segment_manager.append(new_position)

		assert segment_manager.segments[-1] == new_position
		assert segment_manager.start == 0
		assert segment_manager.end == 7

	def test_remove(self, message_segments, segment_manager):
		"""Test segment removal."""
		position_to_remove = message_segments[1]
		segment_manager.remove(position_to_remove)

		assert position_to_remove not in segment_manager.segments
		assert segment_manager.start == 0
		assert segment_manager.end == 7

	def test_clear(self, segment_manager):
		"""Test clearing all segments."""
		segment_manager.clear()

		assert len(segment_manager.segments) == 0
		assert segment_manager.position == -1
		assert segment_manager.absolute_position == -1

	def test_getitem_setitem_delitem(self, segment_manager):
		"""Test item access operations."""
		# Test setting item
		new_segment = MessageSegment(length=50, kind=MessageSegmentType.SUFFIX)
		segment_manager[1] = new_segment
		assert segment_manager[1] == new_segment

		# Test deleting item
		del segment_manager[1]
		assert new_segment not in segment_manager.segments
		assert len(segment_manager) == 2
