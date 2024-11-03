import re

import accessible_output3.outputs.auto

accessible_output = None


def init_accessible_output():
	global accessible_output
	accessible_output = accessible_output3.outputs.auto.Auto()


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
