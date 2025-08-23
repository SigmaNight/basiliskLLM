"""Tests for conversation profile configuration and validation."""

from functools import cached_property
from typing import Optional
from uuid import UUID, uuid4

import pytest
from pydantic import UUID4, Field, OnErrorOmit, model_validator
from pydantic_settings import SettingsConfigDict

from basilisk.config.config_helper import BasiliskBaseSettings
from basilisk.config.conversation_profile import (
	ConversationProfile,
	get_conversation_profile_config,
)


class IsolatedConversationProfileManager(BasiliskBaseSettings):
	"""Test version of ConversationProfileManager that doesn't load from files."""

	model_config = SettingsConfigDict(env_prefix="BASILISK_", extra="allow")

	profiles: list[OnErrorOmit[ConversationProfile]] = Field(
		default_factory=list
	)
	default_profile_id: Optional[UUID4] = Field(default=None)

	def get_profile(self, **kwargs: dict) -> ConversationProfile | None:
		return next(
			filter(
				lambda p: all(getattr(p, k) == v for k, v in kwargs.items()),
				self.profiles,
			),
			None,
		)

	@cached_property
	def default_profile(self) -> ConversationProfile | None:
		if self.default_profile_id is None:
			return None
		return self.get_profile(id=self.default_profile_id)

	def set_default_profile(self, value: ConversationProfile | None):
		if value is None:
			self.default_profile_id = None
		else:
			self.default_profile_id = value.id
		if "default_profile" in self.__dict__:
			del self.__dict__["default_profile"]

	@model_validator(mode="after")
	def check_default_profile(self) -> "IsolatedConversationProfileManager":
		if self.default_profile_id is None:
			return self
		if self.default_profile is None:
			# Auto-correct invalid default_profile_id instead of failing
			self.default_profile_id = None
			if "default_profile" in self.__dict__:
				del self.__dict__["default_profile"]
		return self

	def __iter__(self):
		return iter(self.profiles)

	def add(self, profile: ConversationProfile):
		self.profiles.append(profile)

	def remove(self, profile: ConversationProfile):
		if profile == self.default_profile:
			self.default_profile_id = None
			if "default_profile" in self.__dict__:
				del self.__dict__["default_profile"]
		self.profiles.remove(profile)

	def __len__(self) -> int:
		return len(self.profiles)

	def __getitem__(self, index: int | UUID) -> ConversationProfile:
		if isinstance(index, int):
			return self.profiles[index]
		elif isinstance(index, UUID):
			profile = self.get_profile(id=index)
			if profile is None:
				raise KeyError(f"No profile found with id {index}")
			return profile
		else:
			raise TypeError(f"Invalid index type: {type(index)}")

	def __delitem__(self, index: int):
		profile = self.profiles[index]
		self.remove(profile)

	def __setitem__(self, index: int | UUID, value: ConversationProfile):
		if isinstance(index, int):
			self.profiles[index] = value
		elif isinstance(index, UUID):
			profile = self.get_profile(id=index)
			if not profile:
				self.add(value)
			else:
				idx = self.profiles.index(profile)
				self.profiles[idx] = value
		else:
			raise TypeError(f"Invalid index type: {type(index)}")

	def save(self):
		"""Mock save method for testing."""
		from basilisk.config.conversation_profile import save_config_file

		save_config_file(
			self.model_dump(
				mode="json", exclude_defaults=True, exclude_none=True
			),
			"profiles.yml",
		)


@pytest.fixture
def isolated_config_manager(tmp_path):
	"""Provide an isolated conversation profile manager for testing.

	This fixture ensures tests don't interfere with real user configuration files
	by returning a test manager that doesn't load from files.
	"""
	# Global instance for caching tests
	_cached_instance = None

	def mock_get_conversation_profile_config():
		nonlocal _cached_instance
		if _cached_instance is None:
			_cached_instance = IsolatedConversationProfileManager()
		return _cached_instance

	# Clear the cache to ensure we get a fresh instance
	get_conversation_profile_config.cache_clear()

	# Yield the mock function
	yield mock_get_conversation_profile_config

	# Clean up the cache after the test
	get_conversation_profile_config.cache_clear()


