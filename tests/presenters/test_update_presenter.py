"""Tests for UpdatePresenter and DownloadPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.update_presenter import (
	DownloadPresenter,
	UpdatePresenter,
)


def _make_updater(
	is_update_enable=True,
	update_available=True,
	current_version="1.0.0",
	latest_version="2.0.0",
	release_notes="What's new",
	downloaded_file=None,
):
	"""Build a mock BaseUpdater with configurable attributes."""
	updater = MagicMock()
	updater.is_update_enable = is_update_enable
	updater.is_update_available.return_value = update_available
	updater.current_version = current_version
	updater.latest_version = latest_version
	updater.release_notes = release_notes
	if downloaded_file is None:
		del updater.downloaded_file
		updater.configure_mock(**{"downloaded_file": None})
	else:
		updater.downloaded_file = downloaded_file
	return updater


@pytest.fixture
def mock_updater():
	"""Build a mock BaseUpdater with typical defaults."""
	return _make_updater()


class TestUpdatePresenterStart:
	"""Tests for UpdatePresenter.start()."""

	def test_with_updater_shows_update_available_immediately(
		self, mock_updater
	):
		"""When an updater is provided, show_update_available is called at once."""
		view = MagicMock()
		mock_updater.current_version = "1.0"
		mock_updater.latest_version = "2.0"
		presenter = UpdatePresenter(view=view, updater=mock_updater)
		presenter.start()
		view.show_update_available.assert_called_once_with("1.0", "2.0", True)

	def test_with_updater_no_release_notes(self, mock_updater):
		"""has_notes is False when release_notes is empty."""
		view = MagicMock()
		mock_updater.release_notes = ""
		presenter = UpdatePresenter(view=view, updater=mock_updater)
		presenter.start()
		_cur, _lat, has_notes = view.show_update_available.call_args.args
		assert has_notes is False

	def test_with_updater_does_not_start_thread(self, mock_updater):
		"""No check thread is started when updater is already provided."""
		view = MagicMock()
		presenter = UpdatePresenter(view=view, updater=mock_updater)
		presenter.start()
		assert presenter._check_thread is None

	def test_without_updater_updates_disabled_shows_error_and_closes(
		self, mocker
	):
		"""When is_update_enable is False, show_error and close are called."""
		view = MagicMock()
		mock_upd = _make_updater(is_update_enable=False)
		mocker.patch(
			"basilisk.updater.get_updater_from_channel", return_value=mock_upd
		)
		mocker.patch("basilisk.config.conf")
		presenter = UpdatePresenter(view=view)
		presenter.start()

		view.show_error.assert_called_once()
		view.close.assert_called_once()
		view.show_checking_state.assert_not_called()

	def test_without_updater_starts_check_thread(self, mocker):
		"""When updates are enabled, a check thread is started."""
		view = MagicMock()
		mock_upd = _make_updater(is_update_enable=True)
		mocker.patch(
			"basilisk.updater.get_updater_from_channel", return_value=mock_upd
		)
		mocker.patch("basilisk.config.conf")
		mocker.patch("wx.CallAfter")
		presenter = UpdatePresenter(view=view)
		presenter.start()
		presenter._check_thread.join(timeout=2)

		view.show_checking_state.assert_called_once_with("1.0.0")
		assert presenter._check_thread is not None
		assert presenter._check_thread.daemon is True

	def test_without_updater_shows_checking_state_with_version(self, mocker):
		"""show_checking_state receives the current version string."""
		view = MagicMock()
		mock_upd = _make_updater(is_update_enable=True, current_version="3.5.1")
		mocker.patch(
			"basilisk.updater.get_updater_from_channel", return_value=mock_upd
		)
		mocker.patch("basilisk.config.conf")
		mocker.patch("wx.CallAfter")
		presenter = UpdatePresenter(view=view)
		presenter.start()
		presenter._check_thread.join(timeout=2)

		view.show_checking_state.assert_called_once_with("3.5.1")


class TestUpdatePresenterDoCheck:
	"""Tests for UpdatePresenter._do_check() called directly (no thread)."""

	def test_update_available_calls_show_update_available(
		self, mock_updater, mocker
	):
		"""When update is available, wx.CallAfter enqueues show_update_available."""
		view = MagicMock()
		mock_updater.current_version = "1.0"
		mock_updater.latest_version = "2.0"
		mock_updater.release_notes = "Notes"
		presenter = UpdatePresenter(view=view, updater=mock_updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_check()

		mock_call_after.assert_any_call(
			view.show_update_available, "1.0", "2.0", True
		)

	def test_no_update_calls_show_no_updates(self, mocker):
		"""When no update is available, wx.CallAfter enqueues show_no_updates."""
		view = MagicMock()
		updater = _make_updater(update_available=False)
		presenter = UpdatePresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_check()

		mock_call_after.assert_any_call(view.show_no_updates)

	def test_exception_calls_show_error_and_close(self, mocker):
		"""On exception, wx.CallAfter enqueues show_error then close."""
		view = MagicMock()
		updater = MagicMock()
		updater.is_update_available.side_effect = RuntimeError("network error")
		presenter = UpdatePresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_check()

		calls = mock_call_after.call_args_list
		funcs = [c.args[0] for c in calls]
		assert view.show_error in funcs
		assert view.close in funcs

	def test_exception_does_not_call_show_no_updates(self, mocker):
		"""On exception, show_no_updates is not enqueued."""
		view = MagicMock()
		updater = MagicMock()
		updater.is_update_available.side_effect = ValueError("oops")
		presenter = UpdatePresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_check()

		calls = mock_call_after.call_args_list
		funcs = [c.args[0] for c in calls]
		assert view.show_no_updates not in funcs


class TestUpdatePresenterEventHandlers:
	"""Tests for UpdatePresenter button / close events."""

	def test_on_update_clicked_delegates_download_and_closes(
		self, mock_updater
	):
		"""on_update_clicked() calls view.start_download then view.close."""
		view = MagicMock()
		presenter = UpdatePresenter(view=view, updater=mock_updater)
		presenter.on_update_clicked()
		view.start_download.assert_called_once_with(mock_updater)
		view.close.assert_called_once()

	def test_on_close_calls_view_close(self):
		"""on_close() delegates to view.close()."""
		view = MagicMock()
		presenter = UpdatePresenter(view=view)
		presenter.on_close()
		view.close.assert_called_once()

	def test_on_release_notes_clicked_calls_view(self):
		"""on_release_notes_clicked() delegates to view.open_release_notes()."""
		view = MagicMock()
		presenter = UpdatePresenter(view=view)
		presenter.on_release_notes_clicked()
		view.open_release_notes.assert_called_once()


class TestDownloadPresenterStart:
	"""Tests for DownloadPresenter.start()."""

	def test_already_downloaded_shows_finished_immediately(self):
		"""When downloaded_file is set, show_download_finished is called."""
		view = MagicMock()
		updater = _make_updater(
			downloaded_file="/tmp/update.exe", release_notes="Notes"
		)
		presenter = DownloadPresenter(view=view, updater=updater)
		presenter.start()
		view.show_download_finished.assert_called_once_with(True)

	def test_already_downloaded_no_notes(self):
		"""has_notes is False when release_notes is empty."""
		view = MagicMock()
		updater = _make_updater(
			downloaded_file="/tmp/update.exe", release_notes=""
		)
		presenter = DownloadPresenter(view=view, updater=updater)
		presenter.start()
		(has_notes,) = view.show_download_finished.call_args.args
		assert has_notes is False

	def test_not_downloaded_starts_thread(self, mocker):
		"""When not yet downloaded, a download thread is started."""
		view = MagicMock()
		updater = _make_updater()  # downloaded_file=None
		updater.download.return_value = False
		presenter = DownloadPresenter(view=view, updater=updater)
		mocker.patch("wx.CallAfter")
		presenter.start()
		presenter._download_thread.join(timeout=2)
		assert presenter._download_thread is not None

	def test_not_downloaded_thread_is_daemon(self, mocker):
		"""The download thread is a daemon thread."""
		view = MagicMock()
		updater = _make_updater()
		updater.download.return_value = False
		presenter = DownloadPresenter(view=view, updater=updater)
		mocker.patch("wx.CallAfter")
		presenter.start()
		presenter._download_thread.join(timeout=2)
		assert presenter._download_thread.daemon is True


class TestDownloadPresenterDoDownload:
	"""Tests for DownloadPresenter._do_download() called directly."""

	def test_successful_download_calls_show_finished(self, mocker):
		"""On success, wx.CallAfter enqueues show_download_finished."""
		view = MagicMock()
		updater = MagicMock()
		updater.download.return_value = True
		updater.release_notes = "Notes"
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_download()

		mock_call_after.assert_any_call(view.show_download_finished, True)

	def test_download_returns_false_does_not_show_finished(self, mocker):
		"""When download() returns False (cancelled), show_download_finished is not called."""
		view = MagicMock()
		updater = MagicMock()
		updater.download.return_value = False
		updater.release_notes = ""
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_download()

		calls = mock_call_after.call_args_list
		funcs = [c.args[0] for c in calls]
		assert view.show_download_finished not in funcs

	def test_exception_calls_show_error(self, mocker):
		"""On download exception, wx.CallAfter enqueues show_error."""
		view = MagicMock()
		updater = MagicMock()
		updater.download.side_effect = IOError("connection reset")
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._do_download()

		calls = mock_call_after.call_args_list
		funcs = [c.args[0] for c in calls]
		assert view.show_error in funcs

	def test_stop_download_flag_forwarded(self, mocker):
		"""The _stop_download flag is passed to updater.download()."""
		view = MagicMock()
		updater = MagicMock()
		updater.download.return_value = False
		presenter = DownloadPresenter(view=view, updater=updater)
		presenter._stop_download = True
		mocker.patch("wx.CallAfter")

		presenter._do_download()

		_args, _kwargs = updater.download.call_args
		assert _args[1] is True


class TestDownloadPresenterProgress:
	"""Tests for DownloadPresenter._on_progress()."""

	def test_progress_enqueues_view_update(self, mocker):
		"""_on_progress() calls wx.CallAfter(view.update_download_progress, pct)."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._on_progress(50, 100)

		mock_call_after.assert_called_once_with(
			view.update_download_progress, 50
		)

	def test_progress_rounds_to_int(self, mocker):
		"""Progress percentage is an integer (int division)."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._on_progress(1, 3)  # 33.33...%

		_fn, pct = mock_call_after.call_args.args
		assert isinstance(pct, int)
		assert pct == 33

	def test_full_download_gives_100(self, mocker):
		"""Progress at full download gives exactly 100%."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_call_after = mocker.patch("wx.CallAfter")

		presenter._on_progress(1024, 1024)

		_fn, pct = mock_call_after.call_args.args
		assert pct == 100


class TestDownloadPresenterEventHandlers:
	"""Tests for DownloadPresenter button events."""

	def test_on_update_clicked_runs_installer_and_closes(self, mocker):
		"""on_update_clicked() calls updater.update(), view.close(), then exits app."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		mock_get_app = mocker.patch("wx.GetApp")

		presenter.on_update_clicked()

		updater.update.assert_called_once()
		view.close.assert_called_once()
		mock_get_app.return_value.GetTopWindow.return_value.Close.assert_called_once()

	def test_on_cancel_sets_flag_and_closes(self):
		"""on_cancel() sets _stop_download=True and calls view.close()."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		assert presenter._stop_download is False
		presenter.on_cancel()
		assert presenter._stop_download is True
		view.close.assert_called_once()

	def test_on_release_notes_clicked_calls_view(self):
		"""on_release_notes_clicked() delegates to view.open_release_notes()."""
		view = MagicMock()
		updater = MagicMock()
		presenter = DownloadPresenter(view=view, updater=updater)
		presenter.on_release_notes_clicked()
		view.open_release_notes.assert_called_once()
