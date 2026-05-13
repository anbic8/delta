"""Buchaufgabe: im_unterricht

Revision ID: 0013
Revises: 0012
Create Date: 2026-05-13
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "buchaufgaben",
        sa.Column("im_unterricht", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("buchaufgaben", "im_unterricht")
