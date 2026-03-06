"""Presenters for conversation profile dialogs.

Extracts business logic from EditConversationProfileDialog and
ConversationProfileDialog into wx-free presenters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError

from basilisk.config import ConversationProfile
from basilisk.presenters.presenter_mixins import ManagerCrudMixin
from basilisk.provider_engine.reasoning_config import get_effort_options

if TYPE_CHECKING:
	from basilisk.config.conversation_profile import ConversationProfileManager

log = logging.getLogger(__name__)


class EditConversationProfilePresenter:
	"""Presenter for the edit/create conversation profile dialog.

	Handles validation and construction of a ConversationProfile
	from the dialog's widget values.

	Attributes:
		view: The EditConversationProfileDialog instance.
		profile: The profile being edited, or None for a new profile.
	"""

	def __init__(self, view, profile: ConversationProfile | None = None):
		"""Initialize the presenter.

		Args:
			view: The dialog view with widget accessors.
			profile: Existing profile to edit, or None to create new.
		"""
		self.view = view
		self.profile = profile

	def validate_and_build_profile(self) -> ConversationProfile | None:
		"""Validate inputs and build a ConversationProfile.

		Reads values from the view's widgets, validates them, and
		constructs or updates the profile.

		Returns:
			The built profile, or None if validation failed.
		"""
		name = self.view.profile_name_txt.GetValue()
		if not name:
			return None

		if not self.profile:
			self.profile = ConversationProfile.model_construct()

		self.profile.name = name
		self.profile.system_prompt = self.view.system_prompt_txt.GetValue()
		self._apply_account_and_model()
		self._apply_generation_params()
		self._apply_reasoning_params()

		try:
			ConversationProfile.model_validate(self.profile)
		except ValidationError as e:
			log.error("Profile validation failed: %s", e)
			return None
		return self.profile

	def _apply_account_and_model(self) -> None:
		"""Set account and model info from view."""
		account = self.view.current_account
		model = self.view.current_model

		if self.view.include_account_checkbox.GetValue():
			self.profile.set_account(account)
		else:
			self.profile.set_account(None)

		if account and model:
			self.profile.set_model_info(account.provider.id, model.id)
		else:
			self.profile.ai_model_info = None

	def _apply_generation_params(self) -> None:
		"""Set max_tokens, temperature, top_p, stream from view."""
		model = self.view.current_model

		max_tokens = self.view.max_tokens_spin_ctrl.GetValue()
		self.profile.max_tokens = (
			max_tokens if (model and max_tokens > 0) else None
		)

		temperature = self.view.temperature_spinner.GetValue()
		self.profile.temperature = (
			temperature
			if (model and temperature != model.default_temperature)
			else None
		)

		top_p = self.view.top_p_spinner.GetValue()
		self.profile.top_p = top_p if (model and top_p != 1.0) else None
		self.profile.stream_mode = self.view.stream_mode.GetValue()

	def _apply_reasoning_params(self) -> None:
		"""Set reasoning_mode, adaptive, budget, effort from view."""
		if not hasattr(self.view, "reasoning_mode"):
			return

		self.profile.reasoning_mode = bool(self.view.reasoning_mode.GetValue())
		self.profile.reasoning_adaptive = bool(
			self.view.reasoning_adaptive.GetValue()
		)

		account = self.view.current_account
		model = self.view.current_model
		if not (model and self.profile.reasoning_mode):
			self.profile.reasoning_budget_tokens = None
			self.profile.reasoning_effort = None
			return

		val = self.view.reasoning_budget_spin.GetValue()
		self.profile.reasoning_budget_tokens = (
			val if isinstance(val, int) else None
		)

		provider_id = account.provider.id if account else ""
		model_id = model.id if model else ""
		options = get_effort_options(provider_id, model_id)
		effort_idx = self.view.reasoning_effort_choice.GetSelection()
		if isinstance(effort_idx, int) and 0 <= effort_idx < len(options):
			self.profile.reasoning_effort = options[effort_idx]
		elif options:
			self.profile.reasoning_effort = options[-1]
		else:
			self.profile.reasoning_effort = None


class ConversationProfilePresenter(ManagerCrudMixin):
	"""Presenter for the conversation profile management dialog.

	Handles CRUD operations and persistence for conversation profiles.

	Attributes:
		view: The ConversationProfileDialog instance.
		profiles: The profile manager for persistence.
		menu_update: Flag indicating the menu needs refreshing.
	"""

	def __init__(self, view, profiles: ConversationProfileManager):
		"""Initialize the presenter.

		Args:
			view: The dialog view.
			profiles: The profile manager instance.
		"""
		self.view = view
		self.profiles = profiles
		self._init_crud()

	@property
	def manager(self):
		"""Return the backing profile manager."""
		return self.profiles

	def add_profile(self, profile: ConversationProfile):
		"""Add a new profile and save.

		Args:
			profile: The profile to add.
		"""
		self.add_item(profile)

	def edit_profile(self, index: int, profile: ConversationProfile):
		"""Replace a profile at the given index and save.

		Args:
			index: The index of the profile to replace.
			profile: The new profile data.
		"""
		self.edit_item(index, profile)

	def remove_profile(self, profile: ConversationProfile):
		"""Remove a profile and save.

		Args:
			profile: The profile to remove.
		"""
		self.remove_item(profile)

	def set_default(self, profile: ConversationProfile):
		"""Set a profile as the default and save.

		Args:
			profile: The profile to set as default.
		"""
		self.profiles.set_default_profile(profile)
		self.profiles.save()
		self.menu_update = True
