from cx_Freeze import setup
from src.consts import APP_VERSION


setup(
	version=APP_VERSION,
	message_extractors={
		"src": [("**.py", "python", None), ("**.pyw", "python", None)]
	},
)
