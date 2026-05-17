"""Grundwissen: Frage, wird_abgefragt, GS-Jahrgangsstufe, Voraussetzungen

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-17
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("grundwissen", sa.Column("frage", sa.Text(), nullable=True))
    op.add_column("grundwissen", sa.Column("wird_abgefragt", sa.Boolean(),
                                            nullable=False, server_default="false"))
    op.create_table(
        "grundwissen_voraussetzungen",
        sa.Column("gw_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("voraussetzung_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="CASCADE"),
                  primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("grundwissen_voraussetzungen")
    op.drop_column("grundwissen", "wird_abgefragt")
    op.drop_column("grundwissen", "frage")
