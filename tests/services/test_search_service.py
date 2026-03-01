"""Tests for SearchService."""

import pytest

from basilisk.services.search_service import (
	SearchMode,
	SearchService,
	adjust_utf16_position,
)


class TestCompilePattern:
	"""Tests for SearchService.compile_pattern."""

	@pytest.mark.parametrize(
		("pattern_str", "mode", "match_text", "no_match_text"),
		[
			("a.b", SearchMode.PLAIN_TEXT, "a.b", "axb"),
			(r"\n", SearchMode.EXTENDED, "hello\nworld", "hello world"),
			(r"\t", SearchMode.EXTENDED, "col1\tcol2", "col1 col2"),
			(r"\d+", SearchMode.REGEX, "abc123", "abcdef"),
		],
		ids=["plain_escape", "ext_newline", "ext_tab", "regex_raw"],
	)
	def test_pattern_mode(self, pattern_str, mode, match_text, no_match_text):
		"""Pattern matches the expected text and not the counter-example."""
		pattern = SearchService.compile_pattern(pattern_str, mode, True, False)
		assert pattern.search(match_text)
		assert not pattern.search(no_match_text)

	@pytest.mark.parametrize(
		("case_sensitive", "text", "should_match"),
		[
			(False, "HELLO", True),
			(False, "Hello", True),
			(True, "hello", True),
			(True, "HELLO", False),
		],
		ids=["insens_upper", "insens_mixed", "sens_lower", "sens_upper"],
	)
	def test_case_sensitivity(self, case_sensitive, text, should_match):
		"""Case-sensitivity flag controls IGNORECASE behaviour."""
		pattern = SearchService.compile_pattern(
			"hello", SearchMode.PLAIN_TEXT, case_sensitive, False
		)
		assert bool(pattern.search(text)) is should_match

	@pytest.mark.parametrize(
		("mode", "dot_all", "text", "should_match"),
		[
			(SearchMode.REGEX, True, "a\nb", True),
			(SearchMode.REGEX, False, "a\nb", False),
			(SearchMode.PLAIN_TEXT, True, "a\nb", False),
			(SearchMode.PLAIN_TEXT, True, "a.b", True),
			(SearchMode.EXTENDED, True, "a\nb", False),
			(SearchMode.EXTENDED, True, "axb", True),
		],
		ids=[
			"regex_on",
			"regex_off",
			"plain_no_nl",
			"plain_dot",
			"ext_no_nl",
			"ext_dot",
		],
	)
	def test_dot_all_flag(self, mode, dot_all, text, should_match):
		r"""dot_all=True sets DOTALL only in REGEX mode; ignored otherwise."""
		pattern = SearchService.compile_pattern("a.b", mode, True, dot_all)
		assert bool(pattern.search(text)) is should_match


class TestFindAllMatches:
	"""Tests for SearchService.find_all_matches."""

	@pytest.mark.parametrize(
		(
			"text",
			"pat",
			"mode",
			"cs",
			"dot_all",
			"expected_count",
			"first_match",
		),
		[
			("hello world", "xyz", SearchMode.PLAIN_TEXT, True, False, 0, None),
			(
				"hello world",
				"world",
				SearchMode.PLAIN_TEXT,
				True,
				False,
				1,
				"world",
			),
			("aaa", "a", SearchMode.PLAIN_TEXT, True, False, 3, None),
			("a.b axb", "a.b", SearchMode.PLAIN_TEXT, True, False, 1, "a.b"),
			(
				"Hello WORLD hello",
				"hello",
				SearchMode.PLAIN_TEXT,
				False,
				False,
				2,
				None,
			),
			("cat bat sat", r"[cbs]at", SearchMode.REGEX, True, False, 3, None),
		],
		ids=[
			"no_match",
			"one",
			"multiple",
			"literal_dot",
			"case_insens",
			"regex",
		],
	)
	def test_find_all_matches(
		self, text, pat, mode, cs, dot_all, expected_count, first_match
	):
		"""find_all_matches returns correct results for varied inputs."""
		matches = SearchService.find_all_matches(text, pat, mode, cs, dot_all)
		assert len(matches) == expected_count
		if first_match is not None:
			assert matches[0].group() == first_match


class TestAdjustUtf16Position:
	"""Tests for adjust_utf16_position."""

	@pytest.mark.parametrize(
		("text", "pos", "reverse", "expected"),
		[
			("hello world", 5, False, 5),
			("\U0001f600abc", 1, False, 2),
			("hello\nworld", 6, False, 7),
			("\U0001f600abc", 1, True, 0),
		],
		ids=["ascii", "surrogate_fwd", "newline_fwd", "surrogate_rev"],
	)
	def test_utf16_adjust(self, text, pos, reverse, expected):
		"""adjust_utf16_position returns the correct adjusted index."""
		assert adjust_utf16_position(text, pos, reverse) == expected
