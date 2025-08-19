"""Tests for conversation profile configuration and validation."""

from uuid import uuid4

from basilisk.config.conversation_profile import (
	ConversationProfile,
	ConversationProfileManager,
)


class TestConversationProfileManager:
	"""Tests for ConversationProfileManager validation and functionality."""

	def test_valid_default_profile(self):
		"""Test that a valid default profile passes validation."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = ConversationProfileManager(
			profiles=[profile], default_profile_id=profile.id
		)

		assert manager.default_profile == profile
		assert manager.default_profile_id == profile.id

	def test_no_default_profile(self):
		"""Test that no default profile is valid."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = ConversationProfileManager(
			profiles=[profile], default_profile_id=None
		)

		assert manager.default_profile is None
		assert manager.default_profile_id is None

	def test_orphaned_default_profile_id_auto_corrects(self):
		"""Test that an orphaned default_profile_id is auto-corrected (no longer fails)."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		# Create a manager with a default_profile_id that doesn't exist in profiles
		orphaned_id = uuid4()

		# This should now auto-correct instead of failing
		manager = ConversationProfileManager(
			profiles=[profile],  # profile with different ID
			default_profile_id=orphaned_id,  # orphaned ID
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None

	def test_remove_default_profile_clears_default_id(self):
		"""Test that removing the default profile clears the default_profile_id."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = ConversationProfileManager(
			profiles=[profile], default_profile_id=profile.id
		)

		# Remove the default profile
		manager.remove(profile)

		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 0


class TestOrphanedDefaultProfileScenario:
	"""Test the specific scenario that causes cx_Freeze installation failure."""

	def test_simulate_orphaned_default_profile_from_config_file(self):
		"""Simulate loading a config file with orphaned default_profile_id.

		This reproduces the exact scenario described in the issue:
		1. User creates profiles and sets one as default
		2. User deletes that profile (but config file retains orphaned default_profile_id)
		3. App tries to load config on next startup
		4. Validation now auto-corrects instead of failing
		"""
		# This simulates the corrupted state that can exist in a config file
		profile1 = ConversationProfile(
			name="Profile 1", system_prompt="Prompt 1"
		)
		profile2 = ConversationProfile(
			name="Profile 2", system_prompt="Prompt 2"
		)

		# Simulate a configuration where default_profile_id points to a deleted profile
		deleted_profile_id = uuid4()

		# This should now auto-correct instead of failing
		manager = ConversationProfileManager(
			profiles=[profile1, profile2], default_profile_id=deleted_profile_id
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 2  # Original profiles remain

	def test_empty_profiles_with_default_profile_id(self):
		"""Test edge case where profiles list is empty but default_profile_id is set."""
		orphaned_id = uuid4()

		# This should now auto-correct instead of failing
		manager = ConversationProfileManager(
			profiles=[], default_profile_id=orphaned_id
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 0

	def test_valid_default_after_correction_still_works(self):
		"""Test that after auto-correction, setting a valid default still works."""
		profile1 = ConversationProfile(
			name="Profile 1", system_prompt="Prompt 1"
		)
		profile2 = ConversationProfile(
			name="Profile 2", system_prompt="Prompt 2"
		)

		# Start with orphaned default_profile_id
		orphaned_id = uuid4()
		manager = ConversationProfileManager(
			profiles=[profile1, profile2], default_profile_id=orphaned_id
		)

		# Verify auto-correction happened
		assert manager.default_profile_id is None
		assert manager.default_profile is None

		# Set a valid default and verify it works
		manager.set_default_profile(profile1)
		assert manager.default_profile_id == profile1.id
		assert manager.default_profile == profile1
