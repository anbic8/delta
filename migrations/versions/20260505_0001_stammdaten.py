"""Stammdaten: Schuljahr, Klasse, Schueler

Revision ID: 0001
Revises:
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schuljahre",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(10), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_table(
        "klassen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("jahrgangsstufe", sa.Integer(), nullable=False),
        sa.Column("buchstabe", sa.String(1), nullable=False),
        sa.Column("fach", sa.String(50), nullable=False, server_default="Mathematik"),
        sa.Column("notensystem", sa.String(20), nullable=False),
        sa.Column("schuljahr_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schuljahr_id"], ["schuljahre.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "schueler",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("vorname", sa.String(100), nullable=False),
        sa.Column("nachname", sa.String(100), nullable=False),
        sa.Column("pseudonym_id", sa.String(8), nullable=False),
        sa.Column("klasse_id", sa.Integer(), nullable=False),
        sa.Column("geloescht_am", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["klasse_id"], ["klassen.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pseudonym_id"),
    )


def downgrade() -> None:
    op.drop_table("schueler")
    op.drop_table("klassen")
    op.drop_table("schuljahre")
