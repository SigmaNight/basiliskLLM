import sys
from cx_Freeze import setup, Executable
from src.consts import APP_NAME, APP_VERSION

sys.path.append("src")

build_exe_options = {
	"packages": [
		"os",
		"sys",
		"wx",
		"wx.adv",
		"openai",
		"anthropic",
		"configobj",
	],
	"excludes": ["tkinter"],
	"include_files": ["src/res"],
}
if sys.platform == "win32":
	build_exe_options["packages"].extend(["winsound", "win32con"])

base = None
if sys.platform == "win32":
	base = "Win32GUI"

setup(
	name=APP_NAME,
	version=APP_VERSION,
	description="Where LLMs Unite",
	options={"build_exe": build_exe_options},
	executables=[
		Executable(
			"src/main.pyw",
			base=base,
			target_name="basiliskLLM.exe"
			if sys.platform == "win32"
			else "basiliskLLM",
		)
	],
	message_extractors={
		"src": [("**.py", "python", None), ("**.pyw", "python", None)]
	},
)
