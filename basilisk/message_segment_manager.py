"""Manages text segments and their positions within a conversation's message history.

This module provides functionality to track and navigate through different parts of messages
(prefixes, content, suffixes) in a conversation interface. It helps manage cursor positions,
segment types, and message block references.

Example:
	manager = MessageSegmentManager()
	manager.append(MessageSegment(length=10, kind=MessageSegmentType.PREFIX))
	manager.append(MessageSegment(length=100, kind=MessageSegmentType.CONTENT))
	manager.next(MessageSegmentType.CONTENT)  # Move to content section
"""

import logging
import weakref
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from basilisk.conversation import MessageBlock

log = logging.getLogger(__name__)


class MessageSegmentType(Enum):
	"""Defines the different types of message segments in a conversation."""

	# The introductory part of a message (e.g., role labels)
	PREFIX = "prefix"
	# The main content of a message
	CONTENT = "content"
	# The trailing part of a message (e.g., newlines)
	SUFFIX = "suffix"


@dataclass
class MessageSegment:
	"""Represents a segment of text within a message.

	Attributes:
		length: The length of the segment in characters
		kind: The type of segment (prefix, content, or suffix)
		message_block: Weak reference to the associated MessageBlock
	"""

	length: int
	kind: MessageSegmentType
	message_block: weakref.ReferenceType[MessageBlock] = None


