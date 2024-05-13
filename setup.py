from setuptools import setup

setup(
	message_extractors={
		"basilisk": [("**.py", "python", None), ("**.pyw", "python", None)]
	}
)
