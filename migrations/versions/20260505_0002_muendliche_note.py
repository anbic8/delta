"""Mündliche Noten

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "muendliche_noten",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schueler_id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("note", sa.Float(), nullable=False),
        sa.Column("notensystem", sa.String(20), nullable=False),
        sa.Column("gewichtung", sa.Float(), nullable=False),
        sa.Column("beschreibung", sa.String(255), nullable=True),
        sa.Column("geloescht_am", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["schueler_id"], ["schueler.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("muendliche_noten")
