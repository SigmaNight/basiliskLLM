import argparse
import logging
import sys
import wx
import basilisk.globalvars as globalvars
import basilisk.config as config

# don't use relative import here, CxFreeze will fail to find the module
from basilisk.consts import APP_NAME
from basilisk.localization import init_translation
from basilisk.logger import (
	setup_logging,
	logging_uncaught_exceptions,
	get_log_file_path,
)
from basilisk.serverthread import ServerThread
from basilisk.soundmanager import initialize_sound_manager

log = logging.getLogger(__name__)


def parse_args():
	parser = argparse.ArgumentParser(
		description="Runs the application with customized configurations."
	)
	parser.add_argument(
		"--language", "-l", help="Set the application language", default=None
	)
	parser.add_argument(
		"--log_level",
		"-L",
		help="Set the logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)",
		default=None,
	)
	parser.add_argument(
		"--no-env-account",
		"-N",
		help="Disable loading accounts from environment variables",
		action="store_true",
	)
	return parser.parse_args()


class MainApp(wx.App):
	def OnInit(self) -> bool:
		globalvars.args = parse_args()
		log.debug(f"args: {globalvars.args}")

		self.conf = config.initialize_config()
		log_level = (
			globalvars.args.log_level or self.conf.general.log_level.name
		)
		setup_logging(log_level)
		log.debug(f"config: {self.conf}")
		if getattr(sys, "frozen", False):
			log.info(
				"running frozen application: redirecting stdio to log file"
			)
			self.RedirectStdio(str(get_log_file_path()))
		language = globalvars.args.language or self.conf.general.language
		self.locale = init_translation(language)
		log.info("translation initialized")
		initialize_sound_manager()
		log.info("sound manager initialized")
		from basilisk.gui.mainframe import MainFrame

		self.frame = MainFrame(None, title=APP_NAME, conf=self.conf)
		self.SetTopWindow(self.frame)
		self.frame.Show(True)
		self.server = None
		if self.conf.server.enable:
			self.server = ServerThread(self.frame, self.conf.server.port)
			self.server.start()
		log.info("Application started")
		return True

	def OnExit(self) -> int:
		if self.server:
			log.debug("Stopping server")
			self.server.stop()
			self.server.join()
			log.debug("Server stopped")
		log.info("Application exited")
		return 0


if __name__ == '__main__':
	sys.excepthook = logging_uncaught_exceptions
	app = MainApp()
	app.MainLoop()