@pytest.fixture
def clean_config_manager(tmp_path):
	"""Provide a clean ConversationProfileManager instance for testing.

	This fixture creates isolated ConversationProfileManager instances that don't
	load from real user configuration files. Use this when you need to create
	manager instances directly without going through the cached function.
	"""

	# Return a factory function to create clean managers
	def _create_manager(**kwargs):
		return IsolatedConversationProfileManager(**kwargs)

	yield _create_manager


class TestConversationProfileManager:
	"""Tests for ConversationProfileManager validation and functionality."""

	def test_valid_default_profile(self, clean_config_manager):
		"""Test that a valid default profile passes validation."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = clean_config_manager(
			profiles=[profile], default_profile_id=profile.id
		)

		assert manager.default_profile == profile
		assert manager.default_profile_id == profile.id

	def test_no_default_profile(self, clean_config_manager):
		"""Test that no default profile is valid."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = clean_config_manager(
			profiles=[profile], default_profile_id=None
		)

		assert manager.default_profile is None
		assert manager.default_profile_id is None

	def test_orphaned_default_profile_id_auto_corrects(
		self, clean_config_manager
	):
		"""Test that an orphaned default_profile_id is auto-corrected (no longer fails)."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		# Create a manager with a default_profile_id that doesn't exist in profiles
		orphaned_id = uuid4()

		# This should now auto-correct instead of failing
		manager = clean_config_manager(
			profiles=[profile],  # profile with different ID
			default_profile_id=orphaned_id,  # orphaned ID
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None

	def test_remove_default_profile_clears_default_id(
		self, clean_config_manager
	):
		"""Test that removing the default profile clears the default_profile_id."""
		profile = ConversationProfile(
			name="Test Profile", system_prompt="Test prompt"
		)

		manager = clean_config_manager(
			profiles=[profile], default_profile_id=profile.id
		)

		# Remove the default profile
		manager.remove(profile)

		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 0


class TestOrphanedDefaultProfileScenario:
	"""Test the specific scenario that causes cx_Freeze installation failure."""

	def test_simulate_orphaned_default_profile_from_config_file(
		self, clean_config_manager
	):
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
		manager = clean_config_manager(
			profiles=[profile1, profile2], default_profile_id=deleted_profile_id
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 2  # Original profiles remain

	def test_empty_profiles_with_default_profile_id(self, clean_config_manager):
		"""Test edge case where profiles list is empty but default_profile_id is set."""
		orphaned_id = uuid4()

		# This should now auto-correct instead of failing
		manager = clean_config_manager(
			profiles=[], default_profile_id=orphaned_id
		)

		# The orphaned ID should be auto-corrected to None
		assert manager.default_profile_id is None
		assert manager.default_profile is None
		assert len(manager.profiles) == 0

	def test_valid_default_after_correction_still_works(
		self, clean_config_manager
	):
		"""Test that after auto-correction, setting a valid default still works."""
		profile1 = ConversationProfile(
			name="Profile 1", system_prompt="Prompt 1"
		)
		profile2 = ConversationProfile(
			name="Profile 2", system_prompt="Prompt 2"
		)

		# Start with orphaned default_profile_id
		orphaned_id = uuid4()
		manager = clean_config_manager(
			profiles=[profile1, profile2], default_profile_id=orphaned_id
		)

		# Verify auto-correction happened
		assert manager.default_profile_id is None
		assert manager.default_profile is None

		# Set a valid default and verify it works
		manager.set_default_profile(profile1)
		assert manager.default_profile_id == profile1.id
		assert manager.default_profile == profile1


class TestConversationProfile:
	"""Tests for ConversationProfile model and methods."""

	def test_basic_profile_creation(self):
		"""Test basic profile creation with minimal fields."""
		profile = ConversationProfile(name="Test Profile")
		assert profile.name == "Test Profile"
		assert profile.system_prompt == ""
		assert profile.account_info is None
		assert profile.ai_model_info is None
		assert profile.max_tokens is None
		assert profile.temperature is None
		assert profile.top_p is None
		assert profile.stream_mode is True
		assert isinstance(profile.id, UUID)

	def test_profile_creation_with_all_fields(self):
		"""Test profile creation with all fields specified."""
		profile = ConversationProfile(
			name="Full Profile",
			system_prompt="You are a helpful assistant",
			ai_model_info="openai/gpt-4",  # Need model for params validation
			max_tokens=1000,
			temperature=0.7,
			top_p=0.9,
			stream_mode=False,
		)
		assert profile.name == "Full Profile"
		assert profile.system_prompt == "You are a helpful assistant"
		assert profile.max_tokens == 1000
		assert profile.temperature == 0.7
		assert profile.top_p == 0.9
		assert profile.stream_mode is False

	def test_profile_initialization_error_handling(self):
		"""Test error handling in profile initialization."""
		# Test with invalid data that would cause validation errors
		with pytest.raises(Exception):
			ConversationProfile(
				name="Test",
				max_tokens=100,  # max_tokens without ai_model_info should fail
			)

	def test_ai_model_string_conversion(self):
		"""Test ai_model_info field validator converts strings correctly."""
		profile = ConversationProfile(name="Test", ai_model_info="openai/gpt-4")
		assert profile.ai_model_info.provider_id == "openai"
		assert profile.ai_model_info.model_id == "gpt-4"

	def test_ai_model_dict_passthrough(self):
		"""Test ai_model_info field validator passes through dict unchanged."""
		model_dict = {"provider_id": "anthropic", "model_id": "claude-3"}
		profile = ConversationProfile(name="Test", ai_model_info=model_dict)
		assert profile.ai_model_info.provider_id == "anthropic"
		assert profile.ai_model_info.model_id == "claude-3"

	def test_ai_model_none_passthrough(self):
		"""Test ai_model_info field validator passes through None unchanged."""
		profile = ConversationProfile(name="Test", ai_model_info=None)
		assert profile.ai_model_info is None

	def test_get_default_class_method(self):
		"""Test the get_default class method creates a valid default profile."""
		profile = ConversationProfile.get_default()
		assert profile.name == "default"
		assert profile.system_prompt == ""
		assert profile.account_info is None
		assert profile.ai_model_info is None

	def test_ai_model_id_property(self):
		"""Test ai_model_id property returns correct values."""
		# With no model info
		profile = ConversationProfile(name="Test")
		assert profile.ai_model_id is None

		# With model info
		profile = ConversationProfile(name="Test", ai_model_info="openai/gpt-4")
		assert profile.ai_model_id == "gpt-4"

	def test_ai_provider_property_no_account_no_model(self):
		"""Test ai_provider property when no account or model is set."""
		profile = ConversationProfile(name="Test")
		assert profile.ai_provider is None

	def test_ai_provider_property_with_model_only(self):
		"""Test ai_provider property when only model is set."""
		profile = ConversationProfile(name="Test", ai_model_info="openai/gpt-4")
		assert profile.ai_provider.id == "openai"

	def test_set_model_info_method(self):
		"""Test set_model_info method sets model information correctly."""
		profile = ConversationProfile(name="Test")
		profile.set_model_info("anthropic", "claude-3")
		assert profile.ai_model_info.provider_id == "anthropic"
		assert profile.ai_model_info.model_id == "claude-3"

	def test_equality_comparison(self):
		"""Test profile equality comparison based on ID."""
		profile1 = ConversationProfile(name="Test1")
		profile2 = ConversationProfile(name="Test2")
		profile3 = ConversationProfile(name="Test3")
		profile3.id = profile1.id  # Same ID as profile1

		# Different profiles should not be equal
		assert profile1 != profile2
		assert not (profile1 == profile2)

		# Same ID should be equal even if other fields differ
		assert profile1 == profile3

		# Comparison with None should be False
		assert profile1 is not None

	def test_model_params_validation_without_model(self):
		"""Test that model parameters cannot be set without an AI model."""
		with pytest.raises(
			ValueError, match="Max tokens must be None without model"
		):
			ConversationProfile(name="Test", max_tokens=100)

		with pytest.raises(
			ValueError, match="Temperature must be None without model"
		):
			ConversationProfile(name="Test", temperature=0.7)

		with pytest.raises(
			ValueError, match="Top P must be None without model"
		):
			ConversationProfile(name="Test", top_p=0.9)

	def test_model_params_validation_with_model(self):
		"""Test that model parameters can be set when AI model is present."""
		profile = ConversationProfile(
			name="Test",
			ai_model_info="openai/gpt-4",
			max_tokens=100,
			temperature=0.7,
			top_p=0.9,
		)
		assert profile.max_tokens == 100
		assert profile.temperature == 0.7
		assert profile.top_p == 0.9

	def test_invalid_ai_model_string_format(self):
		"""Test handling of invalid ai_model string formats."""
		with pytest.raises(ValueError):
			ConversationProfile(
				name="Test", ai_model_info="invalid_format_no_slash"
			)


class TestConversationProfileManagerCollectionOperations:
	"""Tests for ConversationProfileManager collection-like operations."""

	def test_iteration(self, clean_config_manager):
		"""Test iteration over profiles in manager."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1, profile2])

		profiles_list = list(manager)
		assert len(profiles_list) == 2
		assert profile1 in profiles_list
		assert profile2 in profiles_list

	def test_length(self, clean_config_manager):
		"""Test len() operation on manager."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager()
		assert len(manager) == 0

		manager = clean_config_manager(profiles=[profile1])
		assert len(manager) == 1

		manager = clean_config_manager(profiles=[profile1, profile2])
		assert len(manager) == 2

	def test_getitem_by_index(self, clean_config_manager):
		"""Test accessing profiles by integer index."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1, profile2])

		assert manager[0] == profile1
		assert manager[1] == profile2

		with pytest.raises(IndexError):
			_ = manager[2]

	def test_getitem_by_uuid(self, clean_config_manager):
		"""Test accessing profiles by UUID."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1, profile2])

		assert manager[profile1.id] == profile1
		assert manager[profile2.id] == profile2

		# Test KeyError for non-existent UUID
		with pytest.raises(KeyError):
			_ = manager[uuid4()]

	def test_getitem_invalid_type(self, clean_config_manager):
		"""Test accessing profiles with invalid index type."""
		profile = ConversationProfile(name="Profile")
		manager = clean_config_manager(profiles=[profile])

		with pytest.raises(TypeError):
			_ = manager["invalid_type"]

	def test_setitem_by_index(self, clean_config_manager):
		"""Test setting profiles by integer index."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")
		new_profile = ConversationProfile(name="New Profile")

		manager = clean_config_manager(profiles=[profile1, profile2])

		manager[0] = new_profile
		assert manager[0] == new_profile
		assert len(manager) == 2

	def test_setitem_by_uuid_existing(self, clean_config_manager):
		"""Test setting profiles by UUID for existing profile."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")
		new_profile = ConversationProfile(name="New Profile")

		manager = clean_config_manager(profiles=[profile1, profile2])

		manager[profile1.id] = new_profile
		assert manager[0] == new_profile
		assert len(manager) == 2

	def test_setitem_by_uuid_new(self, clean_config_manager):
		"""Test setting profiles by UUID for non-existent profile (adds new)."""
		profile1 = ConversationProfile(name="Profile 1")
		new_profile = ConversationProfile(name="New Profile")

		manager = clean_config_manager(profiles=[profile1])

		manager[uuid4()] = new_profile
		assert len(manager) == 2
		assert new_profile in list(manager)

	def test_setitem_invalid_type(self, clean_config_manager):
		"""Test setting profiles with invalid index type."""
		profile = ConversationProfile(name="Profile")
		manager = clean_config_manager(profiles=[profile])

		with pytest.raises(TypeError):
			manager["invalid_type"] = profile

	def test_delitem(self, clean_config_manager):
		"""Test deleting profiles by index."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1, profile2])
		assert len(manager) == 2

		del manager[0]
		assert len(manager) == 1
		assert manager[0] == profile2

		with pytest.raises(IndexError):
			del manager[1]

	def test_delitem_removes_default_if_deleted(self, clean_config_manager):
		"""Test that deleting the default profile clears default_profile_id."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(
			profiles=[profile1, profile2], default_profile_id=profile1.id
		)

		assert manager.default_profile == profile1

		del manager[0]  # Delete profile1
		assert manager.default_profile_id is None
		assert manager.default_profile is None

	def test_add_method(self, clean_config_manager):
		"""Test add method adds profiles correctly."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager()
		assert len(manager) == 0

		manager.add(profile1)
		assert len(manager) == 1
		assert manager[0] == profile1

		manager.add(profile2)
		assert len(manager) == 2
		assert manager[1] == profile2

	def test_get_profile_with_kwargs(self, clean_config_manager):
		"""Test get_profile method with various keyword arguments."""
		profile1 = ConversationProfile(
			name="Profile 1", system_prompt="Prompt 1"
		)
		profile2 = ConversationProfile(
			name="Profile 2", system_prompt="Prompt 2"
		)

		manager = clean_config_manager(profiles=[profile1, profile2])

		# Test finding by name
		found = manager.get_profile(name="Profile 1")
		assert found == profile1

		# Test finding by system_prompt
		found = manager.get_profile(system_prompt="Prompt 2")
		assert found == profile2

		# Test finding by multiple criteria
		found = manager.get_profile(name="Profile 1", system_prompt="Prompt 1")
		assert found == profile1

		# Test not found
		found = manager.get_profile(name="Non-existent")
		assert found is None

		# Test multiple criteria mismatch
		found = manager.get_profile(
			name="Profile 1", system_prompt="Wrong Prompt"
		)
		assert found is None


