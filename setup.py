"""Setup file for the project."""

from setuptools import setup

setup(
	message_extractors={
		"basilisk": [
			("*.py", "python", None),
			("gui/**.py", "python", None),
			("provider_engine/**.py", "python", None),
		]
	}
)
