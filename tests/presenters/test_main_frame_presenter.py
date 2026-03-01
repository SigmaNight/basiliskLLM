"""Tests for MainFramePresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.main_frame_presenter import MainFramePresenter


@pytest.fixture
def mock_view():
	"""Return a mock MainFrame view with required attributes."""
	view = MagicMock()
	view.conf = MagicMock()
	view.conf.conversation.reopen_last_conversation = False
	view.conf.conversation.last_active_conversation_id = None
	view.conf.general.quit_on_close = True
	view.notebook = MagicMock()
	view.tabs_panels = []
	view.current_tab = MagicMock()
	view.current_tab.db_conv_id = None
	view.current_tab.bskc_path = None
	view.add_conversation_tab = MagicMock()
	view.refresh_frame_title = MagicMock()
	view.refresh_tab_title = MagicMock()
	view.refresh_tabs = MagicMock()
	view.on_save_as_conversation = MagicMock(return_value=None)
	view.IsShown.return_value = True
	return view


@pytest.fixture
def presenter(mock_view):
	"""Return a MainFramePresenter with a mocked view."""
	return MainFramePresenter(view=mock_view)


class TestGetDefaultConvTitle:
	"""Tests for get_default_conv_title."""

	def test_increments_counter(self, presenter):
		"""Counter should increment on each call."""
		title1 = presenter.get_default_conv_title()
		title2 = presenter.get_default_conv_title()
		assert presenter.last_conversation_id == 2
		assert "1" in title1
		assert "2" in title2

	def test_starts_at_zero(self, presenter):
		"""Counter starts at 0 before first call."""
		assert presenter.last_conversation_id == 0
		presenter.get_default_conv_title()
		assert presenter.last_conversation_id == 1


class TestTryReopenLastConversation:
	"""Tests for try_reopen_last_conversation."""

	@pytest.mark.parametrize(
		("reopen", "conv_id"),
		[(False, None), (True, None)],
		ids=["config_off", "no_id"],
	)
	def test_returns_false_early(self, presenter, mock_view, reopen, conv_id):
		"""Returns False when config disabled or no last conversation ID."""
		mock_view.conf.conversation.reopen_last_conversation = reopen
		mock_view.conf.conversation.last_active_conversation_id = conv_id
		assert presenter.try_reopen_last_conversation() is False

	def test_returns_true_on_success(self, presenter, mock_view, mocker):
		"""Should return True and add tab when reopening succeeds."""
		mock_view.conf.conversation.reopen_last_conversation = True
		mock_view.conf.conversation.last_active_conversation_id = 42
		mock_tab = MagicMock()
		mock_open_from_db = mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_from_db",
			return_value=mock_tab,
		)

		result = presenter.try_reopen_last_conversation()

		assert result is True
		mock_open_from_db.assert_called_once()
		mock_view.add_conversation_tab.assert_called_once_with(mock_tab)

	def test_handles_exception(self, presenter, mock_view, mocker):
		"""Should return False and clear config on exception."""
		mock_view.conf.conversation.reopen_last_conversation = True
		mock_view.conf.conversation.last_active_conversation_id = 99
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_from_db",
			side_effect=RuntimeError("DB error"),
		)

		result = presenter.try_reopen_last_conversation()

		assert result is False
		assert mock_view.conf.conversation.last_active_conversation_id is None
		mock_view.conf.save.assert_called_once()


class TestFlushAndSaveOnQuit:
	"""Tests for flush_and_save_on_quit."""

	def test_flushes_all_tabs(self, presenter, mock_view):
		"""Should call cleanup_resources on each tab."""
		tab1 = MagicMock()
		tab2 = MagicMock()
		mock_view.tabs_panels = [tab1, tab2]
		mock_view.conf.conversation.reopen_last_conversation = False

		presenter.flush_and_save_on_quit()

		tab1.cleanup_resources.assert_called_once()
		tab2.cleanup_resources.assert_called_once()

	@pytest.mark.parametrize(
		("db_conv_id", "expected_id"),
		[(42, 42), (None, None)],
		ids=["with_id", "no_id"],
	)
	def test_saves_last_conv_id(
		self, presenter, mock_view, db_conv_id, expected_id
	):
		"""Saves or clears last_active_conversation_id based on db_conv_id."""
		mock_view.conf.conversation.reopen_last_conversation = True
		mock_view.current_tab.db_conv_id = db_conv_id
		mock_view.tabs_panels = []

		presenter.flush_and_save_on_quit()

		assert (
			mock_view.conf.conversation.last_active_conversation_id
			== expected_id
		)
		mock_view.conf.save.assert_called_once()


class TestNewConversation:
	"""Tests for new_conversation."""

	def test_creates_tab_and_adds_to_view(self, presenter, mock_view, mocker):
		"""Should create a ConversationTab and add it to the view."""
		mock_init = mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.__init__",
			return_value=None,
		)
		profile = MagicMock()

		presenter.new_conversation(profile)

		mock_init.assert_called_once()
		mock_view.add_conversation_tab.assert_called_once()


class TestOpenConversation:
	"""Tests for open_conversation."""

	def test_success(self, presenter, mock_view, mocker):
		"""Should add tab when opening succeeds."""
		mock_tab = MagicMock()
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_conversation",
			return_value=mock_tab,
		)

		presenter.open_conversation("/path/to/file.bskc")

		mock_view.add_conversation_tab.assert_called_once_with(mock_tab)

	def test_error_shows_message(self, presenter, mock_view, mocker):
		"""Should show error dialog when opening fails."""
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_conversation",
			side_effect=RuntimeError("bad file"),
		)

		presenter.open_conversation("/bad/file.bskc")

		mock_view.show_error.assert_called_once()
		mock_view.add_conversation_tab.assert_not_called()


class TestOpenFromDb:
	"""Tests for open_from_db."""

	def test_success(self, presenter, mock_view, mocker):
		"""Should add tab when opening from DB succeeds."""
		mock_tab = MagicMock()
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_from_db",
			return_value=mock_tab,
		)

		presenter.open_from_db(42)

		mock_view.add_conversation_tab.assert_called_once_with(mock_tab)

	def test_error_shows_message(self, presenter, mock_view, mocker):
		"""Should show error dialog when DB open fails."""
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.open_from_db",
			side_effect=RuntimeError("DB error"),
		)

		presenter.open_from_db(99)

		mock_view.show_error.assert_called_once()
		mock_view.add_conversation_tab.assert_not_called()


class TestCloseConversation:
	"""Tests for close_conversation."""

	def test_does_nothing_when_not_found(self, presenter, mock_view):
		"""Should do nothing when no tab is selected."""
		import wx

		mock_view.notebook.GetSelection.return_value = wx.NOT_FOUND

		presenter.close_conversation()

		mock_view.notebook.DeletePage.assert_not_called()

	def test_creates_new_tab_when_last_closed(
		self, presenter, mock_view, mocker
	):
		"""Should create new default conversation when last tab is closed."""
		mock_config = mocker.patch(
			"basilisk.presenters.main_frame_presenter.config"
		)
		mock_view.notebook.GetSelection.return_value = 0
		mock_view.tabs_panels = [MagicMock()]
		mock_view.notebook.GetPageCount.return_value = 0
		mock_config.accounts.return_value = True
		mock_config.conversation_profiles.return_value.default_profile = None

		mocker.patch.object(presenter, "on_new_default_conversation")
		presenter.close_conversation()
		presenter.on_new_default_conversation.assert_called_once()

	def test_selects_last_tab_when_remaining(self, presenter, mock_view):
		"""Should select the last tab when tabs remain."""
		mock_view.notebook.GetSelection.return_value = 0
		mock_view.tabs_panels = [MagicMock(), MagicMock()]
		mock_view.notebook.GetPageCount.return_value = 1

		presenter.close_conversation()

		mock_view.notebook.SetSelection.assert_called_once_with(0)
		mock_view.refresh_frame_title.assert_called_once()


class TestSaveCurrentConversation:
	"""Tests for save_current_conversation."""

	def test_delegates_save_as_when_no_path(self, presenter, mock_view):
		"""Should trigger save-as when no bskc_path is set."""
		mock_view.current_tab.bskc_path = None

		presenter.save_current_conversation()

		mock_view.on_save_as_conversation.assert_called_once_with(None)

	def test_saves_when_path_exists(self, presenter, mock_view):
		"""Should save directly when bskc_path exists."""
		mock_view.current_tab.bskc_path = "/path/to/file.bskc"

		presenter.save_current_conversation()

		mock_view.current_tab.save_conversation.assert_called_once_with(
			"/path/to/file.bskc"
		)


class TestSaveConversationAs:
	"""Tests for save_conversation_as."""

	def test_saves_and_updates_path(self, presenter, mock_view):
		"""Should save and update bskc_path on success."""
		mock_view.current_tab.save_conversation.return_value = True

		result = presenter.save_conversation_as("/new/path.bskc")

		assert result is True
		assert mock_view.current_tab.bskc_path == "/new/path.bskc"

	def test_returns_false_on_failure(self, presenter, mock_view):
		"""Should return False on save failure."""
		mock_view.current_tab.save_conversation.return_value = False

		result = presenter.save_conversation_as("/new/path.bskc")

		assert result is False


class TestHandleNoAccountConfigured:
	"""Tests for handle_no_account_configured."""

	def test_does_nothing_when_accounts_exist(
		self, presenter, mock_view, mocker
	):
		"""Should do nothing when accounts are already configured."""
		mock_config = mocker.patch(
			"basilisk.presenters.main_frame_presenter.config"
		)
		mock_wx = mocker.patch("basilisk.presenters.main_frame_presenter.wx")
		mock_config.accounts.return_value = [MagicMock()]

		presenter.handle_no_account_configured()

		mock_wx.MessageBox.assert_not_called()

	def test_shows_dialog_when_no_accounts(self, presenter, mock_view, mocker):
		"""Should show confirmation dialog when no accounts exist."""
		mock_config = mocker.patch(
			"basilisk.presenters.main_frame_presenter.config"
		)
		mock_wx = mocker.patch("basilisk.presenters.main_frame_presenter.wx")
		mock_config.accounts.return_value = []
		mock_wx.YES_NO = 0x2 | 0x4
		mock_wx.ICON_QUESTION = 0x100
		mock_wx.YES = 0x2
		mock_wx.MessageBox.return_value = mock_wx.NO

		presenter.handle_no_account_configured()

		mock_wx.MessageBox.assert_called_once()


class TestTogglePrivacy:
	"""Tests for toggle_privacy."""

	@pytest.mark.parametrize(
		("current", "expected"),
		[(False, True), (True, False)],
		ids=["toggle_on", "toggle_off"],
	)
	def test_toggles_private_flag(
		self, presenter, mock_view, current, expected
	):
		"""Should call set_private with the negated current flag."""
		mock_view.current_tab.private = current

		presenter.toggle_privacy()

		mock_view.current_tab.set_private.assert_called_once_with(expected)

	def test_does_nothing_when_no_tab(self, presenter, mock_view):
		"""Should do nothing when no current tab."""
		mock_view.current_tab = None

		presenter.toggle_privacy()  # Should not raise


class TestScreenCapture:
	"""Tests for screen_capture."""

	def test_error_when_no_tab(self, presenter, mock_view):
		"""Should show error when no conversation is selected."""
		from basilisk.screen_capture_thread import CaptureMode

		mock_view.current_tab = None

		presenter.screen_capture(CaptureMode.FULL)

		mock_view.show_error.assert_called_once()

	def test_starts_capture_thread(self, presenter, mock_view, mocker):
		"""Should start a capture thread."""
		from basilisk.screen_capture_thread import CaptureMode

		mock_thread_cls = mocker.patch(
			"basilisk.presenters.main_frame_presenter.ScreenCaptureThread"
		)
		mock_view.current_tab.conv_storage_path = MagicMock()
		mock_view.current_tab.conv_storage_path.__truediv__ = MagicMock(
			return_value="path"
		)

		presenter.screen_capture(CaptureMode.FULL)

		mock_thread_cls.assert_called_once()
		mock_thread_cls.return_value.start.assert_called_once()


class TestOnNewDefaultConversation:
	"""Tests for on_new_default_conversation."""

	def test_creates_conversation_with_default_profile(
		self, presenter, mock_view, mocker
	):
		"""Should create a new conversation with the default profile."""
		mock_config = mocker.patch(
			"basilisk.presenters.main_frame_presenter.config"
		)
		mocker.patch(
			"basilisk.views.conversation_tab.ConversationTab.__init__",
			return_value=None,
		)
		mock_config.accounts.return_value = [MagicMock()]
		profile = MagicMock()
		mock_config.conversation_profiles.return_value.default_profile = profile

		presenter.on_new_default_conversation()

		mock_view.add_conversation_tab.assert_called_once()
