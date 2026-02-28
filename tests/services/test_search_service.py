"""Tests for SearchService."""

from basilisk.services.search_service import (
	SearchMode,
	SearchService,
	adjust_utf16_position,
)


class TestCompilePattern:
	"""Tests for SearchService.compile_pattern."""

	def test_plain_text_escapes_regex_chars(self):
		"""PLAIN_TEXT mode should escape regex metacharacters."""
		pattern = SearchService.compile_pattern(
			"a.b", SearchMode.PLAIN_TEXT, True, False
		)
		assert pattern.search("a.b")
		assert not pattern.search("axb")

	def test_extended_replaces_newline(self):
		r"""EXTENDED mode should replace \n with a real newline."""
		pattern = SearchService.compile_pattern(
			r"\n", SearchMode.EXTENDED, True, False
		)
		assert pattern.search("hello\nworld")
		assert not pattern.search("hello world")

	def test_extended_replaces_tab(self):
		r"""EXTENDED mode should replace \t with a real tab."""
		pattern = SearchService.compile_pattern(
			r"\t", SearchMode.EXTENDED, True, False
		)
		assert pattern.search("col1\tcol2")
		assert not pattern.search("col1 col2")

	def test_regex_raw(self):
		"""REGEX mode should compile the pattern as-is."""
		pattern = SearchService.compile_pattern(
			r"\d+", SearchMode.REGEX, True, False
		)
		assert pattern.search("abc123")
		assert not pattern.search("abcdef")

	def test_case_insensitive(self):
		"""case_sensitive=False should set IGNORECASE flag."""
		pattern = SearchService.compile_pattern(
			"hello", SearchMode.PLAIN_TEXT, False, False
		)
		assert pattern.search("HELLO")
		assert pattern.search("Hello")

	def test_case_sensitive(self):
		"""case_sensitive=True should NOT set IGNORECASE flag."""
		pattern = SearchService.compile_pattern(
			"hello", SearchMode.PLAIN_TEXT, True, False
		)
		assert pattern.search("hello")
		assert not pattern.search("HELLO")

	def test_dot_all_on_with_regex(self):
		"""dot_all=True with REGEX mode should set DOTALL flag."""
		pattern = SearchService.compile_pattern(
			"a.b", SearchMode.REGEX, True, True
		)
		assert pattern.search("a\nb")

	def test_dot_all_off_with_regex(self):
		"""dot_all=False with REGEX mode should NOT match newline with dot."""
		pattern = SearchService.compile_pattern(
			"a.b", SearchMode.REGEX, True, False
		)
		assert not pattern.search("a\nb")

	def test_dot_all_ignored_in_plain_text(self):
		"""dot_all should have no effect in PLAIN_TEXT mode."""
		pattern = SearchService.compile_pattern(
			"a.b", SearchMode.PLAIN_TEXT, True, True
		)
		# The dot is escaped in PLAIN_TEXT, so "a\nb" should NOT match
		assert not pattern.search("a\nb")
		assert pattern.search("a.b")

	def test_dot_all_ignored_in_extended(self):
		"""dot_all should have no effect in EXTENDED mode."""
		pattern = SearchService.compile_pattern(
			"a.b", SearchMode.EXTENDED, True, True
		)
		# dot is NOT escaped in EXTENDED mode, but DOTALL flag is not set
		assert not pattern.search("a\nb")
		assert pattern.search("axb")


class TestFindAllMatches:
	"""Tests for SearchService.find_all_matches."""

	def test_no_result(self):
		"""Should return empty list when no match exists."""
		matches = SearchService.find_all_matches(
			"hello world", "xyz", SearchMode.PLAIN_TEXT, True, False
		)
		assert matches == []

	def test_one_result(self):
		"""Should return one match when there is exactly one occurrence."""
		matches = SearchService.find_all_matches(
			"hello world", "world", SearchMode.PLAIN_TEXT, True, False
		)
		assert len(matches) == 1
		assert matches[0].group() == "world"

	def test_multiple_results(self):
		"""Should return all occurrences."""
		matches = SearchService.find_all_matches(
			"aaa", "a", SearchMode.PLAIN_TEXT, True, False
		)
		assert len(matches) == 3

	def test_plain_text_literal_dot(self):
		"""PLAIN_TEXT should treat '.' as a literal dot, not a wildcard."""
		matches = SearchService.find_all_matches(
			"a.b axb", "a.b", SearchMode.PLAIN_TEXT, True, False
		)
		assert len(matches) == 1
		assert matches[0].group() == "a.b"

	def test_case_insensitive(self):
		"""case_sensitive=False should find matches regardless of case."""
		matches = SearchService.find_all_matches(
			"Hello WORLD hello", "hello", SearchMode.PLAIN_TEXT, False, False
		)
		assert len(matches) == 2

	def test_regex_mode(self):
		"""REGEX mode should allow regex patterns."""
		matches = SearchService.find_all_matches(
			"cat bat sat", r"[cbs]at", SearchMode.REGEX, True, False
		)
		assert len(matches) == 3


class TestAdjustUtf16Position:
	"""Tests for adjust_utf16_position."""

	def test_ascii_no_adjustment(self):
		"""Pure ASCII text should not change the position."""
		text = "hello world"
		assert adjust_utf16_position(text, 5) == 5

	def test_surrogate_pair_adjusts_position(self):
		"""A character outside BMP (emoji) should increase position by 1."""
		# U+1F600 (GRINNING FACE) is outside BMP, ord() >= 0x10000
		text = "\U0001f600abc"
		# Position 1 (after the emoji) should be adjusted by +1
		result = adjust_utf16_position(text, 1)
		assert result == 2

	def test_newline_adjusts_position(self):
		"""A newline character should increase position by 1."""
		text = "hello\nworld"
		# Position 6 (after newline) should be adjusted by +1
		result = adjust_utf16_position(text, 6)
		assert result == 7

	def test_reverse_subtracts_adjustment(self):
		"""reverse=True should subtract the surrogate offset (UTF-16 → Python).

		For "\U0001f600abc" the emoji occupies two UTF-16 code units.
		- forward (Python→UTF-16): position 1 → 2 (add 1 for the surrogate pair)
		- reverse (UTF-16→Python): position 1 → 0 (subtract 1 for the surrogate pair)
		"""
		text = "\U0001f600abc"
		# reverse=False: Python position 1 (after emoji) → UTF-16 position 2
		result_forward = adjust_utf16_position(text, 1, reverse=False)
		assert result_forward == 2
		# reverse=True: UTF-16 position 1 (inside emoji surrogate pair) → Python position 0
		result_reverse = adjust_utf16_position(text, 1, reverse=True)
		assert result_reverse == 0
