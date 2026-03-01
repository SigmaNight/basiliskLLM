"""Tests for OCRPresenter."""

from unittest.mock import MagicMock

import pytest

from basilisk.presenters.ocr_presenter import CHECK_TASK_DELAY, OCRPresenter
from basilisk.provider_capability import ProviderCapability


@pytest.fixture
def mock_view():
	"""Build a default mock view."""
	return MagicMock()


@pytest.fixture
def mock_engine():
	"""Build a mock engine with OCR capability and a client."""
	engine = MagicMock()
	engine.capabilities = {ProviderCapability.OCR}
	engine.client = MagicMock()
	return engine


def _make_default_account():
	"""Build a mock account with API key and provider base URL for OCR."""
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "sk-test"
	account.custom_base_url = None
	account.provider.base_url = "https://api.example.com"
	return account


@pytest.fixture
def mock_account():
	"""Build a mock account with a secret API key."""
	return _make_default_account()


@pytest.fixture
def presenter(mock_view, mock_engine, mock_account):
	"""Build an OCRPresenter with sensible defaults."""
	attachments = [MagicMock()]
	return OCRPresenter(
		view=mock_view,
		get_engine=lambda: mock_engine,
		get_attachments=lambda: attachments,
		get_account=lambda: mock_account,
		get_log_level=lambda: "DEBUG",
		check_attachments_valid=lambda: True,
		scheduler=None,
	)


_UNSET = object()


def _make_engine(has_ocr=True, client=_UNSET):
	"""Build a mock engine with configurable capabilities and client."""
	engine = MagicMock()
	engine.capabilities = {ProviderCapability.OCR} if has_ocr else set()
	engine.client = MagicMock() if client is _UNSET else client
	return engine


def _make_presenter(
	view=None,
	engine=None,
	attachments=None,
	account=None,
	log_level="DEBUG",
	attachments_valid=True,
	scheduler=None,
):
	"""Build an OCRPresenter with sensible defaults."""
	if view is None:
		view = MagicMock()
	if engine is None:
		engine = _make_engine()
	if attachments is None:
		attachments = [MagicMock()]
	if account is None:
		account = _make_default_account()
	return OCRPresenter(
		view=view,
		get_engine=lambda: engine,
		get_attachments=lambda: attachments,
		get_account=lambda: account,
		get_log_level=lambda: log_level,
		check_attachments_valid=lambda: attachments_valid,
		scheduler=scheduler,
	)


class TestOCRPresenterIsRunning:
	"""Tests for the is_running property."""

	def test_false_when_no_process(self, presenter):
		"""is_running is False when no process has been spawned."""
		assert presenter.is_running is False

	def test_true_when_process_alive(self, presenter):
		"""is_running is True when the process is alive."""
		presenter.process = MagicMock()
		presenter.process.is_alive.return_value = True
		assert presenter.is_running is True

	def test_false_when_process_dead(self, presenter):
		"""is_running is False when the process has terminated."""
		presenter.process = MagicMock()
		presenter.process.is_alive.return_value = False
		assert presenter.is_running is False


class TestOCRPresenterOnOcrValidation:
	"""Tests for the validation phase of on_ocr()."""

	def test_no_ocr_capability_shows_error(self, mock_view):
		"""When engine lacks OCR capability, show_error is called."""
		p = _make_presenter(view=mock_view, engine=_make_engine(has_ocr=False))
		p.on_ocr()
		mock_view.show_error.assert_called_once()
		mock_view.set_ocr_button_enabled.assert_not_called()

	def test_no_attachments_shows_error(self, mock_view):
		"""When attachment list is empty, show_error is called."""
		p = _make_presenter(view=mock_view, attachments=[])
		p.on_ocr()
		mock_view.show_error.assert_called_once()
		mock_view.set_ocr_button_enabled.assert_not_called()

	def test_attachments_invalid_returns_early(self, mock_view):
		"""When check_attachments_valid returns False, nothing more happens."""
		p = _make_presenter(view=mock_view, attachments_valid=False)
		p.on_ocr()
		mock_view.show_error.assert_not_called()
		mock_view.set_ocr_button_enabled.assert_not_called()

	def test_no_client_shows_error(self, mock_view):
		"""When engine.client is None/falsy, show_error is called."""
		p = _make_presenter(
			view=mock_view, engine=_make_engine(has_ocr=True, client=None)
		)
		p.on_ocr()
		mock_view.show_error.assert_called_once()
		mock_view.set_ocr_button_enabled.assert_not_called()


