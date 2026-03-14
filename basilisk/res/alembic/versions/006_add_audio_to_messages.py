"""Add audio_data and audio_format to messages table.

Revision ID: 006
Revises: 005
Create Date: 2026-03-06

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
	"""Add audio columns to messages table."""
	op.add_column("messages", sa.Column("audio_data", sa.Text(), nullable=True))
	op.add_column(
		"messages", sa.Column("audio_format", sa.String(), nullable=True)
	)


def downgrade() -> None:
	"""Remove audio columns from messages table."""
	op.drop_column("messages", "audio_format")
	op.drop_column("messages", "audio_data")
