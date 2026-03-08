"""Mako-based template rendering service."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from basilisk import global_vars

log = logging.getLogger(__name__)


def _render_file(template_path: Path, context: dict[str, Any]) -> str:
	"""Render a Mako template file with the given context.

	Args:
		template_path: Path to the .mako template file.
		context: Variables available in the template.

	Returns:
		The rendered string.

	Raises:
		ValueError: On any Mako syntax or runtime error.
	"""
	from mako.exceptions import MakoException
	from mako.lookup import TemplateLookup

	lookup = TemplateLookup(
		directories=[str(template_path.parent)], filesystem_checks=True
	)
	try:
		tpl = lookup.get_template(template_path.name)
		return tpl.render(**context)
	except MakoException as exc:
		raise ValueError(f"Mako template error: {exc}") from exc
	except Exception as exc:
		raise ValueError(f"Template runtime error: {exc}") from exc


def _render_inline(template_str: str, context: dict[str, Any]) -> str:
	"""Render a Mako template string with the given context.

	Args:
		template_str: The Mako template source.
		context: Variables available in the template.

	Returns:
		The rendered string.

	Raises:
		ValueError: On any Mako syntax or runtime error.
	"""
	from mako.exceptions import MakoException
	from mako.template import Template

	try:
		tpl = Template(template_str)
		return tpl.render(**context)
	except MakoException as exc:
		raise ValueError(f"Mako template error: {exc}") from exc
	except Exception as exc:
		raise ValueError(f"Template runtime error: {exc}") from exc


class TemplateService:
	"""Centralised Mako rendering service.

	All methods are static — no instance state. Presenters call these
	methods; they never import Mako directly.
	"""

	@staticmethod
	def render_prompt(template_str: str, context: dict[str, Any]) -> str:
		"""Render a system-prompt Mako template.

		Args:
			template_str: Raw template string from ConversationProfile.
			context: Variables injected into the template namespace.

		Returns:
			Rendered plain-text prompt.

		Raises:
			ValueError: On Mako syntax or runtime error.
		"""
		return _render_inline(template_str, context)

	@staticmethod
	def render_html_message(
		content: str, title: str, template_path: Path | None
	) -> str:
		"""Render the single-message HTML wrapper.

		Uses the file at *template_path* when it exists, otherwise falls
		back to the default template from the resource directory.

		Args:
			content: HTML body content (already converted from Markdown).
			title: Page/window title.
			template_path: Optional path to a custom .mako file on disk.

		Returns:
			Complete HTML document string.
		"""
		ctx = {"title": title, "content": content}
		if template_path and template_path.exists():
			try:
				return _render_file(template_path, ctx)
			except Exception as exc:
				log.warning(
					"Custom HTML template failed, using default: %s", exc
				)
		default = global_vars.templates_path / "html_message.mako"
		return _render_file(default, ctx)

	@staticmethod
	def render_conversation_export(
		conversation: Any,
		profile: Any | None,
		template_path: Path | None,
		extra_context: dict[str, Any] | None = None,
	) -> str:
		"""Render a full conversation as an HTML document.

		Args:
			conversation: The Conversation model instance.
			profile: The ConversationProfile or None.
			template_path: Optional path to a custom .mako file.
			extra_context: Additional variables merged into context
				(used in tests to inject translation stubs).

		Returns:
			Complete HTML document string.
		"""
		ctx: dict[str, Any] = {
			"conversation": conversation,
			"profile": profile,
			"_": _,
			"ngettext": ngettext,
			"pgettext": pgettext,
		}
		if extra_context:
			ctx.update(extra_context)
		if template_path and template_path.exists():
			try:
				return _render_file(template_path, ctx)
			except Exception as exc:
				log.warning(
					"Custom export template failed, using default: %s", exc
				)
		default = global_vars.templates_path / "conversation_export.mako"
		return _render_file(default, ctx)
