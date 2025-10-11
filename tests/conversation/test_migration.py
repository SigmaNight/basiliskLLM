"""Tests for conversation migration functions."""

import json
import zipfile

import pytest
from upath import UPath

from basilisk.consts import BSKC_VERSION
from basilisk.conversation import Conversation
from basilisk.conversation.conversation_helper import (
	migrate_from_bskc_v0_to_v1,
	migrate_from_bskc_v1_to_v2,
	migrate_from_bskc_v2_to_v3,
)


class TestMigrationFunctions:
	"""Tests for the migration functions in conversation_helper.py."""

	def test_migrate_from_bskc_v0_to_v1(self):
		"""Test migrating from v0 to v1 format."""
		# Create v0 format data
		v0_data = {"messages": [], "systems": [], "title": "Test Conversation"}

		# Call migration function
		validation_info = {"context": None}
		v1_data = migrate_from_bskc_v0_to_v1(v0_data, validation_info)

		# Assert that version was added
		assert v1_data["version"] == 1
		assert v1_data["title"] == "Test Conversation"
		assert "messages" in v1_data
		assert "systems" in v1_data

	def test_migrate_from_bskc_v1_to_v2_with_system(self):
		"""Test migrating from v1 to v2 format with system message."""
		# Create v1 format data with system message
		v1_data = {
			"version": 1,
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {"provider_id": "test", "model_id": "model1"},
				}
			],
			"system": {"role": "system", "content": "System instructions"},
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v2_data = migrate_from_bskc_v1_to_v2(v1_data, validation_info)

		# Assert that system was moved to systems array
		assert "system" not in v2_data
		assert "systems" in v2_data
		assert len(v2_data["systems"]) == 1
		assert v2_data["systems"][0]["role"] == "system"
		assert v2_data["systems"][0]["content"] == "System instructions"

		# Check that the last message has a system_index
		assert v2_data["messages"][-1]["system_index"] == 0

	def test_migrate_from_bskc_v1_to_v2_without_system(self):
		"""Test migrating from v1 to v2 format without system message."""
		# Create v1 format data without system message
		v1_data = {
			"version": 1,
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {"provider_id": "test", "model_id": "model1"},
				}
			],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v2_data = migrate_from_bskc_v1_to_v2(v1_data, validation_info)

		# Assert that structure was preserved without systems
		assert "system" not in v2_data
		assert "systems" in v2_data
		assert len(v2_data["systems"]) == 0

		# Check that message has no system_index added
		assert "system_index" not in v2_data["messages"][0]

	def test_migrate_from_bskc_v1_to_v2_empty_messages(self):
		"""Test migrating from v1 to v2 format with empty messages."""
		# Create v1 format data with empty messages
		v1_data = {
			"version": 1,
			"messages": [],
			"system": {"role": "system", "content": "System instructions"},
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v2_data = migrate_from_bskc_v1_to_v2(v1_data, validation_info)

		# Assert that system was moved to systems array
		assert "system" not in v2_data
		assert "systems" in v2_data
		assert len(v2_data["systems"]) == 1
		assert v2_data["systems"][0]["role"] == "system"
		assert v2_data["systems"][0]["content"] == "System instructions"

		# Check that messages is still empty
		assert len(v2_data["messages"]) == 0

	def test_migrate_from_bskc_v2_to_v3_with_attachments(self):
		"""Test migrating from v2 to v3 format with attachments."""
		# Create v2 format data with attachments that need migration
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {
						"role": "user",
						"content": "Test message",
						"attachments": [
							{
								"type": "image",
								"location": "attachments/image1.png",
								"name": "image1.png",
							},
							{
								"type": "file",
								"location": "attachments/document.pdf",
								"name": "document.pdf",
							},
						],
					},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {"provider_id": "test", "model_id": "model1"},
					"system_index": 0,
				}
			],
			"systems": [{"role": "system", "content": "System instructions"}],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v3_data = migrate_from_bskc_v2_to_v3(v2_data, validation_info)

		# Assert that version was updated
		assert v3_data["version"] == 3

		# Check that attachment locations were converted to dict format
		attachments = v3_data["messages"][0]["request"]["attachments"]
		assert len(attachments) == 2

		# First attachment
		assert attachments[0]["location"]["protocol"] == "zip"
		assert attachments[0]["location"]["path"] == "attachments/image1.png"
		assert attachments[0]["location"]["storage_options"] == {}

		# Second attachment
		assert attachments[1]["location"]["protocol"] == "zip"
		assert attachments[1]["location"]["path"] == "attachments/document.pdf"
		assert attachments[1]["location"]["storage_options"] == {}

	def test_migrate_from_bskc_v2_to_v3_with_url_attachments(self):
		"""Test migrating from v2 to v3 format with URL attachments (should not be changed)."""
		# Create v2 format data with URL attachments
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {
						"role": "user",
						"content": "Test message",
						"attachments": [
							{
								"type": "url",
								"location": "https://example.com/image.png",
								"name": "image.png",
							},
							{
								"type": "file",
								"location": "zip://attachments/file.txt",
								"name": "file.txt",
							},
						],
					},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {"provider_id": "test", "model_id": "model1"},
				}
			],
			"systems": [],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v3_data = migrate_from_bskc_v2_to_v3(v2_data, validation_info)

		# Assert that version was updated
		assert v3_data["version"] == 3

		# Check that URL attachment location was NOT converted (already has ://)
		attachments = v3_data["messages"][0]["request"]["attachments"]
		assert len(attachments) == 2
		assert attachments[0]["location"] == "https://example.com/image.png"
		assert attachments[1]["location"] == "zip://attachments/file.txt"

	def test_migrate_from_bskc_v2_to_v3_without_attachments(self):
		"""Test migrating from v2 to v3 format without attachments."""
		# Create v2 format data without attachments
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {"provider_id": "test", "model_id": "model1"},
				}
			],
			"systems": [],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v3_data = migrate_from_bskc_v2_to_v3(v2_data, validation_info)

		# Assert that version was updated
		assert v3_data["version"] == 3

		# Check that structure was preserved
		assert len(v3_data["messages"]) == 1
		assert v3_data["messages"][0]["request"]["content"] == "Test message"

	def test_migrate_from_bskc_v2_to_v3_empty_messages(self):
		"""Test migrating from v2 to v3 format with empty messages."""
		# Create v2 format data with empty messages
		v2_data = {
			"version": 2,
			"messages": [],
			"systems": [],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v3_data = migrate_from_bskc_v2_to_v3(v2_data, validation_info)

		# Assert that version was updated
		assert v3_data["version"] == 3

		# Check that messages is still empty
		assert len(v3_data["messages"]) == 0

	def test_migrate_from_bskc_v2_to_v3_multiple_messages_mixed_attachments(
		self,
	):
		"""Test migrating from v2 to v3 format with multiple messages having mixed attachments."""
		# Create v2 format data with multiple messages
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {
						"role": "user",
						"content": "First message",
						"attachments": [
							{
								"type": "image",
								"location": "attachments/img1.png",
								"name": "img1.png",
							}
						],
					},
					"response": {"role": "assistant", "content": "Response 1"},
					"model": {"provider_id": "test", "model_id": "model1"},
				},
				{
					"request": {
						"role": "user",
						"content": "Second message",
						"attachments": [
							{
								"type": "url",
								"location": "https://example.com/img2.png",
								"name": "img2.png",
							}
						],
					},
					"response": {"role": "assistant", "content": "Response 2"},
					"model": {"provider_id": "test", "model_id": "model1"},
				},
				{
					"request": {"role": "user", "content": "Third message"},
					"response": {"role": "assistant", "content": "Response 3"},
					"model": {"provider_id": "test", "model_id": "model1"},
				},
			],
			"systems": [],
			"title": "Test Conversation",
		}

		# Call migration function
		validation_info = {"context": None}
		v3_data = migrate_from_bskc_v2_to_v3(v2_data, validation_info)

		# Assert that version was updated
		assert v3_data["version"] == 3

		# Check first message - should be converted
		assert len(v3_data["messages"][0]["request"]["attachments"]) == 1
		assert (
			v3_data["messages"][0]["request"]["attachments"][0]["location"][
				"protocol"
			]
			== "zip"
		)
		assert (
			v3_data["messages"][0]["request"]["attachments"][0]["location"][
				"path"
			]
			== "attachments/img1.png"
		)

		# Check second message - URL should not be converted
		assert len(v3_data["messages"][1]["request"]["attachments"]) == 1
		assert (
			v3_data["messages"][1]["request"]["attachments"][0]["location"]
			== "https://example.com/img2.png"
		)

		# Check third message - no attachments
		assert "attachments" not in v3_data["messages"][2]["request"]


