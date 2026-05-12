"""Aufgabe: kapitel + unterkapitel fuer Buchaufgaben-Zuordnung

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("aufgaben", sa.Column("kapitel", sa.String(100), nullable=True))
    op.add_column("aufgaben", sa.Column("unterkapitel", sa.String(100), nullable=True))


def downgrade() -> None:
    op.drop_column("aufgaben", "unterkapitel")
    op.drop_column("aufgaben", "kapitel")
