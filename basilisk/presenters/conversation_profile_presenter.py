"""Presenters for conversation profile dialogs.

Extracts business logic from EditConversationProfileDialog and
ConversationProfileDialog into wx-free presenters.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from basilisk.config import ConversationProfile

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

		max_tokens = self.view.max_tokens_spin_ctrl.GetValue()
		if model and max_tokens > 0:
			self.profile.max_tokens = max_tokens
		else:
			self.profile.max_tokens = None

		temperature = self.view.temperature_spinner.GetValue()
		if model and temperature != model.default_temperature:
			self.profile.temperature = temperature
		else:
			self.profile.temperature = None

		top_p = self.view.top_p_spinner.GetValue()
		if model and top_p != 1.0:
			self.profile.top_p = top_p
		else:
			self.profile.top_p = None

		self.profile.stream_mode = self.view.stream_mode.GetValue()
		ConversationProfile.model_validate(self.profile)
		return self.profile


class ConversationProfilePresenter:
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
		self.menu_update = False

	def add_profile(self, profile: ConversationProfile):
		"""Add a new profile and save.

		Args:
			profile: The profile to add.
		"""
		self.profiles.add(profile)
		self.profiles.save()
		self.menu_update = True

	def edit_profile(self, index: int, profile: ConversationProfile):
		"""Replace a profile at the given index and save.

		Args:
			index: The index of the profile to replace.
			profile: The new profile data.
		"""
		self.profiles[index] = profile
		self.profiles.save()
		self.menu_update = True

	def remove_profile(self, profile: ConversationProfile):
		"""Remove a profile and save.

		Args:
			profile: The profile to remove.
		"""
		self.profiles.remove(profile)
		self.profiles.save()
		self.menu_update = True

	def set_default(self, profile: ConversationProfile):
		"""Set a profile as the default and save.

		Args:
			profile: The profile to set as default.
		"""
		self.profiles.set_default_profile(profile)
		self.profiles.save()
