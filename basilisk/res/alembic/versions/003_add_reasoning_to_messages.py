"""Add reasoning column to messages table.

Revision ID: 003
Revises: 002
Create Date: 2026-03-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add reasoning column to messages table."""
	op.add_column("messages", sa.Column("reasoning", sa.Text(), nullable=True))


def downgrade() -> None:
	"""Remove reasoning column from messages table."""
	op.drop_column("messages", "reasoning")