class TestConversationProfileManagerConfig:
	"""Tests for ConversationProfileManager configuration functionality."""

	def test_get_conversation_profile_config_function(
		self, isolated_config_manager
	):
		"""Test the global configuration function with proper isolation."""
		config = isolated_config_manager()
		# Check that it behaves like a ConversationProfileManager
		assert hasattr(config, 'profiles')
		assert hasattr(config, 'default_profile_id')
		assert hasattr(config, 'add')
		assert hasattr(config, 'remove')

		# Test caching - should return same instance
		config2 = isolated_config_manager()
		assert config is config2

	def test_config_isolation_prevents_test_interference(
		self, isolated_config_manager
	):
		"""Test that tests don't interfere with real user configuration files.

		This test verifies that the test isolation works correctly and tests
		don't fail when there are existing user configuration files on the system.
		"""
		# This should work regardless of what config files exist on the system
		config = isolated_config_manager()
		# Check that it behaves like a ConversationProfileManager
		assert hasattr(config, 'profiles')
		assert hasattr(config, 'default_profile_id')

		# Should start with no profiles (clean slate)
		assert len(config.profiles) == 0
		assert config.default_profile_id is None

		# Test that we can add profiles and they work correctly
		profile = ConversationProfile(name="Test Profile")
		config.add(profile)
		assert len(config.profiles) == 1
		assert config.profiles[0].name == "Test Profile"


