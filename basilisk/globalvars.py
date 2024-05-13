import sys
from pathlib import Path

base_path = Path(
	sys.executable if getattr(sys, "frozen", False) else __file__
).parent

user_data_path = (
	base_path / Path("user_data")
	if (base_path / "user_data").exists()
	else None
)

resource_path = base_path / Path("res")

args = None
