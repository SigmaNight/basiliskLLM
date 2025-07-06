"""Singleton instance management for Basilisk application."""

import sys

if sys.platform == "win32":
	from .windows_singleton_instance import (
		WindowsSingletonInstance as SingletonInstance,
	)
else:
	from .posix_singleton_instance import (
		POSIXSingletonInstance as SingletonInstance,
	)

__all__ = ["SingletonInstance"]
