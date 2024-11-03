import re
from functools import cache

import accessible_output3.outputs.auto


@cache
def get_accessible_output():
	return accessible_output3.outputs.auto.Auto()


def clear_for_speak(text: str) -> str:
	"""Remove common Markdown elements from text for accessible output."""
	# Remove bold and italics
	text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
	text = re.sub(r"__(.*?)__", r"\1", text)
	text = re.sub(r"\*(.*?)\*", r"\1", text)
	text = re.sub(r"_(.*?)_", r"\1", text)

	# Remove links but keep the link text
	text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)

	# Remove images (keep alt text)
	text = re.sub(r"!\[([^\]]*)\]\([^\)]+\)", r"\1", text)

	# Remove headers
	text = re.sub(r"^#{1,6} (.*)", r"\1", text, flags=re.MULTILINE)

	# Remove blockquotes
	text = re.sub(r"^> (.*)", r"\1", text, flags=re.MULTILINE)

	# Remove horizontal rules
	text = re.sub(r"^-{3,}$", r"", text, flags=re.MULTILINE)

	return text