class TestOCRPresenterOnOcrStart:
	"""Tests for the process-spawn phase of on_ocr()."""

	def test_disables_button(self, mock_view, mocker):
		"""on_ocr() disables the OCR button before starting."""
		scheduler = MagicMock()
		mock_run = mocker.patch("basilisk.presenters.ocr_presenter.run_task")
		mock_run.return_value = MagicMock()
		p = _make_presenter(view=mock_view, scheduler=scheduler)
		p.on_ocr()
		mock_view.set_ocr_button_enabled.assert_any_call(False)

	def test_creates_progress_dialog(self, mock_view, mocker):
		"""on_ocr() creates a progress dialog via the view."""
		scheduler = MagicMock()
		mock_run = mocker.patch("basilisk.presenters.ocr_presenter.run_task")
		mock_run.return_value = MagicMock()
		p = _make_presenter(view=mock_view, scheduler=scheduler)
		p.on_ocr()
		mock_view.create_progress_dialog.assert_called_once()
		call_kwargs = mock_view.create_progress_dialog.call_args
		assert "title" in call_kwargs.kwargs or len(call_kwargs.args) >= 1

	def test_spawns_process(self, mock_view, mocker):
		"""on_ocr() calls run_task to spawn the OCR subprocess."""
		scheduler = MagicMock()
		mock_run = mocker.patch("basilisk.presenters.ocr_presenter.run_task")
		mock_process = MagicMock()
		mock_run.return_value = mock_process
		p = _make_presenter(view=mock_view, scheduler=scheduler)
		p.on_ocr()
		mock_run.assert_called_once()
		assert p.process is mock_process

	def test_schedules_first_progress_check(self, mock_view, mocker):
		"""on_ocr() schedules check_task_progress via the scheduler."""
		scheduler = MagicMock()
		mock_run = mocker.patch("basilisk.presenters.ocr_presenter.run_task")
		mock_run.return_value = MagicMock()
		p = _make_presenter(view=mock_view, scheduler=scheduler)
		p.on_ocr()
		scheduler.assert_called_once()
		delay, func = scheduler.call_args.args[:2]
		assert delay == CHECK_TASK_DELAY
		assert func == p.check_task_progress

	def test_passes_api_key_to_run_task(self, mock_view, mocker):
		"""on_ocr() forwards the account API key to run_task kwargs."""
		scheduler = MagicMock()
		account = MagicMock()
		account.api_key.get_secret_value.return_value = "sk-secret"
		account.custom_base_url = None
		account.provider.base_url = "https://api.example.com"
		mock_run = mocker.patch("basilisk.presenters.ocr_presenter.run_task")
		mock_run.return_value = MagicMock()
		p = _make_presenter(
			view=mock_view, account=account, scheduler=scheduler
		)
		p.on_ocr()
		_args, kwargs = mock_run.call_args
		assert kwargs.get("api_key") == "sk-secret"


class TestOCRPresenterCheckTaskProgress:
	"""Tests for the polling loop check_task_progress()."""

	def _make_dialog(self, cancelled=False):
		"""Build a mock progress dialog with configurable cancel state."""
		dialog = MagicMock()
		dialog.cancel_flag.value = 1 if cancelled else 0
		return dialog

	def _make_queue(self, empty=True):
		"""Build a mock result queue."""
		q = MagicMock()
		q.empty.return_value = empty
		return q

	def test_reschedules_while_process_alive(self, presenter, mock_view):
		"""check_task_progress reschedules itself when the process is alive."""
		scheduler = MagicMock()
		presenter._scheduler = scheduler
		presenter.process = MagicMock()
		presenter.process.is_alive.return_value = True
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		presenter.check_task_progress(dialog, queue, None)

		scheduler.assert_called_once()
		delay, func = scheduler.call_args.args[:2]
		assert delay == CHECK_TASK_DELAY
		assert func == presenter.check_task_progress

	def test_cleans_up_when_process_finishes(self, presenter, mock_view):
		"""check_task_progress cleans up when process is no longer alive."""
		scheduler = MagicMock()
		presenter._scheduler = scheduler
		presenter.process = MagicMock()
		presenter.process.is_alive.return_value = False
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		presenter.check_task_progress(dialog, queue, None)

		mock_view.set_ocr_button_enabled.assert_called_with(True)
		assert presenter.process is None
		scheduler.assert_not_called()

	def test_cleans_up_when_cancelled(self, presenter, mock_view):
		"""check_task_progress cleans up when user cancels."""
		scheduler = MagicMock()
		presenter._scheduler = scheduler
		presenter.process = MagicMock()
		presenter.process.is_alive.return_value = True  # still alive
		dialog = self._make_dialog(cancelled=True)  # but cancelled
		queue = self._make_queue(empty=True)

		presenter.check_task_progress(dialog, queue, None)

		mock_view.set_ocr_button_enabled.assert_called_with(True)
		assert presenter.process is None
		scheduler.assert_not_called()

	def test_cleans_up_when_no_process(self, presenter, mock_view):
		"""check_task_progress cleans up gracefully when process is None."""
		scheduler = MagicMock()
		presenter._scheduler = scheduler
		presenter.process = None
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		presenter.check_task_progress(dialog, queue, None)

		mock_view.set_ocr_button_enabled.assert_called_with(True)
		scheduler.assert_not_called()


