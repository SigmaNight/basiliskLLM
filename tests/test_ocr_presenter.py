"""Tests for OCRPresenter."""

from unittest.mock import MagicMock, patch

from basilisk.presenters.ocr_presenter import CHECK_TASK_DELAY, OCRPresenter
from basilisk.provider_capability import ProviderCapability

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_engine(has_ocr=True, client=MagicMock()):
	"""Build a mock engine with configurable capabilities and client."""
	engine = MagicMock()
	engine.capabilities = {ProviderCapability.OCR} if has_ocr else set()
	engine.client = client
	return engine


def make_account():
	"""Build a mock account with a secret API key."""
	account = MagicMock()
	account.api_key.get_secret_value.return_value = "sk-test"
	account.custom_base_url = None
	account.provider.base_url = "https://api.example.com"
	return account


def make_presenter(
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
		engine = make_engine()
	if attachments is None:
		attachments = [MagicMock()]  # non-empty
	if account is None:
		account = make_account()

	return OCRPresenter(
		view=view,
		get_engine=lambda: engine,
		get_attachments=lambda: attachments,
		get_account=lambda: account,
		get_log_level=lambda: log_level,
		check_attachments_valid=lambda: attachments_valid,
		scheduler=scheduler,
	)


# ---------------------------------------------------------------------------
# OCRPresenter — is_running
# ---------------------------------------------------------------------------


class TestOCRPresenterIsRunning:
	"""Tests for the is_running property."""

	def test_false_when_no_process(self):
		"""is_running is False when no process has been spawned."""
		p = make_presenter()
		assert p.is_running is False

	def test_true_when_process_alive(self):
		"""is_running is True when the process is alive."""
		p = make_presenter()
		p.process = MagicMock()
		p.process.is_alive.return_value = True
		assert p.is_running is True

	def test_false_when_process_dead(self):
		"""is_running is False when the process has terminated."""
		p = make_presenter()
		p.process = MagicMock()
		p.process.is_alive.return_value = False
		assert p.is_running is False


# ---------------------------------------------------------------------------
# OCRPresenter — on_ocr validation
# ---------------------------------------------------------------------------


class TestOCRPresenterOnOcrValidation:
	"""Tests for the validation phase of on_ocr()."""

	def test_no_ocr_capability_shows_error(self):
		"""When engine lacks OCR capability, show_error is called."""
		view = MagicMock()
		engine = make_engine(has_ocr=False)
		p = make_presenter(view=view, engine=engine)
		p.on_ocr()
		view.show_error.assert_called_once()
		view.set_ocr_button_enabled.assert_not_called()

	def test_no_attachments_shows_error(self):
		"""When attachment list is empty, show_error is called."""
		view = MagicMock()
		p = make_presenter(view=view, attachments=[])
		p.on_ocr()
		view.show_error.assert_called_once()
		view.set_ocr_button_enabled.assert_not_called()

	def test_attachments_invalid_returns_early(self):
		"""When check_attachments_valid returns False, nothing more happens."""
		view = MagicMock()
		p = make_presenter(view=view, attachments_valid=False)
		p.on_ocr()
		view.show_error.assert_not_called()
		view.set_ocr_button_enabled.assert_not_called()

	def test_no_client_shows_error(self):
		"""When engine.client is None/falsy, show_error is called."""
		view = MagicMock()
		engine = make_engine(has_ocr=True, client=None)
		p = make_presenter(view=view, engine=engine)
		p.on_ocr()
		view.show_error.assert_called_once()
		view.set_ocr_button_enabled.assert_not_called()


# ---------------------------------------------------------------------------
# OCRPresenter — on_ocr successful start
# ---------------------------------------------------------------------------


class TestOCRPresenterOnOcrStart:
	"""Tests for the process-spawn phase of on_ocr()."""

	def test_disables_button(self):
		"""on_ocr() disables the OCR button before starting."""
		view = MagicMock()
		scheduler = MagicMock()
		with patch("basilisk.presenters.ocr_presenter.run_task") as mock_run:
			mock_run.return_value = MagicMock()
			p = make_presenter(view=view, scheduler=scheduler)
			p.on_ocr()
		view.set_ocr_button_enabled.assert_any_call(False)

	def test_creates_progress_dialog(self):
		"""on_ocr() creates a progress dialog via the view."""
		view = MagicMock()
		scheduler = MagicMock()
		with patch("basilisk.presenters.ocr_presenter.run_task") as mock_run:
			mock_run.return_value = MagicMock()
			p = make_presenter(view=view, scheduler=scheduler)
			p.on_ocr()
		view.create_progress_dialog.assert_called_once()
		call_kwargs = view.create_progress_dialog.call_args
		assert "title" in call_kwargs.kwargs or len(call_kwargs.args) >= 1

	def test_spawns_process(self):
		"""on_ocr() calls run_task to spawn the OCR subprocess."""
		view = MagicMock()
		scheduler = MagicMock()
		with patch("basilisk.presenters.ocr_presenter.run_task") as mock_run:
			mock_process = MagicMock()
			mock_run.return_value = mock_process
			p = make_presenter(view=view, scheduler=scheduler)
			p.on_ocr()
		mock_run.assert_called_once()
		assert p.process is mock_process

	def test_schedules_first_progress_check(self):
		"""on_ocr() schedules check_task_progress via the scheduler."""
		view = MagicMock()
		scheduler = MagicMock()
		with patch("basilisk.presenters.ocr_presenter.run_task") as mock_run:
			mock_run.return_value = MagicMock()
			p = make_presenter(view=view, scheduler=scheduler)
			p.on_ocr()
		scheduler.assert_called_once()
		delay, func = scheduler.call_args.args[:2]
		assert delay == CHECK_TASK_DELAY
		assert func == p.check_task_progress

	def test_passes_api_key_to_run_task(self):
		"""on_ocr() forwards the account API key to run_task kwargs."""
		view = MagicMock()
		scheduler = MagicMock()
		account = make_account()
		account.api_key.get_secret_value.return_value = "sk-secret"
		with patch("basilisk.presenters.ocr_presenter.run_task") as mock_run:
			mock_run.return_value = MagicMock()
			p = make_presenter(view=view, account=account, scheduler=scheduler)
			p.on_ocr()
		_args, kwargs = mock_run.call_args
		assert kwargs.get("api_key") == "sk-secret"


# ---------------------------------------------------------------------------
# OCRPresenter — check_task_progress
# ---------------------------------------------------------------------------


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

	def test_reschedules_while_process_alive(self):
		"""check_task_progress reschedules itself when the process is alive."""
		view = MagicMock()
		scheduler = MagicMock()
		p = make_presenter(view=view, scheduler=scheduler)
		p.process = MagicMock()
		p.process.is_alive.return_value = True
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		p.check_task_progress(dialog, queue, None)

		scheduler.assert_called_once()
		delay, func = scheduler.call_args.args[:2]
		assert delay == CHECK_TASK_DELAY
		assert func == p.check_task_progress

	def test_cleans_up_when_process_finishes(self):
		"""check_task_progress cleans up when process is no longer alive."""
		view = MagicMock()
		scheduler = MagicMock()
		p = make_presenter(view=view, scheduler=scheduler)
		p.process = MagicMock()
		p.process.is_alive.return_value = False
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		p.check_task_progress(dialog, queue, None)

		# Cleanup: button re-enabled, process set to None
		view.set_ocr_button_enabled.assert_called_with(True)
		assert p.process is None
		scheduler.assert_not_called()

	def test_cleans_up_when_cancelled(self):
		"""check_task_progress cleans up when user cancels."""
		view = MagicMock()
		scheduler = MagicMock()
		p = make_presenter(view=view, scheduler=scheduler)
		p.process = MagicMock()
		p.process.is_alive.return_value = True  # still alive
		dialog = self._make_dialog(cancelled=True)  # but cancelled
		queue = self._make_queue(empty=True)

		p.check_task_progress(dialog, queue, None)

		view.set_ocr_button_enabled.assert_called_with(True)
		assert p.process is None
		scheduler.assert_not_called()

	def test_cleans_up_when_no_process(self):
		"""check_task_progress cleans up gracefully when process is None."""
		view = MagicMock()
		scheduler = MagicMock()
		p = make_presenter(view=view, scheduler=scheduler)
		p.process = None
		dialog = self._make_dialog(cancelled=False)
		queue = self._make_queue(empty=True)

		p.check_task_progress(dialog, queue, None)

		view.set_ocr_button_enabled.assert_called_with(True)
		scheduler.assert_not_called()


# ---------------------------------------------------------------------------
# OCRPresenter — message handling
# ---------------------------------------------------------------------------


class TestOCRPresenterHandleMessage:
	"""Tests for _handle_ocr_message and _handle_ocr_completion_message."""

	def _make_dialog(self):
		"""Build a mock dialog with cancel_flag.value = 0."""
		dialog = MagicMock()
		dialog.cancel_flag.value = 0
		return dialog

	def test_message_type_updates_dialog_message(self):
		"""'message' type calls dialog.update_message with string data."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("message", "Processing file 1...", dialog)
		dialog.update_message.assert_called_once_with("Processing file 1...")

	def test_message_type_ignores_empty_string(self):
		"""'message' type with empty string does not call update_message."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("message", "", dialog)
		dialog.update_message.assert_not_called()

	def test_message_type_ignores_non_string(self):
		"""'message' type with non-string data does not call update_message."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("message", 42, dialog)
		dialog.update_message.assert_not_called()

	def test_progress_type_updates_gauge(self):
		"""'progress' type calls dialog.update_progress_bar with int data."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("progress", 75, dialog)
		dialog.update_progress_bar.assert_called_once_with(75)

	def test_progress_type_ignores_non_int(self):
		"""'progress' type with non-integer data is ignored."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("progress", "75%", dialog)
		dialog.update_progress_bar.assert_not_called()

	def test_result_type_destroys_dialog_and_shows_result(self):
		"""'result' type destroys the dialog, re-enables button, shows result."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("result", ["output.txt"], dialog)
		view.destroy_progress_dialog.assert_called_once_with(dialog)
		view.set_ocr_button_enabled.assert_called_with(True)
		view.show_result.assert_called_once_with(["output.txt"])

	def test_error_type_destroys_dialog_and_shows_error(self):
		"""'error' type destroys the dialog, re-enables button, shows error."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("error", "Something went wrong", dialog)
		view.destroy_progress_dialog.assert_called_once_with(dialog)
		view.set_ocr_button_enabled.assert_called_with(True)
		view.show_error.assert_called_once_with(
			"Something went wrong", _("OCR Error")
		)

	def test_unknown_type_does_not_crash(self):
		"""Unknown message types are silently logged without raising."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = self._make_dialog()
		p._handle_ocr_message("unknown_type", None, dialog)  # must not raise
		view.show_result.assert_not_called()
		view.show_error.assert_not_called()

	def test_completion_no_op_when_dialog_is_none(self):
		"""_handle_ocr_completion_message is a no-op when dialog is falsy."""
		view = MagicMock()
		p = make_presenter(view=view)
		p._handle_ocr_completion_message("result", "data", None)
		view.destroy_progress_dialog.assert_not_called()
		view.show_result.assert_not_called()


# ---------------------------------------------------------------------------
# OCRPresenter — process queue draining
# ---------------------------------------------------------------------------


class TestOCRPresenterProcessQueue:
	"""Tests for _process_ocr_queue."""

	def test_drains_multiple_messages(self):
		"""_process_ocr_queue drains all pending messages."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = MagicMock()
		dialog.cancel_flag.value = 0

		queue = MagicMock()
		queue.empty.side_effect = [False, False, True]
		queue.get.side_effect = [("message", "step 1"), ("progress", 50)]

		p._process_ocr_queue(queue, dialog)

		dialog.update_message.assert_called_once_with("step 1")
		dialog.update_progress_bar.assert_called_once_with(50)

	def test_empty_queue_does_nothing(self):
		"""_process_ocr_queue is a no-op on an empty queue."""
		view = MagicMock()
		p = make_presenter(view=view)
		dialog = MagicMock()
		queue = MagicMock()
		queue.empty.return_value = True

		p._process_ocr_queue(queue, dialog)

		queue.get.assert_not_called()
