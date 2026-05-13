"""Schüler-Grundwissen-Fehler

Revision ID: 0011
Revises: 0010
Create Date: 2026-05-13
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: Union[str, None] = "0010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schueler_grundwissen_fehler",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schueler_id", sa.Integer(), nullable=False),
        sa.Column("leistung_aufgabe_id", sa.Integer(), nullable=False),
        sa.Column("grundwissen_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schueler_id"], ["schueler.id"]),
        sa.ForeignKeyConstraint(["leistung_aufgabe_id"], ["leistung_aufgaben.id"]),
        sa.ForeignKeyConstraint(["grundwissen_id"], ["grundwissen.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schueler_id", "leistung_aufgabe_id", "grundwissen_id"),
    )


def downgrade() -> None:
    op.drop_table("schueler_grundwissen_fehler")
