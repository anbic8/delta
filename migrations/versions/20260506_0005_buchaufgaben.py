"""Buchaufgaben-Katalog

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "buchaufgaben",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("buch", sa.String(200), nullable=False),
        sa.Column("kapitel", sa.String(100), nullable=False),
        sa.Column("seite", sa.Integer(), nullable=True),
        sa.Column("aufgabennummer", sa.String(20), nullable=False),
        sa.Column("beschreibung", sa.Text(), nullable=True),
        sa.Column("afb_niveau", sa.String(10), nullable=False),
        sa.Column("wichtigkeit", sa.Integer(), nullable=False, server_default="2"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("buch", "kapitel", "aufgabennummer", name="uq_buchaufgabe"),
    )
    op.create_table(
        "buchaufgabe_kompetenzen",
        sa.Column("buchaufgabe_id", sa.Integer(), nullable=False),
        sa.Column("kompetenz_id", sa.Integer(), nullable=False),
        sa.Column("gewichtung", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["buchaufgabe_id"], ["buchaufgaben.id"]),
        sa.ForeignKeyConstraint(["kompetenz_id"], ["kompetenzen.id"]),
        sa.PrimaryKeyConstraint("buchaufgabe_id", "kompetenz_id"),
    )


def downgrade() -> None:
    op.drop_table("buchaufgabe_kompetenzen")
    op.drop_table("buchaufgaben")
