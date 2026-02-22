"""Module for the BasiliskLLM connector for NVDA.

This module provides a global plugin for NVDA that allows the user to send information to BasiliskLLM.
"""

import socket

import addonHandler  # type: ignore
import api  # type: ignore
import config  # type: ignore
import controlTypes  # type: ignore
import globalPluginHandler  # type: ignore
import gui  # type: ignore
import ui  # type: ignore
from scriptHandler import script  # type: ignore

addonHandler.initTranslation()

confSpecs = {"port": "integer(min=1, max=65535, default=4242)"}
config.conf.spec["basiliskLLM"] = confSpecs
conf = config.conf["basiliskLLM"]


def send_message(message: str) -> bool:
	"""Send a message to BasiliskLLM application.

	Args:
		message: The message to send to BasiliskLLM.

	Returns:
		True if the message was sent successfully, False otherwise.
	"""
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	server_address = ("127.0.0.1", conf["port"])
	success = False
	try:
		sock.connect(server_address)
		sock.sendall(message.encode())
		response = sock.recv(128).decode()
		if response == "ACK":
			success = True
	except Exception:
		pass
	finally:
		sock.close()
	return success


class SettingsDlg(gui.settingsDialogs.SettingsPanel):
	"""nvda settings panel for BasiliskLLM connector."""

	title = "BasiliskLLM Connector"

	def makeSettings(self, settingsSizer):
		"""Create the settings panel.

		Args:
			settingsSizer: The sizer to add the settings to.
		"""
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.port = sHelper.addLabeledControl(
			# Translators: This is a label for a text field where the user can fill the port number in the settings dialog.
			_("Port to connect to BasiliskLLM:"),
			gui.nvdaControls.SelectOnFocusSpinCtrl,
			min=1,
			max=65535,
			initial=conf["port"],
		)

	def onSave(self):
		"""Save the settings."""
		conf["port"] = self.port.GetValue()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	"""NVDA Global plugin for BasiliskLLM connector."""

	scriptCategory = "BasiliskLLM Connector"

	def __init__(self):
		"""Initialize the global plugin."""
		super().__init__()
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(
			SettingsDlg
		)

	def checkScreenCurtain(self) -> bool:
		"""Check if the screen curtain is running.

		Returns:
			True if the screen curtain is running, False otherwise.
		"""
		import vision  # type: ignore
		from visionEnhancementProviders.screenCurtain import (  # type: ignore
			ScreenCurtainProvider,
		)

		screenCurtainId = ScreenCurtainProvider.getSettings().getId()
		screenCurtainProviderInfo = vision.handler.getProviderInfo(
			screenCurtainId
		)
		isScreenCurtainRunning = bool(
			vision.handler.getProviderInstance(screenCurtainProviderInfo)
		)
		if isScreenCurtainRunning:
			ui.message(
				_(
					"Please disable the screen curtain before taking a screenshot"
				)
			)
		return isScreenCurtainRunning

	@staticmethod
	def send_message(
		data: str, success_msg: str = _("Image sent to BasiliskLLM")
	):
		"""Send a message to BasiliskLLM application.

		Args:
			data: The message to send to BasiliskLLM.
			success_msg: The message to display on success. Defaults to "Image sent to BasiliskLLM".
		"""
		if not send_message(data):
			ui.message(_("Unable to send image to BasiliskLLM. Is it running?"))
		else:
			ui.message(success_msg)

	def _get_base_url(self):
		"""Get the base URL of the current image.

		Returns:
			The base URL of the current image.
		"""
		obj = api.getNavigatorObject()
		url = None
		while obj:
			obj = obj.parent
			if not obj:
				break
			if obj.role != controlTypes.Role.DOCUMENT:
				continue
			url = obj.IAccessibleObject.accValue(obj.IAccessibleChildID)
			if url and url.startswith("http"):
				url = "/".join(url.split("/", 3)[:3])
				break
		return url

	@script(
		gesture="kb:nvda+shift+k",
		description=_(
			"Grab the current navigator object and send it to BasiliskLLM"
		),
	)
	def script_grabObject(self, gesture):
		"""Grab the current navigator object and send it to BasiliskLLM.

		Args:
			gesture: The gesture that triggered this script.
		"""
		if self.checkScreenCurtain():
			return
		nav = api.getNavigatorObject()
		name = nav.name
		try:
			nav.scrollIntoView()
		except BaseException:
			pass
		left, top, width, height = nav.location
		right = left + width
		bottom = top + height
		data = f"grab:{left}, {top}, {right}, {bottom}"
		if name:
			data += f"\n{name}"
		self.send_message(data, _("Object image sent to BasiliskLLM"))

	@script(
		gesture="kb:nvda+shift+l",
		description=_("Send the current src of the image to BasiliskLLM"),
	)
	def script_sendURL(self, gesture):
		"""Send the current src of the image to BasiliskLLM.

		Args:
			gesture: The gesture that triggered this script.
		"""
		nav = api.getNavigatorObject()
		name = nav.name
		if nav.IA2Attributes and "src" in nav.IA2Attributes:
			src = nav.IA2Attributes["src"]
			if src.startswith("/"):
				base_url = self._get_base_url()
				if not base_url:
					ui.message(_("Unable to retrieve base URL"))
					return
				src = base_url + src
			data = "url:%s" % src
			if name:
				data += f"\n{name}"
			self.send_message(data, _("URL image sent to BasiliskLLM"))
		else:
			ui.message(_("src not found. Is this an image?"))

	def terminate(self):
		"""Terminate the global plugin."""
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
			SettingsDlg
		)
		super().terminate()
