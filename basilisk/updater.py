"""Module for updating the application."""
import platform
import re
import subprocess
import sys
import tempfile
import time
import zipfile
from abc import ABC, abstractmethod
from datetime import datetime
from functools import cached_property
from logging import getLogger
from typing import Any, Callable, Optional
from xml.etree import ElementTree as ET

import httpx

from basilisk.config import BasiliskConfig, ReleaseChannelEnum

from .consts import APP_REPO, UNINSTALL_FILE_NAME, WORKFLOW_NAME
from .global_vars import base_path

log = getLogger(__name__)
# This script is used to update the portable version of the application.
update_portable_script = r"""@echo off
REM Check if the portable ZIP file path is provided
if "%~1"=="" (
	echo error: you must provide the path to the portable ZIP file to extract.
	exit /b 1
)

REM Check if the portable APP destination folder is provided
if "%~2"=="" (
	echo error: you must provide the portable APP destination folder.
	exit /b 1
)


REM Check if the portable ZIP file exists
if not exist "%~1" (
	echo Error: the portable ZIP file "%~1" does not exist.
	exit /b 1
)

REM Check if the portable APP destination folder exists
if not exist "%~2" (
	echo Creating the portable APP destination folder...
	mkdir "%~2"
)

REM Path to the ZIP utility
set "zipUtil=%SystemRoot%\System32"

REM Wait for the portable APP to be closed
timeout /t 3 /nobreak >nul

REM Decompress the ZIP file
echo Decompressing the portable ZIP file...
"%zipUtil%\tar.exe" -xf "%~1" -C "%~2" --exclude=user_data

if %errorlevel% neq 0 (
	echo Error: failed to decompress the portable ZIP file.
	exit /b %errorlevel%
)

echo The portable APP has been successfully updated.
start "" "%~2\basilisk.exe"

REM Delete the ZIP file
del "%~1"
if %errorlevel% neq 0 (
	echo Error: failed to delete the portable ZIP file.
	exit /b %errorlevel%
)

exit /b 0
"""