class TestOCRPresenterHandleMessage:
	"""Tests for _handle_ocr_message and _handle_ocr_completion_message."""

	def _make_dialog(self):
		"""Build a mock dialog with cancel_flag.value = 0."""
		dialog = MagicMock()
		dialog.cancel_flag.value = 0
		return dialog

	def test_message_type_updates_dialog_message(self, presenter):
		"""'message' type calls dialog.update_message with string data."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("message", "Processing file 1...", dialog)
		dialog.update_message.assert_called_once_with("Processing file 1...")

	def test_message_type_ignores_empty_string(self, presenter):
		"""'message' type with empty string does not call update_message."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("message", "", dialog)
		dialog.update_message.assert_not_called()

	def test_message_type_ignores_non_string(self, presenter):
		"""'message' type with non-string data does not call update_message."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("message", 42, dialog)
		dialog.update_message.assert_not_called()

	def test_progress_type_updates_gauge(self, presenter):
		"""'progress' type calls dialog.update_progress_bar with int data."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("progress", 75, dialog)
		dialog.update_progress_bar.assert_called_once_with(75)

	def test_progress_type_ignores_non_int(self, presenter):
		"""'progress' type with non-integer data is ignored."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("progress", "75%", dialog)
		dialog.update_progress_bar.assert_not_called()

	def test_result_type_destroys_dialog_and_shows_result(
		self, presenter, mock_view
	):
		"""'result' type destroys the dialog, re-enables button, shows result."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("result", ["output.txt"], dialog)
		mock_view.destroy_progress_dialog.assert_called_once_with(dialog)
		mock_view.set_ocr_button_enabled.assert_called_with(True)
		mock_view.show_result.assert_called_once_with(["output.txt"])

	def test_error_type_destroys_dialog_and_shows_error(
		self, presenter, mock_view
	):
		"""'error' type destroys the dialog, re-enables button, shows error."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message("error", "Something went wrong", dialog)
		mock_view.destroy_progress_dialog.assert_called_once_with(dialog)
		mock_view.set_ocr_button_enabled.assert_called_with(True)
		mock_view.show_error.assert_called_once_with(
			"Something went wrong", _("OCR Error")
		)

	def test_unknown_type_does_not_crash(self, presenter, mock_view):
		"""Unknown message types are silently logged without raising."""
		dialog = self._make_dialog()
		presenter._handle_ocr_message(
			"unknown_type", None, dialog
		)  # must not raise
		mock_view.show_result.assert_not_called()
		mock_view.show_error.assert_not_called()

	def test_completion_no_op_when_dialog_is_none(self, presenter, mock_view):
		"""_handle_ocr_completion_message is a no-op when dialog is falsy."""
		presenter._handle_ocr_completion_message("result", "data", None)
		mock_view.destroy_progress_dialog.assert_not_called()
		mock_view.show_result.assert_not_called()


class TestOCRPresenterProcessQueue:
	"""Tests for _process_ocr_queue."""

	def test_drains_multiple_messages(self, presenter):
		"""_process_ocr_queue drains all pending messages."""
		dialog = MagicMock()
		dialog.cancel_flag.value = 0

		queue = MagicMock()
		queue.empty.side_effect = [False, False, True]
		queue.get.side_effect = [("message", "step 1"), ("progress", 50)]

		presenter._process_ocr_queue(queue, dialog)

		dialog.update_message.assert_called_once_with("step 1")
		dialog.update_progress_bar.assert_called_once_with(50)

	def test_empty_queue_does_nothing(self, presenter):
		"""_process_ocr_queue is a no-op on an empty queue."""
		dialog = MagicMock()
		queue = MagicMock()
		queue.empty.return_value = True

		presenter._process_ocr_queue(queue, dialog)

		queue.get.assert_not_called()
