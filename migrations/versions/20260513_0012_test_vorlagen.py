"""Test-Vorlagen

Revision ID: 0012
Revises: 0011
Create Date: 2026-05-13
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0012"
down_revision: Union[str, None] = "0011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "test_vorlagen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "test_vorlage_aufgaben",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vorlage_id", sa.Integer(), nullable=False),
        sa.Column("aufgabe_id", sa.Integer(), nullable=False),
        sa.Column("aufgabennummer", sa.String(10), nullable=False),
        sa.Column("reihenfolge", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["vorlage_id"], ["test_vorlagen.id"]),
        sa.ForeignKeyConstraint(["aufgabe_id"], ["aufgaben.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("test_vorlage_aufgaben")
    op.drop_table("test_vorlagen")
