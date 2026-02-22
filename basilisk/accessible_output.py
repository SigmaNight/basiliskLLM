"""Functions for interacting with the Accessible Output library."""

import logging
import re
from functools import cached_property

import accessible_output3.outputs.auto

import basilisk.config as config
from basilisk.completion_handler import COMMON_PATTERN
from basilisk.decorators import measure_time

log = logging.getLogger(__name__)
RE_SPEECH_STREAM_BUFFER = re.compile(rf"{COMMON_PATTERN}")


class AccessibleOutputHandler:
	"""Handles accessible output and streaming for screen readers.

	This class provides common functionality for handling accessible output
	and speech streaming that can be shared between different UI components.
	"""

	def __init__(self):
		"""Initialize the accessible output handler."""
		self._accessible_output = None
		self._init_accessible_output(True)
		self.speech_stream_buffer: str = ""

	@cached_property
	def clean_steps(self) -> list[tuple[re.Pattern | str]]:
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

	@property
	def use_accessible_output(self) -> bool:
		"""Check if accessible output is enabled in the configuration."""
		return config.conf().conversation.use_accessible_output

	@measure_time
	def _init_accessible_output(self, display_log: bool) -> None:
		"""Initialize the Accessible Output library."""
		if not self.use_accessible_output:
			if display_log:
				log.warning(
					"Accessible output is disabled in the configuration."
				)
			self._accessible_output = None
			return
		log.info("Initializing Accessible Output")
		self._accessible_output = accessible_output3.outputs.auto.Auto()
		log.info("Accessible Output initialized successfully.")

	@property
	def accessible_output(self) -> accessible_output3.outputs.auto.Auto:
		"""Get the Accessible Output instance, initializing it if necessary."""
		if self._accessible_output is None:
			self._init_accessible_output(False)
		return self._accessible_output

	def clear_for_speak(self, text: str) -> str:
		"""Remove common Markdown elements from text for accessible output.

		Args:
			text: The text to clean

		Returns:
			The cleaned text
		"""
		for pattern, replacement in self.clean_steps:
			text = pattern.sub(replacement, text)
		return text

	def handle(
		self,
		text: str,
		braille: bool = False,
		force: bool = False,
		clear_for_speak: bool = True,
	):
		"""Handle accessible output for screen readers, including both speech and braille output.

		Args:
			text: Text to output
			braille: Whether to use braille output
			force: Whether to force output
			clear_for_speak: Whether to clean the text for speech output
		"""
		if force and self._accessible_output is None:
			self._init_accessible_output(True)
		if (
			(not force and not self.use_accessible_output)
			or not isinstance(text, str)
			or not text.strip()
		):
			return
		if braille:
			try:
				self.accessible_output.braille(text)
			except Exception as e:
				log.error(
					"Failed to output text to braille display", exc_info=e
				)
		try:
			if clear_for_speak:
				text = self.clear_for_speak(text)
			self.accessible_output.speak(text)
		except Exception as e:
			log.error("Failed to output text to screen reader", exc_info=e)

	def handle_stream_buffer(self, new_text: str = ""):
		"""Processes incoming speech stream text and updates the buffer accordingly.

		If the input `new_text` is not a valid string or is empty, it forces flushing the current buffer to the accessible output handler.
		If `new_text` contains punctuation or newlines, it processes text up to the last
		occurrence, sends that portion to the output handler, and retains the remaining
		text in the buffer.

		Args:
			new_text: The new incoming text to process. If not a string or empty, the buffer is processed immediately.
		"""
		if not isinstance(new_text, str) or not new_text:
			if self.speech_stream_buffer:
				self.handle(self.speech_stream_buffer, clear_for_speak=True)
				self.speech_stream_buffer = ""
			return

		try:
			# Find the last occurrence of punctuation mark or newline
			matches = list(RE_SPEECH_STREAM_BUFFER.finditer(new_text))
			if matches:
				# Use the last match
				last_match = matches[-1]
				part_to_handle = (
					self.speech_stream_buffer + new_text[: last_match.end()]
				)
				remaining_text = new_text[last_match.end() :]

				if part_to_handle:
					self.handle(part_to_handle, clear_for_speak=True)

				# Update the buffer with the remaining text
				self.speech_stream_buffer = remaining_text.lstrip()
			else:
				# Concatenate new text to the buffer if no punctuation is found
				self.speech_stream_buffer += new_text
		except re.error as e:
			log.error("Regex error in _handle_speech_stream_buffer: %s", e)
			# Fallback: treat the entire text as a single chunk
			self.speech_stream_buffer += new_text