class TestBSKCFileMigration:
	"""Tests for migrating BSKC files using open_bskc_file."""

	@pytest.fixture
	def bskc_path(self, tmp_path):
		"""Return a test conversation file path."""
		return f"{tmp_path}/test_migration.bskc"

	@pytest.fixture
	def storage_path(self):
		"""Return a test storage path."""
		return UPath("memory://test_migration")

	def test_open_bskc_v0_file(self, ai_model, bskc_path, storage_path):
		"""Test opening a v0 format BSKC file."""
		# Create v0 format conversation file
		v0_data = {
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {
						"provider_id": ai_model.provider_id,
						"model_id": ai_model.model_id,
					},
				}
			],
			"title": "Test V0 Conversation",
		}

		# Save as BSKC file
		with open(bskc_path, 'w+b') as f:
			with zipfile.ZipFile(
				f, mode='w', compression=zipfile.ZIP_STORED
			) as zipf:
				zipf.writestr("conversation.json", json.dumps(v0_data))

		# Open and verify migration to latest version
		conversation = Conversation.open(bskc_path, storage_path)

		# Check that it was migrated to latest version
		assert conversation.version == BSKC_VERSION
		assert conversation.title == "Test V0 Conversation"
		assert len(conversation.messages) == 1
		assert conversation.messages[0].request.content == "Test message"
		assert conversation.messages[0].response.content == "Test response"

	def test_open_bskc_v1_file(self, ai_model, bskc_path, storage_path):
		"""Test opening a v1 format BSKC file."""
		# Create v1 format conversation file
		v1_data = {
			"version": 1,
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {
						"provider_id": ai_model.provider_id,
						"model_id": ai_model.model_id,
					},
				}
			],
			"system": {"role": "system", "content": "System instructions"},
			"title": "Test V1 Conversation",
		}

		# Save as BSKC file
		with open(bskc_path, 'w+b') as f:
			with zipfile.ZipFile(
				f, mode='w', compression=zipfile.ZIP_STORED
			) as zipf:
				zipf.writestr("conversation.json", json.dumps(v1_data))

		# Open and verify migration to latest version
		conversation = Conversation.open(bskc_path, storage_path)

		# Check that it was migrated to latest version
		assert conversation.version == BSKC_VERSION
		assert conversation.title == "Test V1 Conversation"
		assert len(conversation.messages) == 1
		assert conversation.messages[0].request.content == "Test message"
		assert conversation.messages[0].response.content == "Test response"

		# Check that system was moved to systems
		assert len(conversation.systems) == 1
		assert conversation.systems[0].content == "System instructions"
		assert conversation.messages[0].system_index == 0

	def test_open_bskc_v2_file(self, ai_model, bskc_path, storage_path):
		"""Test opening a v2 format BSKC file."""
		# Create v2 format conversation file
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {"role": "user", "content": "Test message"},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {
						"provider_id": ai_model.provider_id,
						"model_id": ai_model.model_id,
					},
					"system_index": 0,
				}
			],
			"systems": [{"role": "system", "content": "System instructions"}],
			"title": "Test V2 Conversation",
		}

		# Save as BSKC file
		with open(bskc_path, 'w+b') as f:
			with zipfile.ZipFile(
				f, mode='w', compression=zipfile.ZIP_STORED
			) as zipf:
				zipf.writestr("conversation.json", json.dumps(v2_data))

		# Open and verify migration to latest version
		conversation = Conversation.open(bskc_path, storage_path)

		# Check that it was migrated to the latest version
		assert conversation.version == BSKC_VERSION
		assert conversation.title == "Test V2 Conversation"
		assert len(conversation.messages) == 1
		assert conversation.messages[0].request.content == "Test message"
		assert conversation.messages[0].response.content == "Test response"

		# Check systems array
		assert len(conversation.systems) == 1
		assert conversation.systems[0].content == "System instructions"
		assert conversation.messages[0].system_index == 0

	def test_open_bskc_v2_file_with_attachments(
		self, ai_model, bskc_path, storage_path
	):
		"""Test opening a v2 format BSKC file with attachments that need migration."""
		# Create v2 format conversation file with old-style attachment paths
		v2_data = {
			"version": 2,
			"messages": [
				{
					"request": {
						"role": "user",
						"content": "Test message",
						"attachments": [
							{
								"type": "image",
								"location": "attachments/test_image.png",
								"name": "test_image.png",
								"width": 100,
								"height": 100,
							}
						],
					},
					"response": {
						"role": "assistant",
						"content": "Test response",
					},
					"model": {
						"provider_id": ai_model.provider_id,
						"model_id": ai_model.model_id,
					},
					"system_index": 0,
				}
			],
			"systems": [{"role": "system", "content": "System instructions"}],
			"title": "Test V2 Conversation with Attachments",
		}

		# Create a simple test image for the attachment
		import io

		from PIL import Image

		# Create a simple 100x100 red image
		img = Image.new('RGB', (100, 100), color='red')
		img_bytes = io.BytesIO()
		img.save(img_bytes, format='PNG')
		img_bytes.seek(0)

		# Save as BSKC file with attachment
		with open(bskc_path, 'w+b') as f:
			with zipfile.ZipFile(
				f, mode='w', compression=zipfile.ZIP_STORED
			) as zipf:
				zipf.writestr("conversation.json", json.dumps(v2_data))
				zipf.writestr("attachments/test_image.png", img_bytes.read())

		# Open and verify migration to latest version
		conversation = Conversation.open(bskc_path, storage_path)

		# Check that it was migrated to the latest version
		assert conversation.version == BSKC_VERSION
		assert conversation.title == "Test V2 Conversation with Attachments"
		assert len(conversation.messages) == 1
		assert conversation.messages[0].request.content == "Test message"

		# Check that attachments were properly migrated
		assert len(conversation.messages[0].request.attachments) == 1
		attachment = conversation.messages[0].request.attachments[0]
		assert attachment.name == "test_image.png"
		# The location should be migrated to the storage path
		assert attachment.location.exists()

	def test_open_invalid_version_bskc_file(self, bskc_path, storage_path):
		"""Test opening a BSKC file with invalid version."""
		# Create an invalid version format conversation file
		invalid_data = {
			"version": 999,  # Invalid version
			"messages": [],
			"title": "Invalid Version",
		}

		# Save as BSKC file
		with open(bskc_path, 'w+b') as f:
			with zipfile.ZipFile(
				f, mode='w', compression=zipfile.ZIP_STORED
			) as zipf:
				zipf.writestr("conversation.json", json.dumps(invalid_data))

		# Open should raise ValueError for invalid version
		with pytest.raises(ValueError, match="Invalid conversation version"):
			Conversation.open(bskc_path, storage_path)