class BaseUpdater(ABC):
	"""Base class for application updaters. This class defines the interface for application updaters."""

	@abstractmethod
	def latest_version(self) -> str:
		"""Get the latest version of the application. This method should be implemented by the derived class.

		Returns:
			The latest version of the application as a string.
		"""
		pass

	@property
	def release_notes(self) -> Optional[str]:
		"""Get the release notes for the latest version of the application. This method should be implemented by the derived class.

		Returns:
			The release notes for the latest version of the application as a string.
		"""
		return None

	@cached_property
	def is_update_enable(self) -> bool:
		"""Check if the application is enabled for updates.

		Returns:
			True if the application is packaged as an executable or if the application is installed, False otherwise.
		"""
		return getattr(sys, "frozen", False)

	@cached_property
	def current_version(self) -> str:
		"""Get the current version of the application.

		Raises:
			NotImplementedError: If the application is not packaged as an executable.

		Returns:
			The current version of the application as a string.

		"""
		if getattr(sys, "frozen", False):
			from BUILD_CONSTANTS import BUILD_RELEASE_STRING  # noqa # type: ignore

			return BUILD_RELEASE_STRING
		else:
			raise NotImplementedError(
				"Version not implemented for non-frozen applications"
			)

	def is_update_available(self) -> bool:
		"""Check if an update is available for the application.

		Returns:
			True if the latest version string is different from the current version string, False otherwise.
		"""
		current_version = self.current_version
		log.info(f"Current version: {current_version}")
		latest_version = self.latest_version
		log.info(f"Latest version: {latest_version}")
		return current_version != latest_version

	@cached_property
	def get_app_architecture(self) -> str:
		"""Get the architecture of the application.

		Returns:
			The architecture of the application as a string (e.g., 'x64' or 'x86').
		"""
		arch = platform.architecture()[0]
		if arch == "64bit":
			return "x64"
		elif arch == "32bit":
			return "x86"
		else:
			raise Exception("Unknown architecture")

	@cached_property
	def is_app_installed(self) -> bool:
		"""Check if the application is installed.

		Returns:
			True if the application is installed, False otherwise.
		"""
		if self.is_update_enable:
			return base_path.joinpath(UNINSTALL_FILE_NAME).exists()
		else:
			raise NotImplementedError(
				"Installation check not implemented for non-frozen applications"
			)

	def download_file(
		self,
		link: str,
		file_tmp: tempfile.NamedTemporaryFile,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download: bool = False,
	) -> bool:
		"""Download a file from a URL and save it to a temporary file.

		Args:
			link: The URL to download the file from.
			file_tmp: The temporary file to save the downloaded data to.
			grafical_callback: A callback function to update a progress bar. Defaults to None.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			True if the download was successful, False otherwise.
		"""
		response = httpx.get(link, follow_redirects=True)
		response.raise_for_status()
		total_length = int(response.headers.get("Content-Length", 0))
		chunk_size = 4096
		downloaded_length = 0
		for chunk in response.iter_bytes(chunk_size):
			file_tmp.write(chunk)
			downloaded_length += chunk_size
			if grafical_callback:
				grafical_callback(downloaded_length, total_length)
			if stop_download:
				return False
		file_tmp.flush()
		file_tmp.seek(0)
		return True

	@abstractmethod
	def download_installer(
		self, grafical_callback: Callable[[int, int], None], stop_download: bool = False
	) -> Optional[str]:
		"""Download the installer for the application. This method should be implemented by the derived class.

		Args:
			grafical_callback: A callback function to update a progress bar.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded installer file as a string, or None if the download failed.
		"""
		pass

	@abstractmethod
	def download_portable(
		self,
		grafical_callback: Callable[[int, int], None],
		stop_download: bool = False,
	) -> Optional[str]:
		"""Download the portable version of the application. This method should be implemented by the derived class.

		Args:
			grafical_callback: A callback function to update a progress bar.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded portable file as a string, or None if the download failed.
		"""
		pass

	def download(
		self,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download: bool = False,
	) -> bool:
		"""Download the update for the application.

		Args:
			grafical_callback: A callback function to update a progress bar. Defaults to None.
			stop_download: A flag to stop the download process. Defaults to False.

		Raises:
			NotImplementedError: If the application is not packaged as an executable.

		Returns:
			True if the download was successful, False otherwise.
		"""
		if self.is_update_enable:
			if self.is_app_installed:
				log.debug("starting download installer")
				self.downloaded_file = self.download_installer(
					grafical_callback, stop_download
				)
			else:
				log.debug("starting download portable")
				self.downloaded_file = self.download_portable(
					grafical_callback, stop_download
				)
			return self.downloaded_file is not None
		else:
			raise NotImplementedError(
				"Download not implemented for non-frozen applications"
			)

	def update_with_installer(self):
		"""Update the installed version of the application using the downloaded installer."""
		subprocess.Popen(
			executable=self.downloaded_file,
			args=["/SILENT"],
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			stdin=subprocess.DEVNULL,
			close_fds=True,
			creationflags=subprocess.CREATE_NO_WINDOW
			| subprocess.DETACHED_PROCESS,
			shell=True,
		)

	def update_portable(self):
		"""Update the portable version of the application using the downloaded portable file."""
		update_script_path = base_path / "update_portable.bat"
		with open(update_script_path, "w") as update_script:
			update_script.write(update_portable_script)
		subprocess.Popen(
			(update_script_path, self.downloaded_file, base_path),
			stdin=subprocess.DEVNULL,
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			shell=True,
			close_fds=True,
			creationflags=subprocess.CREATE_NO_WINDOW
			| subprocess.DETACHED_PROCESS,
		)

	def update(self):
		"""Update the application using the downloaded update file.

		Raises:
		Exception: If the update file has not been downloaded.
			NotImplementedError: If the application is not packaged as an executable.
		"""
		if self.is_update_enable:
			if not getattr(self, "downloaded_file", None):
				raise Exception("Download the update first")
			if self.is_app_installed:
				self.update_with_installer()
			else:
				self.update_portable()
		else:
			raise NotImplementedError(
				"Update not implemented for non-frozen applications"
			)


