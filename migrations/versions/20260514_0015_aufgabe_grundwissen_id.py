"""Aufgabe: grundwissen_id (Aufgabe ist Grundwissen)

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "aufgaben",
        sa.Column("grundwissen_id", sa.Integer(), sa.ForeignKey("grundwissen.id", ondelete="SET NULL"), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("aufgaben", "grundwissen_id")
