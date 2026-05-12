"""Buchaufgabe: unterkapitel + minimalfahrplan

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("buchaufgaben", sa.Column("unterkapitel", sa.String(100), nullable=True))
    op.add_column("buchaufgaben", sa.Column("minimalfahrplan", sa.Boolean(), nullable=False, server_default="false"))


def downgrade() -> None:
    op.drop_column("buchaufgaben", "minimalfahrplan")
    op.drop_column("buchaufgaben", "unterkapitel")
