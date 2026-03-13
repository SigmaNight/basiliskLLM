"""Add group chat support to conversation database.

Revision ID: 002
Revises: 001
Create Date: 2026-03-13

Adds:
- ``conversations.is_group_chat`` column
- ``message_blocks.profile_id``, ``group_id``, ``group_position`` columns
- ``conversation_participants`` table (participant snapshots)
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add group chat columns and the conversation_participants table."""
	# Add is_group_chat flag to conversations
	with op.batch_alter_table("conversations") as batch_op:
		batch_op.add_column(
			sa.Column(
				"is_group_chat",
				sa.Boolean(),
				nullable=False,
				server_default="0",
			)
		)

	# Add group-block fields to message_blocks
	with op.batch_alter_table("message_blocks") as batch_op:
		batch_op.add_column(sa.Column("profile_id", sa.String(), nullable=True))
		batch_op.add_column(sa.Column("group_id", sa.String(), nullable=True))
		batch_op.add_column(
			sa.Column("group_position", sa.Integer(), nullable=True)
		)

	# New table for participant snapshots
	op.create_table(
		"conversation_participants",
		sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
		sa.Column("conversation_id", sa.Integer(), nullable=False),
		sa.Column("position", sa.Integer(), nullable=False),
		sa.Column("profile_id", sa.String(), nullable=False),
		sa.Column("name", sa.String(), nullable=False),
		sa.Column("account_info_json", sa.String(), nullable=False),
		sa.Column("provider_id", sa.String(), nullable=False),
		sa.Column("model_id", sa.String(), nullable=False),
		sa.Column(
			"max_tokens", sa.Integer(), nullable=False, server_default="4096"
		),
		sa.Column(
			"temperature", sa.Float(), nullable=False, server_default="1.0"
		),
		sa.Column("top_p", sa.Float(), nullable=False, server_default="1.0"),
		sa.Column(
			"stream_mode", sa.Boolean(), nullable=False, server_default="1"
		),
		sa.Column(
			"system_prompt", sa.String(), nullable=False, server_default=""
		),
		sa.ForeignKeyConstraint(
			["conversation_id"], ["conversations.id"], ondelete="CASCADE"
		),
		sa.UniqueConstraint("conversation_id", "position"),
	)
	op.create_index(
		"ix_conv_participants_conv",
		"conversation_participants",
		["conversation_id"],
	)


def downgrade() -> None:
	"""Remove group chat additions."""
	op.drop_index("ix_conv_participants_conv", "conversation_participants")
	op.drop_table("conversation_participants")
	with op.batch_alter_table("message_blocks") as batch_op:
		batch_op.drop_column("group_position")
		batch_op.drop_column("group_id")
		batch_op.drop_column("profile_id")
	with op.batch_alter_table("conversations") as batch_op:
		batch_op.drop_column("is_group_chat")
