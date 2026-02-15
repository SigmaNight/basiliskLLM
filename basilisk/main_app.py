"""Module for the main application class and initialization.

This module contains the MainApp class, which is the main application class for Basilisk. It is responsible for initializing the application, setting up the main window, logging, localization, and background services. The MainApp class is a subclass of wx.App, which is the main application class for wxPython applications.

Returns:
	MainApp: The main application class for Basilisk.
"""

import logging
import sys
import threading

import truststore
import wx

import basilisk.config as config
import basilisk.global_vars as global_vars

# don't use relative import here, CxFreeze will fail to find the module
from basilisk.consts import APP_NAME
from basilisk.conversation.database import get_db
from basilisk.ipc import BasiliskIpc, FocusSignal, OpenBskcSignal
from basilisk.localization import init_translation
from basilisk.logger import (
	get_log_file_path,
	logging_uncaught_exceptions,
	setup_logging,
)
from basilisk.server_thread import ServerThread
from basilisk.sound_manager import initialize_sound_manager
from basilisk.updater import automatic_update_check, automatic_update_download

log = logging.getLogger(__name__)


class MainApp(wx.App):
	"""Main application class for Basilisk."""

	def OnInit(self) -> bool:
		"""Initialize the application and set up the main window.

		This method is called when the application starts and performs several critical setup tasks:
		- Configures exception handling and logging
		- Sets up localization and language
		- Initializes sound management and accessibility
		- Creates the main application frame
		- Sets up file watching
		- Optionally starts a server thread
		- Optionally starts an automatic update thread

		Returns:
			returns True to indicate successful application initialization

		Raises:
			Various potential exceptions during initialization of components like sound manager,
			file watcher, server thread, or update thread
		"""
		sys.excepthook = logging_uncaught_exceptions
		self.conf = config.conf()
		log_level = (
			global_vars.args.log_level or self.conf.general.log_level.name
		)
		log.debug("args: %s", global_vars.args)
		setup_logging(log_level)
		log.debug("config: %s", self.conf)
		if getattr(sys, "frozen", False):
			log.info(
				"running frozen application: redirecting stdio to log file"
			)
			self.RedirectStdio(str(get_log_file_path()))
		language = global_vars.args.language or self.conf.general.language
		self.locale = init_translation(language)
		log.info("translation initialized")
		initialize_sound_manager()
		log.info("sound manager initialized")
		get_db()
		log.info("conversation database initialized")
		self.init_main_frame()
		log.info("main frame initialized")
		self.init_system_cert_store()
		self.init_ipc()
		self.server = None
		if self.conf.server.enable:
			self.server = ServerThread(self.frame, self.conf.server.port)
			self.server.start()
		self.auto_update = None
		if (
			self.conf.general.automatic_update_mode
			!= config.AutomaticUpdateModeEnum.OFF
		):
			self.start_auto_update_thread()
		log.info("Application started")
		return True

	def init_main_frame(self):
		"""Initializes the main application frame.

		Creates an instance of the MainFrame class and sets it as the top window for the application. The frame is then shown, and the application is set to the top window.
		"""
		from basilisk.gui.main_frame import MainFrame

		frame_style = wx.DEFAULT_FRAME_STYLE
		if global_vars.args.minimize:
			frame_style |= wx.MINIMIZE
		self.frame = MainFrame(
			None,
			title=APP_NAME,
			conf=self.conf,
			style=frame_style,
			open_file=global_vars.args.bskc_file,
		)
		self.frame.Show(not global_vars.args.minimize)
		self.SetTopWindow(self.frame)

	def start_auto_update_thread(self):
		"""Starts the automatic update thread.

		Creates a new thread to handle automatic updates based on the configuration settings. The thread is started in the background and runs until the application exits or the thread is stopped.
		"""
		self.stop_auto_update = False
		target_func = (
			automatic_update_check
			if self.conf.general.automatic_update_mode
			== config.AutomaticUpdateModeEnum.NOTIFY
			else automatic_update_download
		)
		callback_func = (
			self.frame.show_update_notification
			if self.conf.general.automatic_update_mode
			== config.AutomaticUpdateModeEnum.NOTIFY
			else self.frame.show_update_download
		)
		self.auto_update = threading.Thread(
			target=target_func,
			args=(self.conf, callback_func, self.stop_auto_update),
			daemon=True,
		)
		self.auto_update.start()
		log.info("Automatic update thread started")

	def OnExit(self) -> int:
		"""Handles the cleanup and exit process for the application.

		Performs the following cleanup tasks:
		- Stops and joins the server thread if it exists
		- Stops and joins the automatic update thread if running
		- Stops and joins the file watcher
		- Removes temporary files
		- Logs exit-related events

		Returns:
		Always returns 0 to indicate successful application exit
		"""
		if self.server:
			log.debug("Stopping server")
			self.server.stop()
			self.server.join()
			log.debug("Server stopped")
		if self.auto_update and self.auto_update.is_alive():
			self.stop_auto_update = True
			self.auto_update.join()
			log.info("Automatic update thread stopped")
		# Stop IPC mechanism (Windows named pipes or file watcher)
		# Clean up IPC
		if self.ipc:
			log.debug("Stopping IPC receiver")
			self.ipc.stop_receiver()
			log.info("IPC receiver stopped")
		from basilisk.conversation.database import close_db

		close_db()
		log.debug("conversation database closed")
		log.info("Application exited")
		return 0

	def init_system_cert_store(self):
		"""Initializes the system certificate store for SSL connections.

		Activates the system certificate store for SSL connections if the configuration setting is enabled. If the setting is disabled, the certifi certificate store is used instead. If an error occurs during activation, an error message is displayed to the user.
		"""
		if not self.conf.network.use_system_cert_store:
			log.info("Use certifi certificate store")
			return
		try:
			log.debug("Activating system certificate store")
			truststore.inject_into_ssl()
			log.info("System certificate store activated")
		except Exception as e:
			log.error(
				"Failed to activate system certificate store: %s",
				e,
				exc_info=True,
			)
			wx.MessageBox(
				# Translators: Error message
				_("Failed to activate system certificate store"),
				# Translators: Error title
				_("Error"),
				style=wx.ICON_ERROR,
			)

	def bring_window_to_focus(self, data: FocusSignal):
		"""Brings the main application window to the front and gives it focus.

		This method is called by the IPC mechanism when a focus signal is received.
		It ensures that the main application window is brought to the front and given focus,
		with special handling for screen readers like NVDA.

		The logic is:
		1. If window is hidden -> restore it
		2. If window is visible but this is a focus signal from another instance -> toggle to hidden
		3. If window is iconized -> restore it

		Args:
			data: Optional signal data (used by Windows IPC, ignored by file watcher)
		"""
		log.debug("bring_window_to_focus called with data: %s", data)
		log.debug(
			"Frame state - IsShown: %s, IsIconized: %s",
			self.frame.IsShown(),
			self.frame.IsIconized(),
		)

		if not self.frame.IsShown():
			# Window is hidden, restore it
			log.debug("Window is hidden, restoring")
			wx.CallAfter(self.frame.on_restore, None)
			return
		elif self.frame.IsIconized():
			# Window is iconized, restore it
			log.debug("Window is iconized, restoring")
			wx.CallAfter(self.frame.on_restore, None)
			return
		log.debug("Window is visible and signal received, minimizing")
		wx.CallAfter(self.frame.on_minimize, None)

	def open_conversation_file(self, data: OpenBskcSignal):
		"""Opens a conversation file from Windows IPC signal data.

		This method is called by the Windows IPC mechanism when an open_bskc signal is received.
		It extracts the file path from the signal data and opens the conversation.

		Args:
			data: Signal data containing the file path
		"""
		wx.CallAfter(self.frame.open_conversation, data.file_path)
		if not self.frame.IsShown():
			# Window is hidden, restore it
			log.debug("Window is hidden, restoring")
			wx.CallAfter(self.frame.on_restore, None)
		elif self.frame.IsIconized():
			# Window is iconized, restore it
			log.debug("Window is iconized, restoring")
			wx.CallAfter(self.frame.on_restore, None)
		else:
			# Window is visible, just force focus for screen readers
			log.debug("Window is visible, forcing focus for screen readers")
			wx.CallAfter(self.frame.force_focus_for_screen_reader)

	def init_ipc(self):
		"""Initializes the IPC mechanism for inter-process communication."""
		ipc_callbacks = {
			"send_focus": self.bring_window_to_focus,
			"open_bskc": self.open_conversation_file,
		}
		log.info("Initializing IPC mechanism")
		self.ipc = BasiliskIpc("basilisk_ipc")
		if self.ipc.start_receiver(ipc_callbacks):
			log.info("IPC receiver started successfully")
		else:
			log.error("Failed to initialize IPC")
