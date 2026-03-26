"""Tests for sectioned properties dialog helpers."""

from datetime import datetime

from basilisk.views.sectioned_properties_dialog import (
	format_datetime,
	section_header,
)


class TestSectionHeader:
	"""Tests for section_header."""

	def test_underline_matches_title_length(self):
		"""Underline length equals title length."""
		result = section_header("Overview")
		assert result == ["Overview", "--------"]

	def test_short_title(self):
		"""Short title gets short underline."""
		result = section_header("Hi")
		assert result == ["Hi", "--"]

	def test_long_title(self):
		"""Long title gets long underline."""
		title = "Response consumption"
		result = section_header(title)
		assert result == [title, "-" * len(title)]


class TestFormatDatetime:
	"""Tests for format_datetime."""

	def test_formats_yyyy_mm_dd_hh_mm(self):
		"""Uses %Y-%m-%d %H:%M format."""
		dt = datetime(2026, 3, 15, 16, 46, 41)
		result = format_datetime(dt)
		assert result == "2026-03-15 16:46"