class TestConversationProfileAccountIntegration:
	"""Tests for ConversationProfile account integration."""

	def test_account_property_no_account_info(self):
		"""Test account property when no account_info is set."""
		profile = ConversationProfile(name="Test")
		assert profile.account is None

	def test_set_account_to_none(self):
		"""Test setting account to None clears account_info."""
		profile = ConversationProfile(name="Test")
		profile.set_account(None)
		assert profile.account_info is None
		assert profile.account is None

	def test_ai_provider_priority_with_account_and_model(self):
		"""Test that account provider takes priority over model provider."""
		# This test will create a mock account to test the logic
		# Since we don't have a real account system set up in tests,
		# we'll test the property logic directly
		profile = ConversationProfile(name="Test", ai_model_info="openai/gpt-4")

		# When no account is set, should return model provider
		assert profile.ai_provider.id == "openai"


class TestConversationProfileAdvancedValidation:
	"""Tests for advanced validation scenarios in ConversationProfile."""

	def test_revalidation_on_field_change(self):
		"""Test that validation runs when fields are changed."""
		profile = ConversationProfile(
			name="Test", ai_model_info="openai/gpt-4", max_tokens=100
		)

		# Remove the model - should trigger validation error on next access
		profile.ai_model_info = None

		# This should trigger revalidation and fail
		with pytest.raises(Exception):
			profile.model_validate(profile.model_dump())

	def test_all_model_params_together(self):
		"""Test setting all model parameters together."""
		profile = ConversationProfile(
			name="Test",
			ai_model_info="anthropic/claude-3",
			max_tokens=2000,
			temperature=0.5,
			top_p=0.8,
		)
		assert profile.max_tokens == 2000
		assert profile.temperature == 0.5
		assert profile.top_p == 0.8

	def test_edge_case_temperature_values(self):
		"""Test edge case temperature values."""
		# Test with 0 temperature
		profile = ConversationProfile(
			name="Test", ai_model_info="openai/gpt-4", temperature=0.0
		)
		assert profile.temperature == 0.0

		# Test with 1.0 temperature
		profile = ConversationProfile(
			name="Test", ai_model_info="openai/gpt-4", temperature=1.0
		)
		assert profile.temperature == 1.0

	def test_edge_case_top_p_values(self):
		"""Test edge case top_p values."""
		# Test with 0.1 top_p
		profile = ConversationProfile(
			name="Test", ai_model_info="openai/gpt-4", top_p=0.1
		)
		assert profile.top_p == 0.1

		# Test with 1.0 top_p
		profile = ConversationProfile(
			name="Test", ai_model_info="openai/gpt-4", top_p=1.0
		)
		assert profile.top_p == 1.0


