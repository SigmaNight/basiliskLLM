"""Add web_search_mode column to message_blocks table.

Revision ID: 002
Revises: 001
Create Date: 2026-03-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add web_search_mode column to message_blocks table."""
	op.add_column(
		"message_blocks",
		sa.Column(
			"web_search_mode", sa.Boolean(), nullable=False, server_default="0"
		),
	)


def downgrade() -> None:
	"""Remove web_search_mode column from message_blocks table."""
	op.drop_column("message_blocks", "web_search_mode")
