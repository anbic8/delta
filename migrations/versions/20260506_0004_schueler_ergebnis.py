"""Schülerergebnisse (detailliert + pauschal)

Revision ID: 0004
Revises: 0003
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schueler_ergebnisse",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("schueler_id", sa.Integer(), nullable=False),
        sa.Column("leistung_aufgabe_id", sa.Integer(), nullable=True),
        sa.Column("erreichte_punkte", sa.Float(), nullable=True),
        sa.Column("schriftliche_leistung_id", sa.Integer(), nullable=True),
        sa.Column("pauschalnote", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["schueler_id"], ["schueler.id"]),
        sa.ForeignKeyConstraint(["leistung_aufgabe_id"], ["leistung_aufgaben.id"]),
        sa.ForeignKeyConstraint(["schriftliche_leistung_id"], ["schriftliche_leistungen.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schueler_id", "leistung_aufgabe_id", name="uq_ergebnis_detailliert"),
        sa.UniqueConstraint("schueler_id", "schriftliche_leistung_id", name="uq_ergebnis_pauschal"),
    )


def downgrade() -> None:
    op.drop_table("schueler_ergebnisse")