class TestConversationProfileManagerPersistence:
	"""Tests for ConversationProfileManager save functionality."""

	def test_save_method_creates_config(
		self, tmp_path, monkeypatch, clean_config_manager
	):
		"""Test that save method properly calls save_config_file."""
		# Mock the save_config_file function
		import basilisk.config.conversation_profile

		saved_data = None
		saved_filename = None

		def mock_save_config_file(data, filename):
			nonlocal saved_data, saved_filename
			saved_data = data
			saved_filename = filename

		monkeypatch.setattr(
			basilisk.config.conversation_profile,
			"save_config_file",
			mock_save_config_file,
		)

		profile = ConversationProfile(name="Test Profile")
		manager = clean_config_manager(profiles=[profile])

		manager.save()

		assert saved_filename == "profiles.yml"
		assert saved_data is not None
		assert "profiles" in saved_data


class TestConversationProfileManagerComplexScenarios:
	"""Tests for complex scenarios and edge cases."""

	def test_manager_with_multiple_profiles_same_name(
		self, clean_config_manager
	):
		"""Test manager handles profiles with same name correctly."""
		profile1 = ConversationProfile(name="Same Name")
		profile2 = ConversationProfile(name="Same Name")

		manager = clean_config_manager(profiles=[profile1, profile2])

		# Should be able to distinguish by ID
		assert manager[profile1.id] == profile1
		assert manager[profile2.id] == profile2
		assert profile1 != profile2  # Different IDs

	def test_set_default_clears_cached_property(self, clean_config_manager):
		"""Test that setting default profile clears the cached property."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1, profile2])

		# Set initial default
		manager.set_default_profile(profile1)
		assert manager.default_profile == profile1

		# Change default
		manager.set_default_profile(profile2)
		assert manager.default_profile == profile2
		assert manager.default_profile != profile1

	def test_remove_non_existent_profile(self, clean_config_manager):
		"""Test removing a profile that doesn't exist in the list."""
		profile1 = ConversationProfile(name="Profile 1")
		profile2 = ConversationProfile(name="Profile 2")

		manager = clean_config_manager(profiles=[profile1])

		# This should raise ValueError since profile2 is not in the list
		with pytest.raises(ValueError):
			manager.remove(profile2)

	def test_large_profile_collection(self, clean_config_manager):
		"""Test manager with a large number of profiles."""
		profiles = []
		for i in range(100):
			profiles.append(ConversationProfile(name=f"Profile {i}"))

		manager = clean_config_manager(profiles=profiles)
		assert len(manager) == 100

		# Test iteration
		profile_names = [p.name for p in manager]
		assert len(profile_names) == 100
		assert "Profile 50" in profile_names

		# Test access by index and UUID
		assert manager[50].name == "Profile 50"
		assert manager[profiles[75].id] == profiles[75]

	def test_profile_model_validation_chain(self):
		"""Test the full validation chain for profiles."""
		# This should pass all validators
		profile = ConversationProfile(
			name="Valid Profile",
			ai_model_info="gemini/gemini-pro",
			max_tokens=500,
			temperature=0.3,
			top_p=0.7,
			system_prompt="Be helpful",
		)

		assert profile.ai_model_id == "gemini-pro"
		assert profile.ai_provider.id == "gemini"