class NigthlyUpdater(BaseUpdater):
	"""Class for updating the application from the nightly build."""

	def __init__(self):
		"""Initialize the NigthlyUpdater class. Set the URL for the nightly build."""
		self.url = (
			f"https://nightly.link/{APP_REPO}/workflows/{WORKFLOW_NAME}/master"
		)

	@cached_property
	def artifact_xml_table(self) -> ET.Element:
		"""Get the XML table containing the artifact links.

		Returns:
			The XML table containing the artifact links as an ElementTree object.
		"""
		response = httpx.get(self.url)
		response.raise_for_status()
		table_pattern = re.compile(r"(<table>.*?</table>)", re.DOTALL)
		xml_table = re.findall(table_pattern, response.text)[0]
		log.debug(f"link table received: {xml_table}")
		return ET.fromstring(xml_table)

	@cached_property
	def latest_version(self) -> str:
		"""Get the latest version of the application.

		Parse the XML table to find the latest version of the application. The version is extracted from the artifact links.

		Returns:
			The latest version of the application as a string.
		"""
		log.info("Getting latest version")
		version_links = self.artifact_xml_table.findall(".//th/a")
		unique_version = set()
		for link in version_links:
			text = link.text
			log.debug(f"version_link: {text}")
			parts = text.split("_")
			if len(parts) > 1:
				unique_version.add(parts[2])
		log.debug(f"Versions found: {unique_version}")
		if len(unique_version) != 1:
			raise Exception("No version found or multiple versions found")
		return unique_version.pop()

	def get_download_link(self, installer: bool) -> str:
		"""Get the download link for the application.

		Args:
			installer: A flag to indicate if the installer or the portable version of the application is being downloaded.

		Returns:
			The download link for the application as a string.
		"""
		architecture = self.get_app_architecture
		artifact_links = self.artifact_xml_table.findall(".//td/a")
		artifact_prefix_name = (
			"setup_basiliskLLM" if installer else "portable_basiliskLLM"
		)
		for link in artifact_links:
			if artifact_prefix_name in link.text and architecture in link.text:
				return link.get("href")

	def download_installer(
		self,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download=False,
	) -> Optional[str]:
		"""Download the installer for the application.

		The installer is downloaded from the nightly build link and extracted from the ZIP file.

		Args:
			grafical_callback: A callback function to update a progress bar. Defaults to None.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded installer file as a string, or None if the download failed.
		"""
		log.info("Downloading installer")
		link = self.get_download_link(True)
		log.debug(f"Installer link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="setup_basiliskllm_", suffix=".zip"
		) as zip_tmp_file:
			if not self.download_file(
				link, zip_tmp_file, grafical_callback, stop_download
			):
				return None
			return self.extract_installer_from_zip(zip_tmp_file)

	def download_portable(
		self,
		grafical_callback: Callable[[int, int], None],
		stop_download: bool = False,
	) -> str | None:
		"""Download the portable version of the application.

		The portable version is downloaded from the nightly build link and saved to a ZIP file.

		Args:
			grafical_callback: A callback function to update a progress bar.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded portable file as a string, or None if the download failed.
		"""
		log.info("getting link for portable")
		link = self.get_download_link(False)
		log.debug(f"Portable link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="portable_basiliskllm_",
			suffix=".zip",
			dir=base_path,
			delete=False,
			delete_on_close=False,
		) as zip_tmp_file:
			if not self.download_file(
				link, zip_tmp_file, grafical_callback, stop_download
			):
				return None
			return zip_tmp_file.name

	def extract_installer_from_zip(
		self, zip_tmp_file: tempfile.NamedTemporaryFile
	) -> str:
		"""Extract the installer from the ZIP file.

		Args:
			zip_tmp_file: The ZIP file containing the installer.

		Returns:
			The path to the extracted installer file as a string.

		Raises:
			Exception: If the installer is not found in the ZIP file.

		Returns:
			The path to the extracted installer file as a string.
		"""
		log.info(
			f"Extracting installer from artifact zip file: {zip_tmp_file.name}"
		)
		with zipfile.ZipFile(zip_tmp_file) as zip_file:
			setup_file_name = [
				name
				for name in zip_file.namelist()
				if "setup_basiliskLLM" in name
			][0]
			with tempfile.NamedTemporaryFile(
				prefix="setup_basiliskllm_",
				suffix=".exe",
				delete=False,
				delete_on_close=False,
			) as setup_tmp_file:
				setup_tmp_file.write(zip_file.read(setup_file_name))
				setup_tmp_file.flush()
				log.info(f"Installer extracted to: {setup_tmp_file.name}")
				return setup_tmp_file.name


