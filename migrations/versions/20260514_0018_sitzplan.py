"""Sitzplan-Tabelle

Revision ID: 0018
Revises: 0017
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: Union[str, None] = "0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sitzplan_plaetze",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("klasse_id", sa.Integer(), sa.ForeignKey("klassen.id"), nullable=False),
        sa.Column("schueler_id", sa.Integer(), sa.ForeignKey("schueler.id"), nullable=False),
        sa.Column("reihe", sa.Integer(), nullable=False),
        sa.Column("spalte", sa.Integer(), nullable=False),
        sa.UniqueConstraint("klasse_id", "reihe", "spalte"),
        sa.UniqueConstraint("klasse_id", "schueler_id"),
    )


def downgrade() -> None:
    op.drop_table("sitzplan_plaetze")
