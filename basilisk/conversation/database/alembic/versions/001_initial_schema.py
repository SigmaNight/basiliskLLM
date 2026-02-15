"""Initial schema for conversation database.

Revision ID: 001
Revises:
Create Date: 2026-02-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Create all tables for conversation persistence."""
	# conversations
	op.create_table(
		"conversations",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("title", sa.String(), nullable=True),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.Column("updated_at", sa.DateTime(), nullable=False),
	)
	op.create_index(
		"ix_conversations_updated",
		"conversations",
		[sa.text("updated_at DESC")],
	)

	# system_prompts
	op.create_table(
		"system_prompts",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("content_hash", sa.String(), nullable=False, unique=True),
		sa.Column("content", sa.String(), nullable=False),
	)

	# conversation_system_prompts
	op.create_table(
		"conversation_system_prompts",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("conversation_id", sa.Integer(), nullable=False),
		sa.Column("system_prompt_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.Integer(), nullable=False),
		sa.ForeignKeyConstraint(
			["conversation_id"], ["conversations.id"], ondelete="CASCADE"
		),
		sa.ForeignKeyConstraint(["system_prompt_id"], ["system_prompts.id"]),
		sa.UniqueConstraint("conversation_id", "position"),
	)
	op.create_index(
		"ix_conv_sys_prompts_conv",
		"conversation_system_prompts",
		["conversation_id"],
	)

	# message_blocks
	op.create_table(
		"message_blocks",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("conversation_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.Integer(), nullable=False),
		sa.Column("conversation_system_prompt_id", sa.Integer(), nullable=True),
		sa.Column("model_provider", sa.String(), nullable=False),
		sa.Column("model_id", sa.String(), nullable=False),
		sa.Column(
			"temperature", sa.Float(), nullable=False, server_default="1.0"
		),
		sa.Column(
			"max_tokens", sa.Integer(), nullable=False, server_default="4096"
		),
		sa.Column("top_p", sa.Float(), nullable=False, server_default="1.0"),
		sa.Column("stream", sa.Boolean(), nullable=False, server_default="0"),
		sa.Column("created_at", sa.DateTime(), nullable=False),
		sa.Column("updated_at", sa.DateTime(), nullable=False),
		sa.ForeignKeyConstraint(
			["conversation_id"], ["conversations.id"], ondelete="CASCADE"
		),
		sa.ForeignKeyConstraint(
			["conversation_system_prompt_id"],
			["conversation_system_prompts.id"],
		),
		sa.UniqueConstraint("conversation_id", "position"),
	)
	op.create_index(
		"ix_message_blocks_conversation",
		"message_blocks",
		["conversation_id", "position"],
	)

	# messages
	op.create_table(
		"messages",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("message_block_id", sa.Integer(), nullable=False),
		sa.Column("role", sa.String(), nullable=False),
		sa.Column("content", sa.String(), nullable=False),
		sa.ForeignKeyConstraint(
			["message_block_id"], ["message_blocks.id"], ondelete="CASCADE"
		),
		sa.UniqueConstraint("message_block_id", "role"),
	)
	op.create_index("ix_messages_block", "messages", ["message_block_id"])
	op.create_index("ix_messages_content", "messages", ["content"])

	# attachments
	op.create_table(
		"attachments",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("content_hash", sa.String(), nullable=False, unique=True),
		sa.Column("name", sa.String(), nullable=True),
		sa.Column("mime_type", sa.String(), nullable=True),
		sa.Column("size", sa.Integer(), nullable=True),
		sa.Column("location_type", sa.String(), nullable=False),
		sa.Column("url", sa.String(), nullable=True),
		sa.Column("blob_data", sa.LargeBinary(), nullable=True),
		sa.Column("is_image", sa.Boolean(), nullable=False, server_default="0"),
		sa.Column("image_width", sa.Integer(), nullable=True),
		sa.Column("image_height", sa.Integer(), nullable=True),
	)
	op.create_index("ix_attachments_hash", "attachments", ["content_hash"])

	# message_attachments
	op.create_table(
		"message_attachments",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("message_id", sa.Integer(), nullable=False),
		sa.Column("attachment_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.Integer(), nullable=False),
		sa.Column("description", sa.String(), nullable=True),
		sa.ForeignKeyConstraint(
			["message_id"], ["messages.id"], ondelete="CASCADE"
		),
		sa.ForeignKeyConstraint(["attachment_id"], ["attachments.id"]),
		sa.UniqueConstraint("message_id", "position"),
	)

	# citations
	op.create_table(
		"citations",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("message_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.Integer(), nullable=False),
		sa.Column("cited_text", sa.String(), nullable=True),
		sa.Column("source_title", sa.String(), nullable=True),
		sa.Column("source_url", sa.String(), nullable=True),
		sa.Column("start_index", sa.Integer(), nullable=True),
		sa.Column("end_index", sa.Integer(), nullable=True),
		sa.ForeignKeyConstraint(
			["message_id"], ["messages.id"], ondelete="CASCADE"
		),
	)


def downgrade() -> None:
	"""Drop all conversation tables."""
	op.drop_table("citations")
	op.drop_table("message_attachments")
	op.drop_table("attachments")
	op.drop_table("messages")
	op.drop_table("message_blocks")
	op.drop_table("conversation_system_prompts")
	op.drop_table("system_prompts")
	op.drop_table("conversations")
