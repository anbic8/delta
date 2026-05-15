"""SchuelerGrundwissenAbfrage: CSV-Import von Grundwissen-Abfragen

Revision ID: 0016
Revises: 0015
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "schueler_grundwissen_abfragen",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("schueler_id", sa.Integer(), sa.ForeignKey("schueler.id"), nullable=False),
        sa.Column("grundwissen_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="SET NULL"), nullable=True),
        sa.Column("datum", sa.Date(), nullable=False),
        sa.Column("ergebnis", sa.String(20), nullable=False),
        sa.Column("grundwissen_text", sa.Text(), nullable=True),
        sa.Column("erstellt_am", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("schueler_grundwissen_abfragen")
