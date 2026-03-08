"""Tests for basilisk.audio.devices.AudioDeviceManager."""

from __future__ import annotations

from contextlib import ExitStack
from unittest.mock import patch

from basilisk.audio.devices import AudioDeviceManager, DeviceInfo

_WASAPI_HOSTAPI_IDX = 0


def _make_device(name, max_in, max_out, hostapi=_WASAPI_HOSTAPI_IDX):
	"""Return a dict mimicking a sounddevice device entry."""
	return {
		"name": name,
		"max_input_channels": max_in,
		"max_output_channels": max_out,
		"hostapi": hostapi,
	}


_FAKE_HOSTAPIS = [{"name": "WASAPI"}]


class TestAudioDeviceManager:
	"""Tests for AudioDeviceManager."""

	def _patch_devices(self, device_list):
		"""Context manager patching sd.query_devices and sd.query_hostapis."""
		stack = ExitStack()
		stack.enter_context(
			patch(
				"basilisk.audio.devices.sd.query_devices",
				return_value=device_list,
			)
		)
		stack.enter_context(
			patch(
				"basilisk.audio.devices.sd.query_hostapis",
				return_value=_FAKE_HOSTAPIS,
			)
		)
		return stack

	def test_get_input_devices_filters_by_input_channels(self):
		"""get_input_devices() returns only devices with input channels > 0."""
		devs = [
			_make_device("Mic", 2, 0),
			_make_device("Speaker", 0, 2),
			_make_device("Both", 1, 1),
		]
		with self._patch_devices(devs):
			result = AudioDeviceManager.get_input_devices()
		assert len(result) == 2
		names = [d.name for d in result]
		assert "Mic" in names
		assert "Both" in names
		assert "Speaker" not in names

	def test_get_output_devices_filters_by_output_channels(self):
		"""get_output_devices() returns only devices with output channels > 0."""
		devs = [
			_make_device("Mic", 2, 0),
			_make_device("Speaker", 0, 2),
			_make_device("Both", 1, 1),
		]
		with self._patch_devices(devs):
			result = AudioDeviceManager.get_output_devices()
		assert len(result) == 2
		names = [d.name for d in result]
		assert "Speaker" in names
		assert "Both" in names
		assert "Mic" not in names

	def test_device_index_matches_position_in_list(self):
		"""Device indices correspond to positions in the sd device list."""
		devs = [
			_make_device("A", 1, 1),
			_make_device("B", 1, 1),
			_make_device("C", 1, 1),
		]
		with self._patch_devices(devs):
			result = AudioDeviceManager.get_input_devices()
		indices = [d.index for d in result]
		assert indices == [0, 1, 2]

	def test_returns_device_info_objects(self):
		"""Returned items are DeviceInfo instances with correct attributes."""
		devs = [_make_device("My Mic", 2, 0)]
		with self._patch_devices(devs):
			result = AudioDeviceManager.get_input_devices()
		assert len(result) == 1
		dev = result[0]
		assert isinstance(dev, DeviceInfo)
		assert dev.name == "My Mic"
		assert dev.max_input_channels == 2
		assert dev.max_output_channels == 0

	def test_returns_empty_on_query_error(self):
		"""Returns empty list when sd.query_devices raises."""
		with patch(
			"basilisk.audio.devices.sd.query_devices",
			side_effect=Exception("hardware error"),
		):
			result = AudioDeviceManager.get_input_devices()
		assert result == []

	def test_empty_device_list(self):
		"""Returns empty list when no devices are present."""
		with self._patch_devices([]):
			result = AudioDeviceManager.get_input_devices()
		assert result == []

	def test_hostapi_filter_excludes_non_wasapi_duplicates(self):
		"""Devices from non-WASAPI host APIs (MME, DirectSound) are excluded."""
		MME_IDX = 1
		devs = [
			_make_device("Mic (WASAPI)", 2, 0, hostapi=_WASAPI_HOSTAPI_IDX),
			_make_device("Mic (MME)", 2, 0, hostapi=MME_IDX),
		]
		with self._patch_devices(devs):
			result = AudioDeviceManager.get_input_devices()
		assert len(result) == 1
		assert result[0].name == "Mic (WASAPI)"

	def test_hostapi_query_error_falls_back_to_all_devices(self):
		"""If query_hostapis fails, all matching devices are returned."""
		devs = [
			_make_device("Mic", 2, 0, hostapi=0),
			_make_device("Speaker", 0, 2, hostapi=1),
		]
		with (
			patch("basilisk.audio.devices.sd.query_devices", return_value=devs),
			patch(
				"basilisk.audio.devices.sd.query_hostapis",
				side_effect=Exception("hostapi error"),
			),
		):
			result = AudioDeviceManager.get_input_devices()
		assert len(result) == 1
		assert result[0].name == "Mic"
