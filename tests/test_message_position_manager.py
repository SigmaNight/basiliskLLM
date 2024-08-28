import unittest

from basilisk.message_segment_manager import (
	MessageSegment,
	MessageSegmentManager,
	MessageSegmentType,
)


class TestMessagePositionManager(unittest.TestCase):
	def setUp(self):
		self.segments = [
			MessageSegment(length=7, kind=MessageSegmentType.CONTENT),
			MessageSegment(length=14, kind=MessageSegmentType.PREFIX),
			MessageSegment(length=21, kind=MessageSegmentType.CONTENT),
		]
		self.manager = MessageSegmentManager(self.segments)

	def test_initial_state(self):
		self.assertEqual(self.manager.position, 0, "Initial index should be 0")
		self.assertEqual(
			self.manager.absolute_position,
			0,
			"Initial absolute position should be 0",
		)

	def test_next(self):
		self.manager.next()
		self.assertEqual(self.manager.position, 1)
		self.assertEqual(self.manager.start, 7)
		self.assertEqual(self.manager.end, 7 + 14)

	def test_next_with_type(self):
		self.manager.next(MessageSegmentType.CONTENT)
		self.assertEqual(self.manager.position, 2)
		self.assertEqual(self.manager.start, 7 + 14)
		self.assertEqual(self.manager.end, 7 + 14 + 21)

	def test_next_with_type_not_found(self):
		self.manager.position = len(self.segments) - 1
		with self.assertRaises(IndexError):
			self.manager.next("nonexistent_type")

	def test_previous(self):
		self.manager.next()
		self.manager.next()
		self.manager.previous()
		self.assertEqual(self.manager.position, 1)
		self.assertEqual(self.manager.start, 7)
		self.assertEqual(self.manager.end, 7 + 14)

	def test_previous_with_type(self):
		self.manager.next()
		self.manager.next()
		self.manager.previous(MessageSegmentType.PREFIX)
		self.assertEqual(self.manager.position, 1)
		self.assertEqual(self.manager.start, 7)
		self.assertEqual(self.manager.end, 7 + 14)

	def test_previous_with_type_not_found(self):
		with self.assertRaises(IndexError):
			self.manager.previous("nonexistent_type")

	def test_insert(self):
		new_position = MessageSegment(length=5, kind=MessageSegmentType.PREFIX)
		self.manager.insert(2, new_position)
		self.assertEqual(self.manager.segments[2], new_position)
		self.assertEqual(self.manager.start, 0)
		self.assertEqual(self.manager.end, 7)
		self.assertEqual(self.manager.segments[3].length, 7 + 14)
		self.manager.position = 3
		self.assertEqual(self.manager.start, 7 + 5 + 14)
		self.assertEqual(self.manager.end, 7 + 5 + 14 + 21)

	def test_append(self):
		new_position = MessageSegment(length=28, kind=MessageSegmentType.PREFIX)
		self.manager.append(new_position)
		self.assertEqual(self.manager.segments[-1], new_position)
		self.assertEqual(self.manager.start, 0)
		self.assertEqual(self.manager.end, 7)

	def test_remove(self):
		position_to_remove = self.segments[1]
		self.manager.remove(position_to_remove)
		self.assertNotIn(position_to_remove, self.manager.segments)
		self.assertEqual(self.manager.start, 0)
		self.assertEqual(self.manager.end, 7)

	def test_absolute_position_setter(self):
		self.manager.absolute_position = 0
		self.assertEqual(self.manager.position, 0)
		self.assertEqual(self.manager.start, 0)
		self.assertEqual(self.manager.end, 7)
		self.manager.absolute_position = 7
		self.assertEqual(self.manager.position, 1)
		self.assertEqual(self.manager.start, 7)
		self.assertEqual(self.manager.end, 7 + 14)
		self.manager.absolute_position = 20
		self.assertEqual(self.manager.position, 1)
		self.assertEqual(self.manager.start, 7)
		self.assertEqual(self.manager.end, 7 + 14)
		self.manager.absolute_position = 7 + 14 + 21
		self.assertEqual(self.manager.position, 2)
		self.assertEqual(self.manager.absolute_position, 42)
		with self.assertRaises(ValueError):
			self.manager.absolute_position = -1
		self.manager.absolute_position = 1024
		self.assertEqual(self.manager.absolute_position, 42)

	def test_out_of_bounds_positions(self):
		with self.assertRaises(ValueError):
			self.manager.position = -1
		with self.assertRaises(ValueError):
			self.manager.position = len(self.segments)

	def test_str_repr(self):
		self.assertEqual(str(self.manager), "MessageBlockPosition(0/3)")
		self.assertEqual(repr(self.manager), "MessageBlockPosition(0/3)")

	def test_iteration_and_indexing(self):
		expected = self.segments[0]
		self.assertEqual(self.manager[0], expected)
		self.assertEqual(len(self.manager), len(self.segments))
		for pos in self.manager:
			self.assertIn(pos, self.segments)

	def test_focus_content_block_prefix(self):
		self.manager.position = 1
		self.manager.focus_content_block()
		self.assertEqual(self.manager.position, 2)

	def test_focus_content_block_suffix(self):
		self.manager.append(
			MessageSegment(length=10, kind=MessageSegmentType.SUFFIX)
		)
		self.manager.position = 3
		self.manager.focus_content_block()
		self.assertEqual(self.manager.position, 2)

	def test_focus_content_block_noop(self):
		self.manager.focus_content_block()
		self.assertEqual(self.manager.position, 0)

	def test_empty_segments(self):
		manager = MessageSegmentManager([])
		with self.assertRaises(IndexError):
			manager.next()
		with self.assertRaises(IndexError):
			manager.previous()

	def test_single_segment_next(self):
		manager = MessageSegmentManager(
			[MessageSegment(length=7, kind=MessageSegmentType.CONTENT)]
		)
		with self.assertRaises(IndexError):
			manager.next()

	def test_single_segment_previous(self):
		manager = MessageSegmentManager(
			[MessageSegment(length=7, kind=MessageSegmentType.CONTENT)]
		)
		with self.assertRaises(IndexError):
			manager.previous()

	def test_current_segment(self):
		self.assertEqual(self.manager.current_segment, self.segments[0])
		self.manager.next()
		self.assertEqual(self.manager.current_segment, self.segments[1])

	def test_position_setter_invalid(self):
		with self.assertRaises(ValueError):
			self.manager.position = -1
		with self.assertRaises(ValueError):
			self.manager.position = 100

	def test_absolute_position_setter_large(self):
		self.manager.absolute_position = 999
		self.assertEqual(self.manager.absolute_position, 42)

	def test_getitem_setitem_delitem(self):
		segment = MessageSegment(length=50, kind=MessageSegmentType.SUFFIX)
		self.manager[1] = segment
		self.assertEqual(self.manager[1], segment)

		del self.manager[1]
		self.assertNotIn(segment, self.manager.segments)
		self.assertEqual(len(self.manager), 2)

	def test_clear(self):
		self.manager.clear()
		self.assertEqual(len(self.manager.segments), 0)
		self.assertEqual(self.manager.position, -1)
		self.assertEqual(self.manager.absolute_position, -1)

	def test_insert_at_beginning(self):
		segment = MessageSegment(length=5, kind=MessageSegmentType.PREFIX)
		self.manager.insert(0, segment)
		self.assertEqual(self.manager[0], segment)
		self.assertEqual(self.manager.position, 0)
		self.assertEqual(self.manager.absolute_position, 5)

	def test_multiple_content_segments(self):
		self.segments.append(
			MessageSegment(length=10, kind=MessageSegmentType.CONTENT)
		)
		self.manager = MessageSegmentManager(self.segments)
		self.manager.position = 1
		self.manager.next(MessageSegmentType.CONTENT)
		self.assertEqual(self.manager.position, 2)
		self.manager.next(MessageSegmentType.CONTENT)
		self.assertEqual(self.manager.position, 3)


if __name__ == "__main__":
	unittest.main()
