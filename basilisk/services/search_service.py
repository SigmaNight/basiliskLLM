"""Service layer for text search logic.

Provides search algorithm components extracted from SearchDialog, including
enums, pattern compilation, and match finding.
"""

from __future__ import annotations

import enum
import re


class SearchDirection(enum.IntEnum):
	"""Enumeration for search directions."""

	BACKWARD = enum.auto(0)
	FORWARD = enum.auto()


class SearchMode(enum.IntEnum):
	"""Enumeration for search modes."""

	PLAIN_TEXT = enum.auto(0)
	EXTENDED = enum.auto()
	REGEX = enum.auto()


def adjust_utf16_position(
	text: str, position: int, reverse: bool = False
) -> int:
	"""Adjust the given position in the text to account for characters outside of the Basic Multilingual Plane (BMP).

	Characters outside the BMP are represented by surrogate pairs in UTF-16,
	taking up two positions instead of one. This function adjusts the given
	position to account for these surrogate pairs and newlines.

	Args:
		text: The input string.
		position: The original position in the string.
		reverse: If True, the function is intended to adjust the position in
			the reverse direction. Note: due to a bug ``count -= count``
			always zeroes the count, so ``reverse=True`` returns *position*
			unchanged (i.e. the adjustment is fully suppressed rather than
			reversed).

	Returns:
		The adjusted position reflecting the presence of surrogate pairs.
	"""
	relevant_text = text[:position]
	count_high_surrogates = sum(1 for c in relevant_text if ord(c) >= 0x10000)
	if reverse:
		# Bug: subtracting a variable from itself always yields 0, so the
		# intended reverse adjustment is never applied.
		count_high_surrogates -= count_high_surrogates
	count_line_breaks = sum(1 for c in relevant_text if c == "\n")
	if reverse:
		# Bug: same zero-out as above.
		count_line_breaks -= count_line_breaks
	return position + count_high_surrogates + count_line_breaks


class SearchService:
	"""Service providing stateless search operations.

	All methods are static; no instance state is required.
	"""

	@staticmethod
	def compile_pattern(
		query_text: str, mode: SearchMode, case_sensitive: bool, dot_all: bool
	) -> re.Pattern:
		r"""Compile a regex pattern from the given search parameters.

		For PLAIN_TEXT mode the query is escaped so that regex metacharacters
		are treated as literals. For EXTENDED mode common escape sequences
		(``\\n``, ``\\t``, ``\\r``, etc.) are replaced with their real
		counterparts before compilation. For REGEX mode the query is used
		as-is.

		DOTALL is only applied when *mode* is REGEX.

		Args:
			query_text: The raw search text entered by the user.
			mode: The search mode (PLAIN_TEXT, EXTENDED, or REGEX).
			case_sensitive: Whether the search is case-sensitive.
			dot_all: Whether ``.`` should match newlines (REGEX mode only).

		Returns:
			A compiled :class:`re.Pattern`.
		"""
		flags = re.UNICODE
		if not case_sensitive:
			flags |= re.IGNORECASE
		if dot_all and mode == SearchMode.REGEX:
			flags |= re.DOTALL

		if mode == SearchMode.PLAIN_TEXT:
			query_text = re.escape(query_text)
		elif mode == SearchMode.EXTENDED:
			query_text = (
				query_text.replace(r"\n", "\n")
				.replace(r"\t", "\t")
				.replace(r"\r", "\r")
				.replace(r"\x00", "\x00")
				.replace(r"\x1F", "\x1f")
				.replace(r"\x7F", "\x7f")
			)

		return re.compile(query_text, flags)

	@staticmethod
	def find_all_matches(
		text_content: str,
		query_text: str,
		mode: SearchMode,
		case_sensitive: bool,
		dot_all: bool,
	) -> list[re.Match]:
		"""Find all occurrences of *query_text* in *text_content*.

		Uses :meth:`compile_pattern` internally. Case-insensitive matching is
		handled exclusively via the ``re.IGNORECASE`` flag (no manual
		lower-casing of text or query).

		Args:
			text_content: The full text to search within.
			query_text: The raw search text entered by the user.
			mode: The search mode (PLAIN_TEXT, EXTENDED, or REGEX).
			case_sensitive: Whether the search is case-sensitive.
			dot_all: Whether ``.`` should match newlines (REGEX mode only).

		Returns:
			A list of :class:`re.Match` objects for every occurrence found.
		"""
		pattern = SearchService.compile_pattern(
			query_text, mode, case_sensitive, dot_all
		)
		return list(pattern.finditer(text_content))