class MessageSegmentManager:
	"""Manages segments of text within a conversation's message history.

	This class provides functionality for tracking, navigating, and manipulating
	different segments of text within a conversation interface. It maintains segment
	positions, handles cursor movement, and manages segment types.

	Attributes:
		segments: List of MessageSegment objects representing the conversation parts
		_current_index: Current position in the segments list
		_absolute_position: Absolute character position in the text

	Example:
		manager = MessageSegmentManager()
		manager.append(MessageSegment(length=10, kind=MessageSegmentType.PREFIX))
		manager.next(MessageSegmentType.CONTENT)  # Move to next content section
	"""

	def __init__(self, positions: Optional[List[MessageSegment]] = None):
		"""Initialize the message segment manager.

		Args:
			positions: Optional list of MessageSegment objects to initialize with. Defaults to empty list if not provided.
		"""
		self.segments: List[MessageSegment] = (
			positions if positions is not None else []
		)
		self._current_index: int = -1
		self._absolute_position: int = -1
		if self.segments:
			self.position = 0
			self._absolute_position = 0

	def previous(
		self, message_position_type: Optional[MessageSegmentType] = None
	) -> int:
		"""Move to the previous segment position.

		Args:
			message_position_type: Optional type of segment to move to. If specified, moves to the previous segment of this type.

		Returns:
			The new absolute position after moving.

		Raises:
			IndexError: If there is no previous position to move to.
		"""
		if self._current_index <= 0:
			raise IndexError("Cannot move to previous position")
		current_position = self._current_index - 1
		if message_position_type is not None:
			while (
				current_position >= 0
				and self.segments[current_position].kind
				!= message_position_type
			):
				current_position -= 1

		if current_position < 0:
			raise IndexError("Cannot move to previous position")
		self.position = current_position
		return self.absolute_position

	def next(
		self, message_position_type: Optional[MessageSegmentType] = None
	) -> int:
		"""Move to the next segment position.

		Args:
			message_position_type: Optional type of segment to move to. If specified, moves to the next segment of this type.

		Returns:
			The new absolute position after moving.

		Raises:
			IndexError: If there is no next position to move to.
		"""
		if self._current_index >= len(self.segments) - 1:
			raise IndexError("Cannot move to next position")
		current_position = self._current_index + 1
		if message_position_type is not None:
			while (
				current_position < len(self.segments)
				and self.segments[current_position].kind
				!= message_position_type
			):
				current_position += 1

		if current_position >= len(self.segments):
			raise IndexError("Cannot move to next position")
		self.position = current_position
		return self.absolute_position

	@property
	def current_segment(self) -> MessageSegment:
		"""Get the current message segment.

		Returns:
			The MessageSegment at the current position.
		"""
		return self.segments[self._current_index]

	@property
	def position(self) -> int:
		"""Get the current segment index.

		Returns:
			The index of the current segment in the segments list.
		"""
		return self._current_index

	@position.setter
	def position(self, value: int):
		"""Set the current segment index.

		Args:
			value: The new segment index to set.

		Raises:
			ValueError: If the index is invalid.
		"""
		if value < 0 or value >= len(self.segments):
			raise ValueError("Invalid current index")
		self._current_index = value
		self._refresh_absolute_position()

	@property
	def absolute_position(self) -> int:
		"""Get the absolute character position in the text.

		Returns:
			The absolute character position counting from the start of the text.
		"""
		return self._absolute_position

	@absolute_position.setter
	def absolute_position(self, absolute_position: int):
		"""Set the absolute character position and update the current segment.

		Args:
			absolute_position: The new absolute character position to set.

		Raises:
			ValueError: If the position is negative.
		"""
		if absolute_position < 0:
			raise ValueError("Invalid absolute position")
		length_sum = 0
		for index, segment in enumerate(self.segments):
			length_sum += segment.length
			if length_sum > absolute_position:
				self.position = index
				self._refresh_absolute_position()
				return
		self.position = len(self.segments) - 1
		self._refresh_absolute_position()

	@property
	def start(self) -> int:
		"""Get the start position of the current segment.

		Returns:
			The absolute character position where the current segment begins.
		"""
		return self.absolute_position - self.current_segment.length

	@property
	def end(self) -> int:
		"""Get the end position of the current segment.

		Returns:
			The absolute character position where the current segment ends.
		"""
		return self.absolute_position

	def insert(self, index: int, value: MessageSegment):
		"""Insert a new segment at the specified position.

		Args:
			index: Position where to insert the new segment
			value: MessageSegment to insert
		"""
		self.segments.insert(index, value)
		self._refresh_absolute_position()

	def append(self, value: MessageSegment):
		"""Append a new segment to the end of the list.

		Args:
			value: MessageSegment to append
		"""
		self.segments.append(value)
		self._refresh_absolute_position()

	def remove(self, value: MessageSegment):
		"""Remove a segment from the list.

		Args:
			value: MessageSegment to remove
		"""
		self.segments.remove(value)
		self._refresh_absolute_position()

	def clear(self):
		"""Clear all segments and reset positions."""
		self.segments.clear()
		self._current_index = -1
		self._absolute_position = -1

	def index(self, value: MessageSegment) -> int:
		"""Get the index of a segment in the list.

		Args:
			value: MessageSegment to find

		Returns:
			The index of the segment in the list

		Raises:
			ValueError: If the segment is not found
		"""
		return self.segments.index(value)

	def focus_content_block(self):
		"""Move focus to the content block from either prefix or suffix.

		If currently in a prefix segment, moves to the next content segment.
		If in a suffix segment, moves to the previous content segment.
		"""
		if self.current_segment.kind == MessageSegmentType.PREFIX:
			self.next(MessageSegmentType.CONTENT)
		elif self.current_segment.kind == MessageSegmentType.SUFFIX:
			self.previous(MessageSegmentType.CONTENT)

	def _refresh_absolute_position(self):
		"""Update the absolute position based on the current segment index.

		Recalculates the absolute character position by summing the lengths
		of all segments up to and including the current segment.
		"""
		self._absolute_position = 0
		for position in self.segments[: self._current_index]:
			self._absolute_position += position.length
		if self._current_index >= 0:
			self._absolute_position += self.segments[self._current_index].length

	def __len__(self) -> int:
		"""Get the number of segments.

		Returns:
			The total number of segments in the manager.
		"""
		return len(self.segments)

	def __str__(self) -> str:
		"""Get a string representation of the manager.

		Returns:
			A string showing the current position and total number of segments.
		"""
		return (
			f"MessageBlockPosition({self._current_index}/{len(self.segments)})"
		)

	def __repr__(self) -> str:
		"""Get a string representation of the manager.

		Returns:
			Same as __str__
		"""
		return self.__str__()

	def __iter__(self):
		"""Get an iterator over the segments.

		Returns:
			Iterator for the segments list.
		"""
		return iter(self.segments)

	def __getitem__(self, index: int) -> MessageSegment:
		"""Get a segment by index.

		Args:
			index: The index of the segment to retrieve

		Returns:
			The MessageSegment at the specified index
		"""
		return self.segments[index]

	def __setitem__(self, index: int, value: MessageSegment):
		"""Set a segment at the specified index.

		Args:
			index: The index where to set the segment
			value: The MessageSegment to set
		"""
		self.segments[index] = value
		self._refresh_absolute_position()

	def __delitem__(self, index: int):
		"""Delete a segment at the specified index.

		Args:
			index: The index of the segment to delete
		"""
		del self.segments[index]
		self._refresh_absolute_position()