class GithubUpdater(BaseUpdater):
	"""Class for updating the application from the GitHub releases."""

	def __init__(self, pre_release: bool = False):
		"""Initialize the GithubUpdater class. Set the URL for the GitHub releases.

		Args:
			pre_release: A flag to indicate if pre-releases should be included. Defaults to False.
		"""
		self.url = f"https://api.github.com/repos/{APP_REPO}/releases"
		self.headers = {
			"Accept": "application/vnd.github+json",
			"X-GitHub-Api-Version": "2022-11-28",
		}
		self.pre_release = pre_release

	@cached_property
	def release_data(self) -> dict[str, Any]:
		"""Get the release data from the GitHub API.

		Returns:
			The release data as a dictionary.
		"""
		url = self.url
		if not self.pre_release:
			url += "/latest"
		response = httpx.get(url, headers=self.headers)
		response.raise_for_status()
		data = response.json()
		if self.pre_release:
			for release in data:
				if release["prerelease"]:
					data = release
					break
		return data

	@property
	def release_notes(self) -> Optional[str]:
		"""Get the release notes for the latest version of the application.

		Extract the release notes from the release data.

		Returns:
			The release notes for the latest version of the application as a string.
		"""
		return self.release_data.get("body", None)

	@cached_property
	def latest_version(self) -> str:
		"""Get the latest version of the application.

		The version is a git tag which contains a 'v' prefix.

		Returns:
			The latest version of the application as a string.
		"""
		return self.release_data["tag_name"][1:]

	def get_download_link(self, installer: bool) -> str:
		"""Get the download link for the application release.

		Args:
			installer: A flag to indicate if the installer or the portable version of the application is being downloaded.

		Returns:
			The download link for the application as a string.
		"""
		data = self.release_data
		architecture = self.get_app_architecture
		assets = data["assets"]
		asset_prefix_name = (
			"setup_basiliskLLM" if installer else "portable_basiliskLLM"
		)
		for asset in assets:
			if (
				asset_prefix_name in asset["name"]
				and architecture in asset["name"]
			):
				return asset["browser_download_url"]

	def download_installer(
		self,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download=False,
	) -> Optional[str]:
		"""Download the installer for the application.

		The installer is downloaded from the GitHub release link.

		Args:
			grafical_callback: A callback function to update a progress bar. Defaults to None.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded installer file as a string, or None if the download failed.
		"""
		log.info("Downloading installer")
		link = self.get_download_link(True)
		log.debug(f"Installer link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="setup_basiliskllm_",
			suffix=".exe",
			delete=False,
			delete_on_close=False,
		) as installer_tmp_file:
			download_finished = self.download_file(
				link, installer_tmp_file, grafical_callback, stop_download
			)
			if not download_finished:
				return None
			return installer_tmp_file.name

	def download_portable(
		self,
		grafical_callback: Callable[[int, int], None],
		stop_download: bool = False,
	) -> str | None:
		"""Download the portable version of the application.

		The portable version is downloaded from the GitHub release link.

		Args:
			grafical_callback: A callback function to update a progress bar.
			stop_download: A flag to stop the download process. Defaults to False.

		Returns:
			The path to the downloaded portable file as a string, or None if the download failed.
		"""
		link = self.get_download_link(False)
		log.debug(f"Portable link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="portable_basiliskllm_",
			suffix=".zip",
			dir=base_path,
			delete=False,
			delete_on_close=False,
		) as zip_tmp_file:
			download_finished = self.download_file(
				link, zip_tmp_file, grafical_callback, stop_download
			)
			if not download_finished:
				return None
		return zip_tmp_file.name


