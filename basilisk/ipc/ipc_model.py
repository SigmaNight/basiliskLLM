"""IPC signal models for Basilisk inter-process communication.

This module defines the Pydantic models used for structured communication
between application instances via IPC mechanisms.
"""

from datetime import datetime
from typing import Literal, Union

from pydantic import BaseModel, Field, FilePath, TypeAdapter


class FocusSignal(BaseModel):
	"""Signal to focus the Basilisk window."""

	signal_type: Literal["focus"] = "focus"
	timestamp: datetime = Field(default_factory=datetime.now)


class OpenBskcSignal(BaseModel):
	"""Signal to open a BSKC file."""

	signal_type: Literal["open_bskc"] = "open_bskc"
	file_path: FilePath


class ShutdownSignal(BaseModel):
	"""Signal to shut down the Basilisk application."""

	signal_type: Literal["shutdown"] = "shutdown"


IPCModels = TypeAdapter(Union[FocusSignal, OpenBskcSignal, ShutdownSignal])
