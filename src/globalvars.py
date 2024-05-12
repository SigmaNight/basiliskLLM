import sys
from pathlib import Path

user_data_path = None
if getattr(sys, "frozen", False):
	test_user_data = Path(sys.executable).parent / Path("user_data")
	user_data_path = test_user_data if test_user_data.exists() else None
else:
	test_user_data = Path(__file__).parent / Path("user_data")
	user_data_path = test_user_data if test_user_data.exists() else None


args = None
