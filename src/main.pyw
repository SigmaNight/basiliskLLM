import logging
import os
import sys
import wx
import config
from consts import APP_NAME, APP_SOURCE_URL
from gui.mainframe import MainFrame
from localization import init_translation
from logger import setup_logging, logging_uncaught_exceptions
from providerengine import BaseEngine

sys.path.append(os.path.join(os.path.dirname(__file__), ""))

log = logging.getLogger(__name__)


class MainApp(wx.App):

	def OnInit(self) -> bool:
		self.conf = config.initialize_config()
		setup_logging(self.conf.general.log_level.name)
		log.debug(f"config: {self.conf}")
		self.locale = init_translation(self.conf.general.language)
		log.info("translation initialized")
		self.frame = MainFrame(None, title=APP_NAME, conf=self.conf)
		self.SetTopWindow(self.frame)
		self.frame.Show(True)
		log.info("Application started")
		return True

	def OnExit(self) -> int:
		log.info("Application exited")
		return 0


if __name__ == '__main__':
	sys.excepthook = logging_uncaught_exceptions
	app = MainApp()
	app.MainLoop()
