"""Jahresplan pro Jahrgangsstufe

Revision ID: 0020
Revises: 0019
Create Date: 2026-05-16
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0020"
down_revision: Union[str, None] = "0019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "jahresplan_stunden",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("jahrgangsstufe", sa.Integer(), nullable=False),
        sa.Column("stunden_nr", sa.Integer(), nullable=False),
        sa.Column("kapitel", sa.String(200)),
        sa.Column("unterkapitel", sa.String(200)),
        sa.Column("gw1_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="SET NULL")),
        sa.Column("gw2_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="SET NULL")),
        sa.Column("gw3_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="SET NULL")),
        sa.Column("notizen", sa.Text()),
    )
    op.create_index("ix_jahresplan_jg", "jahresplan_stunden", ["jahrgangsstufe", "stunden_nr"])


def downgrade() -> None:
    op.drop_table("jahresplan_stunden")
