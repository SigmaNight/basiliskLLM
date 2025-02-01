"""global variables for the basilisk application.

This module contains global variables that are used throughout the application. These variables are used to store information that is shared between different parts of the application, such as configuration settings, user data, and resource paths.
"""

import sys
from pathlib import Path

# fase directory of the application executable
base_path = Path(
	sys.executable if getattr(sys, "frozen", False) else __file__
).parent

# application configuration inside the base directory (usefull for portable installations)
user_data_path = (
	base_path / Path("user_data")
	if (base_path / "user_data").exists()
	else None
)

# resource directory present in the base directory (contains translation, sounds, etc.)
resource_path = base_path / Path("res")

# command-line arguments parsed by the application
args = None

# flag to indicate if the application should exit
app_should_exit = False
