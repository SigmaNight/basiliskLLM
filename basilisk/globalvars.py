import sys
from pathlib import Path

if getattr(sys, "frozen", False):
	resource_path = Path(sys.executable).parent / Path("res")
else:
	resource_path = Path(__file__).parent / Path("res")

args = None
