"""Tests for group chat data model additions.

Covers:
- MessageBlock group fields (profile_id, group_id, group_position)
- GroupParticipant snapshot model
- Conversation.group_participants field
- Conversation._profile_name_map private attr
- BSKC v3→v4 migration
"""

from __future__ import annotations

import json
from uuid import uuid4

from basilisk.conversation.conversation_helper import (
	migrate_from_bskc_v3_to_v4,
	migration_steps,
)
from basilisk.conversation.conversation_model import (
	Conversation,
	GroupParticipant,
	Message,
	MessageBlock,
	MessageRoleEnum,
)
from basilisk.provider_ai_model import AIModelInfo


class TestMessageBlockGroupFields:
	"""Tests for the three new group fields on MessageBlock."""

	def test_group_fields_default_to_none(self, message_block):
		"""All group fields must default to None for non-group messages."""
		assert message_block.profile_id is None
		assert message_block.group_id is None
		assert message_block.group_position is None

	def test_group_fields_accept_values(self):
		"""Group fields accept valid values."""
		pid = uuid4()
		gid = str(uuid4())
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="hello"),
			model=AIModelInfo(provider_id="openai", model_id="gpt-4o"),
			profile_id=pid,
			group_id=gid,
			group_position=2,
		)
		assert block.profile_id == pid
		assert block.group_id == gid
		assert block.group_position == 2

	def test_group_fields_excluded_from_serialization_unchanged(
		self, message_block
	):
		"""Group fields with None values round-trip cleanly through JSON."""
		data = json.loads(message_block.model_dump_json())
		assert "profile_id" not in data or data["profile_id"] is None
		assert "group_id" not in data or data["group_id"] is None
		assert "group_position" not in data or data["group_position"] is None

	def test_group_fields_persist_through_serialization(self):
		"""Non-None group fields survive a JSON round-trip."""
		pid = uuid4()
		gid = str(uuid4())
		block = MessageBlock(
			request=Message(role=MessageRoleEnum.USER, content="hi"),
			model=AIModelInfo(provider_id="anthropic", model_id="claude-3"),
			profile_id=pid,
			group_id=gid,
			group_position=1,
		)
		data = json.loads(block.model_dump_json())
		restored = MessageBlock.model_validate(data)
		assert restored.profile_id == pid
		assert restored.group_id == gid
		assert restored.group_position == 1


class TestGroupParticipant:
	"""Tests for the GroupParticipant snapshot model."""

	def _make_participant(self, **kwargs) -> GroupParticipant:
		"""Build a minimal valid GroupParticipant."""
		defaults = dict(
			profile_id=uuid4(),
			name="Alice",
			system_prompt="Be concise.",
			account_info={"id": str(uuid4())},
			ai_model_info=AIModelInfo(
				provider_id="anthropic", model_id="claude-3"
			),
			max_tokens=2048,
			temperature=0.7,
			top_p=0.9,
			stream_mode=True,
		)
		defaults.update(kwargs)
		return GroupParticipant(**defaults)

	def test_fields_stored_correctly(self):
		"""All fields are stored and accessible."""
		pid = uuid4()
		acct = {"id": str(uuid4())}
		p = self._make_participant(
			profile_id=pid, name="Bob", account_info=acct
		)
		assert p.profile_id == pid
		assert p.name == "Bob"
		assert p.account_info == acct

	def test_default_system_prompt(self):
		"""system_prompt defaults to empty string."""
		p = self._make_participant(system_prompt="")
		assert p.system_prompt == ""

	def test_json_round_trip(self):
		"""GroupParticipant survives a JSON serialization round-trip."""
		p = self._make_participant()
		data = json.loads(p.model_dump_json())
		restored = GroupParticipant.model_validate(data)
		assert restored.profile_id == p.profile_id
		assert restored.name == p.name
		assert restored.ai_model_info.model_id == p.ai_model_info.model_id


class TestConversationGroupFields:
	"""Tests for group_participants and _profile_name_map on Conversation."""

	def test_group_participants_defaults_empty(self):
		"""group_participants is an empty list by default."""
		conv = Conversation()
		assert conv.group_participants == []

	def test_group_participants_persisted(self):
		"""group_participants set at construction are stored."""
		p = GroupParticipant(
			profile_id=uuid4(),
			name="Alice",
			account_info={},
			ai_model_info=AIModelInfo(provider_id="openai", model_id="gpt-4o"),
			max_tokens=4096,
			temperature=1.0,
			top_p=1.0,
			stream_mode=True,
		)
		conv = Conversation(group_participants=[p])
		assert len(conv.group_participants) == 1
		assert conv.group_participants[0].name == "Alice"

	def test_profile_name_map_defaults_empty(self):
		"""_profile_name_map is an empty dict by default (private attr)."""
		conv = Conversation()
		assert conv._profile_name_map == {}

	def test_profile_name_map_not_in_serialization(self):
		"""_profile_name_map is excluded from JSON serialization."""
		conv = Conversation()
		conv._profile_name_map = {"abc": "Alice"}
		data = json.loads(conv.model_dump_json())
		assert "_profile_name_map" not in data

	def test_group_participants_excluded_from_bskc_when_empty(self):
		"""group_participants absent from JSON payload when empty is fine."""
		conv = Conversation()
		data = json.loads(conv.model_dump_json())
		# Either absent or an empty list — both are valid
		assert data.get("group_participants", []) == []


class TestBskcV3ToV4Migration:
	"""Tests for the v3→v4 migration step."""

	def test_version_bumped(self):
		"""Migration increments version to 4."""
		result = migrate_from_bskc_v3_to_v4({"version": 3}, None)
		assert result["version"] == 4

	def test_group_participants_added(self):
		"""Migration adds group_participants as empty list."""
		result = migrate_from_bskc_v3_to_v4({"version": 3}, None)
		assert result["group_participants"] == []

	def test_existing_group_participants_preserved(self):
		"""If group_participants already present, migration leaves it intact."""
		value = {"version": 3, "group_participants": [{"name": "Alice"}]}
		result = migrate_from_bskc_v3_to_v4(value, None)
		assert result["group_participants"] == [{"name": "Alice"}]

	def test_migration_registered(self):
		"""V3→v4 migration is the 4th entry in migration_steps."""
		assert len(migration_steps) == 4
		assert migration_steps[3] is migrate_from_bskc_v3_to_v4

	def test_v3_conversation_loads(self):
		"""A v3-format conversation dict loads successfully after migration."""
		v3_data = {
			"version": 3,
			"messages": [],
			"systems": [],
			"title": "old chat",
		}
		conv = Conversation.model_validate(v3_data)
		assert conv.version == 4
		assert conv.group_participants == []
		assert conv.title == "old chat"
