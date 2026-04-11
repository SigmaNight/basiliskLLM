"""Setup file for the project."""

from setuptools import setup

setup(
	message_extractors={
		"basilisk": [
			("*.py", "python", None),
			("config/**.py", "python", None),
			("conversation/**.py", "python", None),
			("ipc/**.py", "python", None),
			("presenters/**.py", "python", None),
			("provider_engine/**.py", "python", None),
			("services/**.py", "python", None),
			("singleton_instance/**.py", "python", None),
			("views/**.py", "python", None),
		]
	}
)