def get_updater_from_channel(conf: BasiliskConfig) -> BaseUpdater:
	"""Get the updater object based on the release channel.

	Args:
		conf: The Basilisk configuration object.

	Returns:
		The updater object based on the release channel.
	"""
	log.info(f"Getting updater from channel: {conf.general.release_channel}")
	match conf.general.release_channel:
		case ReleaseChannelEnum.STABLE:
			return GithubUpdater(pre_release=False)
		case ReleaseChannelEnum.BETA:
			return GithubUpdater(pre_release=True)
		case ReleaseChannelEnum.DEV:
			return NigthlyUpdater()


def automatic_update_check(
	conf: BasiliskConfig,
	notify_update_callback: Callable[[BaseUpdater], None] = None,
	stop: bool = False,
	retries: int = 20,
) -> Optional[BaseUpdater]:
	"""Check for updates automatically based on the configuration settings.

	Args:
		conf: The Basilisk configuration object.
		notify_update_callback: A callback function to notify the user of an available update. Defaults to None.
		stop: A flag to stop the update process. Defaults to False.
		retries: The number of retries to attempt. Defaults to 20.

	Returns:
		The updater object if an update is available, None otherwise.
	"""
	updater = get_updater_from_channel(conf)
	if not updater.is_update_enable:
		log.error("Update are disabled for source application")
		return None
	if (
		conf.general.last_update_check is not None
		and conf.general.last_update_check.date() == datetime.now().date()
	):
		log.info("Last update check was today")
		return None
	else:
		log.info("Last update check was not today")
	try:
		update_available = updater.is_update_available()
		conf.general.last_update_check = datetime.now()
		conf.save()
		if notify_update_callback and update_available:
			log.info("Update available")
			notify_update_callback(updater)
		if not update_available:
			log.info("No update available")
			return None
		return updater
	except httpx.HTTPStatusError as e:
		log.error(f"Error checking for updates: {e}")
		return None
	except Exception as e:
		log.error(f"Error checking for updates: {e}")
		if retries > 0 and not stop:
			retries -= 1
			log.info(f"Retrying update check: {retries} retries left")
			time.sleep(300)
			return automatic_update_check(
				conf, notify_update_callback, stop, retries
			)
		else:
			log.error("Failed to check for updates, maximum retries reached")
			return None


def automatic_update_download(
	conf: BasiliskConfig,
	notify_update_callback: Callable[[BaseUpdater], None] = None,
	stop: bool = False,
	retries: int = 20,
) -> Optional[BaseUpdater]:
	"""Download the update automatically based on the configuration settings.

	Args:
		conf: The Basilisk configuration object.
		notify_update_callback: A callback function to notify the user of an available update. Defaults to None.
		stop: A flag to stop the update process. Defaults to False.
		retries: The number of retries to attempt. Defaults to 20.

	Returns:
		The updater object if the update was downloaded successfully, None otherwise.
	"""
	updater = automatic_update_check(conf, None, retries)
	if not updater:
		return None
	try:
		download_finished = updater.download()
		if not download_finished:
			log.info("Update not downloaded")
			return None
		if notify_update_callback:
			log.info("Update downloaded")
			notify_update_callback(updater)
			return updater
	except Exception as e:
		log.error(f"Error downloading update: {e}", exc_info=True)
		if retries > 0 and not stop:
			retries -= 1
			log.info(f"Retrying update download: {retries} retries left")
			time.sleep(300)
			return automatic_update_download(
				conf, notify_update_callback, stop, retries
			)
		else:
			log.error("Failed to download update, maximum retries reached")
			return None
