from cx_Freeze import setup


setup(
	message_extractors={
		"src": [("**.py", "python", None), ("**.pyw", "python", None)]
	}
)
