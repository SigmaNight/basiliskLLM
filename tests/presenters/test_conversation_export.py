"""Tests for ConversationPresenter.export_to_html."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from basilisk.conversation import Conversation
from basilisk.presenters.conversation_presenter import ConversationPresenter
from basilisk.services.conversation_service import ConversationService


@pytest.fixture
def mock_view(conversation_view_base):
	"""Return a mock view with current_profile set to None."""
	conversation_view_base.current_profile = None
	return conversation_view_base


@pytest.fixture
def presenter(mock_view):
	"""Return a ConversationPresenter with minimal mocks."""
	service = MagicMock(spec=ConversationService)
	return ConversationPresenter(
		view=mock_view,
		service=service,
		conversation=Conversation(),
		conv_storage_path="memory://test",
	)


class TestExportToHtml:
	"""Tests for ConversationPresenter.export_to_html."""

	def test_writes_html_file(self, presenter, tmp_path, mocker):
		"""export_to_html writes the rendered HTML to disk."""
		mocker.patch(
			"basilisk.services.template_service.TemplateService"
			".render_conversation_export",
			return_value="<html>test</html>",
		)
		out = tmp_path / "export.html"
		presenter.export_to_html(str(out))
		assert out.read_text(encoding="utf-8") == "<html>test</html>"

	def test_write_error_shows_error(self, presenter, mocker):
		"""OSError during write calls view.show_error."""
		mocker.patch(
			"basilisk.services.template_service.TemplateService"
			".render_conversation_export",
			return_value="<html/>",
		)
		mocker.patch("builtins.open", side_effect=OSError("disk full"))
		presenter.export_to_html("some/path.html")
		presenter.view.show_error.assert_called_once()
