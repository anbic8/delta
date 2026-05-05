"""Schriftliche Leistung, Aufgabenpool, Kompetenzen K1-K6

Revision ID: 0003
Revises: 0002
Create Date: 2026-05-05
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "kompetenzen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kuerzel", sa.String(3), nullable=False),
        sa.Column("bezeichnung", sa.String(200), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("kuerzel"),
    )
    op.create_table(
        "aufgaben",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("titel", sa.String(200), nullable=False),
        sa.Column("aufgabenstellung", sa.Text(), nullable=False),
        sa.Column("loesung", sa.Text(), nullable=True),
        sa.Column("max_punkte", sa.Float(), nullable=False),
        sa.Column("afb_niveau", sa.String(10), nullable=False),
        sa.Column("tags", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "aufgabe_kompetenzen",
        sa.Column("aufgabe_id", sa.Integer(), nullable=False),
        sa.Column("kompetenz_id", sa.Integer(), nullable=False),
        sa.Column("gewichtung", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(["aufgabe_id"], ["aufgaben.id"]),
        sa.ForeignKeyConstraint(["kompetenz_id"], ["kompetenzen.id"]),
        sa.PrimaryKeyConstraint("aufgabe_id", "kompetenz_id"),
    )
    op.create_table(
        "schriftliche_leistungen",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("klasse_id", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("titel", sa.String(200), nullable=False),
        sa.Column("art", sa.String(20), nullable=False),
        sa.Column("detailliert", sa.Boolean(), nullable=False),
        sa.Column("gewichtung", sa.Float(), nullable=False, server_default="1.0"),
        sa.ForeignKeyConstraint(["klasse_id"], ["klassen.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "leistung_aufgaben",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("leistung_id", sa.Integer(), nullable=False),
        sa.Column("aufgabe_id", sa.Integer(), nullable=False),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("aufgabennummer", sa.String(10), nullable=False),
        sa.ForeignKeyConstraint(["leistung_id"], ["schriftliche_leistungen.id"]),
        sa.ForeignKeyConstraint(["aufgabe_id"], ["aufgaben.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # K1–K6 Seed-Daten
    op.execute("""
        INSERT INTO kompetenzen (kuerzel, bezeichnung) VALUES
        ('K1', 'Mathematisch argumentieren'),
        ('K2', 'Probleme mathematisch lösen'),
        ('K3', 'Mathematisch modellieren'),
        ('K4', 'Mathematische Darstellungen verwenden'),
        ('K5', 'Mit symbolischen, formalen und technischen Elementen umgehen'),
        ('K6', 'Mathematisch kommunizieren')
    """)


def downgrade() -> None:
    op.drop_table("leistung_aufgaben")
    op.drop_table("schriftliche_leistungen")
    op.drop_table("aufgabe_kompetenzen")
    op.drop_table("aufgaben")
    op.drop_table("kompetenzen")
