"""Audio device discovery for BasiliskLLM."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import sounddevice as sd

log = logging.getLogger(__name__)


@dataclass
class DeviceInfo:
	"""Information about an audio device."""

	index: int
	name: str
	max_input_channels: int
	max_output_channels: int


class AudioDeviceManager:
	"""Queries and filters available audio devices."""

	@staticmethod
	def get_input_devices() -> list[DeviceInfo]:
		"""Return all devices that have at least one input channel.

		Returns:
			List of DeviceInfo for input-capable devices.
		"""
		return AudioDeviceManager._query(min_input=1)

	@staticmethod
	def get_output_devices() -> list[DeviceInfo]:
		"""Return all devices that have at least one output channel.

		Returns:
			List of DeviceInfo for output-capable devices.
		"""
		return AudioDeviceManager._query(min_output=1)

	@staticmethod
	def _get_preferred_hostapi() -> int | None:
		"""Return the preferred host API index, or None to use all.

		On Windows, returns the WASAPI host API index so that each
		physical device appears only once and disconnected devices
		(which MME/DirectSound may still expose) are excluded.

		Returns:
			Host API index to filter by, or None for no filtering.
		"""
		if sys.platform != "win32":
			return None
		try:
			for idx, api in enumerate(sd.query_hostapis()):
				if "WASAPI" in api["name"]:
					return idx
		except Exception:
			log.warning("Failed to query host APIs", exc_info=True)
		return None

	@staticmethod
	def _query(min_input: int = 0, min_output: int = 0) -> list[DeviceInfo]:
		"""Query sounddevice and filter by channel requirements.

		On Windows, only devices from the WASAPI host API are returned
		to avoid duplicates (MME/DirectSound expose the same hardware)
		and phantom disconnected devices.

		Args:
			min_input: Minimum required input channels.
			min_output: Minimum required output channels.

		Returns:
			Filtered list of DeviceInfo objects.
		"""
		try:
			devices = sd.query_devices()
		except Exception:
			log.error("Failed to query audio devices", exc_info=True)
			return []
		preferred_hostapi = AudioDeviceManager._get_preferred_hostapi()
		result: list[DeviceInfo] = []
		for idx, dev in enumerate(devices):
			if (
				preferred_hostapi is not None
				and dev["hostapi"] != preferred_hostapi
			):
				continue
			if (
				dev["max_input_channels"] >= min_input
				and dev["max_output_channels"] >= min_output
			):
				result.append(
					DeviceInfo(
						index=idx,
						name=dev["name"],
						max_input_channels=dev["max_input_channels"],
						max_output_channels=dev["max_output_channels"],
					)
				)
		return result
