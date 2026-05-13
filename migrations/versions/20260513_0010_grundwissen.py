"""Grundwissen-Datenbank

Revision ID: 0010
Revises: 0009
Create Date: 2026-05-13
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "grundwissen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jahrgangsstufe", sa.Integer(), nullable=False),
        sa.Column("kapitel", sa.String(100), nullable=False),
        sa.Column("unterkapitel", sa.String(100), nullable=True),
        sa.Column("aufgabe", sa.Text(), nullable=False),
        sa.Column("loesung", sa.Text(), nullable=True),
        sa.Column("theorielink", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aufgabe_grundwissen",
        sa.Column("aufgabe_id", sa.Integer(), nullable=False),
        sa.Column("grundwissen_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["aufgabe_id"], ["aufgaben.id"]),
        sa.ForeignKeyConstraint(["grundwissen_id"], ["grundwissen.id"]),
        sa.PrimaryKeyConstraint("aufgabe_id", "grundwissen_id"),
        sa.UniqueConstraint("aufgabe_id", "grundwissen_id"),
    )


def downgrade() -> None:
    op.drop_table("aufgabe_grundwissen")
    op.drop_table("grundwissen")
