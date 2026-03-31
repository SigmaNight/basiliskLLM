"""Add usage_json and timing_json columns to message_blocks table.

Revision ID: 005
Revises: 004
Create Date: 2026-03-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add usage_json, timing_json, cost to message_blocks; pricing_snapshot_json to conversations."""
	op.add_column(
		"message_blocks", sa.Column("usage_json", sa.Text(), nullable=True)
	)
	op.add_column(
		"message_blocks", sa.Column("timing_json", sa.Text(), nullable=True)
	)
	op.add_column(
		"message_blocks", sa.Column("cost", sa.Float(), nullable=True)
	)
	op.add_column(
		"message_blocks",
		sa.Column("cost_breakdown_json", sa.Text(), nullable=True),
	)
	op.add_column(
		"conversations",
		sa.Column("pricing_snapshot_json", sa.Text(), nullable=True),
	)


def downgrade() -> None:
	"""Remove added columns."""
	op.drop_column("conversations", "pricing_snapshot_json")
	op.drop_column("message_blocks", "cost_breakdown_json")
	op.drop_column("message_blocks", "cost")
	op.drop_column("message_blocks", "timing_json")
	op.drop_column("message_blocks", "usage_json")
