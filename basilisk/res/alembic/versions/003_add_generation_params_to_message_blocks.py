"""Add frequency_penalty, presence_penalty, seed, top_k, stop_json to message_blocks.

Revision ID: 003
Revises: 002
Create Date: 2026-03-15

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add generation params columns to message_blocks table."""
	op.add_column(
		"message_blocks",
		sa.Column(
			"frequency_penalty", sa.Float(), nullable=False, server_default="0"
		),
	)
	op.add_column(
		"message_blocks",
		sa.Column(
			"presence_penalty", sa.Float(), nullable=False, server_default="0"
		),
	)
	op.add_column(
		"message_blocks", sa.Column("seed", sa.Integer(), nullable=True)
	)
	op.add_column(
		"message_blocks", sa.Column("top_k", sa.Integer(), nullable=True)
	)
	op.add_column(
		"message_blocks", sa.Column("stop_json", sa.String(), nullable=True)
	)


def downgrade() -> None:
	"""Remove generation params columns from message_blocks table."""
	op.drop_column("message_blocks", "stop_json")
	op.drop_column("message_blocks", "top_k")
	op.drop_column("message_blocks", "seed")
	op.drop_column("message_blocks", "presence_penalty")
	op.drop_column("message_blocks", "frequency_penalty")
