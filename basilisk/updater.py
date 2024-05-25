import platform
import re
import subprocess
import sys
import tempfile
import zipfile
import httpx
from abc import ABC, abstractmethod
from functools import cached_property
from logging import getLogger
from typing import Callable, Optional
from xml.etree import ElementTree as ET

from .globalvars import base_path

log = getLogger(__name__)

update_portable_script = """@echo off
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
"%zipUtil%\\tar.exe" -xf "%~1" -C "%~2" --exclude=user_data

if %errorlevel% neq 0 (
    echo Error: failed to decompress the portable ZIP file.
    exit /b %errorlevel%
)

echo The portable APP has been successfully updated.
start "" "%~2\\basilisk.exe"

REM Delete the ZIP file
del "%~1"
if %errorlevel% neq 0 (
	echo Error: failed to delete the portable ZIP file.
	exit /b %errorlevel%
	)

exit /b 0
"""


class BaseUpdater(ABC):
	@abstractmethod
	def latest_version(self) -> str:
		pass

	def is_update_enable(self) -> bool:
		return getattr(sys, "frozen", False)

	@cached_property
	def current_version(self) -> str:
		if getattr(sys, "frozen", False):
			from BUILD_CONSTANTS import BUILD_RELEASE_STRING  # noqa # type: ignore

			return BUILD_RELEASE_STRING
		else:
			raise NotImplementedError(
				"Version not implemented for non-frozen applications"
			)

	def is_update_available(self) -> bool:
		current_version = self.current_version
		log.info(f"Current version: {current_version}")
		latest_version = self.latest_version
		log.info(f"Latest version: {latest_version}")
		return current_version != latest_version

	def get_app_architecture(self) -> str:
		arch = platform.architecture()[0]
		if arch == "64bit":
			return "x64"
		elif arch == "32bit":
			return "x86"
		else:
			raise Exception("Unknown architecture")

	def is_app_installed(self) -> bool:
		if getattr(sys, "frozen", False):
			return base_path.joinpath("uninstall.exe").exists()
		else:
			raise NotImplementedError(
				"Installation check not implemented for non-frozen applications"
			)

	@abstractmethod
	def download_installer(
		self, grafical_callback: Callable[[int, int], None]
	) -> Optional[str]:
		pass

	@abstractmethod
	def download_portable(
		self,
		grafical_callback: Callable[[int, int], None],
		stop_download: bool = False,
	) -> Optional[str]:
		pass

	def download(
		self,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download: bool = False,
	) -> bool:
		if getattr(sys, "frozen", False):
			if self.is_app_installed():
				self.downloaded_file = self.download_installer(
					grafical_callback, stop_download
				)
			else:
				self.downloaded_file = self.download_portable(
					grafical_callback, stop_download
				)
			return self.downloaded_file is not None
		else:
			raise NotImplementedError(
				"Download not implemented for non-frozen applications"
			)

	def update_with_installer(self):
		subprocess.Popen(
			executable=self.downloaded_file,
			args="/VERYSILENT",
			stdout=subprocess.DEVNULL,
			stderr=subprocess.DEVNULL,
			stdin=subprocess.DEVNULL,
			close_fds=True,
			creationflags=subprocess.CREATE_NO_WINDOW
			| subprocess.DETACHED_PROCESS,
			shell=True,
		)

	def update_portable(self):
		update_script_path = base_path.joinpath("update_portable.bat")
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
		if getattr(sys, "frozen", False):
			if not getattr(self, "downloaded_file", None):
				raise Exception("Download the update first")
			if self.is_app_installed():
				self.update_with_installer()
			else:
				self.update_portable()
		else:
			raise NotImplementedError(
				"Update not implemented for non-frozen applications"
			)


class NigthlyUpdater(BaseUpdater):
	def __init__(self):
		self.url = "https://nightly.link/aaclause/basiliskLLM/workflows/build_app_exe/master"

	@cached_property
	def latest_version(self) -> str:
		log.info("Getting latest version")
		response = httpx.get(self.url)
		response.raise_for_status()
		table_pattern = re.compile(r"(<table>.*?</table>)", re.DOTALL)
		xml_table = re.findall(table_pattern, response.text)[0]
		log.debug(f"link table received: {xml_table}")
		self.table_root = ET.fromstring(xml_table)
		version_links = self.table_root.findall(".//th/a")
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
		architecture = self.get_app_architecture()
		artifact_links = self.table_root.findall(".//td/a")
		artifact_prefix_name = (
			"setup_basiliskLLM" if installer else "portable_basiliskLLM"
		)
		for link in artifact_links:
			if artifact_prefix_name in link.text and architecture in link.text:
				return link.get("href")

	def download_zip(
		self,
		link: str,
		zip_tmp: tempfile.NamedTemporaryFile,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download: bool = False,
	) -> bool:
		response = httpx.get(link, follow_redirects=True)
		response.raise_for_status()
		total_length = int(response.headers.get("Content-Length", 0))
		chunk_size = 4096
		downloaded_length = 0
		for chunk in response.iter_bytes(chunk_size):
			zip_tmp.write(chunk)
			downloaded_length += chunk_size
			if grafical_callback:
				grafical_callback(downloaded_length, total_length)
			if stop_download:
				return False
		zip_tmp.flush()
		zip_tmp.seek(0)
		return True

	def download_installer(
		self,
		grafical_callback: Callable[[int, int], None] = None,
		stop_download=False,
	) -> Optional[str]:
		log.info("Downloading installer")
		link = self.get_download_link(True)
		log.debug(f"Installer link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="setup_basiliskllm_", suffix=".zip"
		) as zip_tmp_file:
			download_finished = self.download_zip(
				link, zip_tmp_file, True, grafical_callback, stop_download
			)
			if not download_finished:
				return None
			return self.extract_installer_from_zip(zip_tmp_file)

	def download_portable(
		self,
		grafical_callback: Callable[[int, int], None],
		stop_download: bool = False,
	) -> str | None:
		link = self.get_download_link(False)
		log.debug(f"Portable link: {link}")
		with tempfile.NamedTemporaryFile(
			prefix="portable_basiliskllm_",
			suffix=".zip",
			dir=base_path,
			delete=False,
			delete_on_close=False,
		) as zip_tmp_file:
			download_finished = self.download_zip(
				link, zip_tmp_file, grafical_callback, stop_download
			)
			if not download_finished:
				return None
		return zip_tmp_file.name

	def extract_installer_from_zip(
		self, zip_tmp_file: tempfile.NamedTemporaryFile
	) -> str:
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
