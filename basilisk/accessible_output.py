"""Functions for interacting with the Accessible Output library."""

import logging
import re
from functools import cache

import accessible_output3.outputs.auto

from basilisk.decorators import measure_time

log = logging.getLogger(__name__)


@cache
@measure_time
def get_accessible_output() -> accessible_output3.outputs.auto.Auto:
	"""Initialize the Accessible Output library. Cache the result for future calls.

	Returns:
		An instance of the Accessible Output library
	"""
	log.info("Initializing Accessible Output")
	return accessible_output3.outputs.auto.Auto()


@cache
def get_clean_steps() -> list[tuple[re.Pattern | str]]:
	"""Return a list of regex patterns and their replacements to clean text.

	Returns:
		A list of tuples containing a compiled regex pattern and its replacement string.
	"""
	log.debug("Initializing clean steps")
	return [
		# Remove bold and italics
		(re.compile(r"\*\*(.*?)\*\*"), r"\1"),
		(re.compile(r"__(.*?)__"), r"\1"),
		(re.compile(r"\*(.*?)\*"), r"\1"),
		(re.compile(r"_(.*?)_"), r"\1"),
		# Remove links but keep the link text
		(re.compile(r"\[([^\]]+)\]\([^\)]+\)"), r"\1"),
		# Remove images (keep alt text)
		(re.compile(r"!\[([^\]]*)\]\([^\)]+\)"), r"\1"),
		# Remove headers
		(re.compile(r"^#{1,6} (.*)", re.MULTILINE), r"\1"),
		# Remove blockquotes
		(re.compile(r"^> (.*)", re.MULTILINE), r"\1"),
		# Remove horizontal rules
		(re.compile(r"^-{3,}$", re.MULTILINE), ""),
	]


def clear_for_speak(text: str) -> str:
	"""Remove common Markdown elements from text for accessible output.

	Args:
		text: The text to clean

	Returns:
		The cleaned text
	"""
	for pattern, replacement in get_clean_steps():
		text = pattern.sub(replacement, text)
	return text
