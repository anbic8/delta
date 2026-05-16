"""Live-Bewertungen (Sitzplan-Modus)

Revision ID: 0019
Revises: 0018
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "live_bewertungen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("klasse_id", sa.Integer(), sa.ForeignKey("klassen.id"), nullable=False),
        sa.Column("schueler_id", sa.Integer(), sa.ForeignKey("schueler.id"), nullable=False),
        sa.Column("grundwissen_id", sa.Integer(), sa.ForeignKey("grundwissen.id"), nullable=False),
        sa.Column("zustand", sa.Integer(), nullable=False),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_live_bew_klasse_datum",
                    "live_bewertungen", ["klasse_id", "datum"])


def downgrade() -> None:
    op.drop_table("live_bewertungen")
