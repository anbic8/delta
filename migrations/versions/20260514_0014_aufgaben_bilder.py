"""Aufgabe: bild_aufgabe und bild_loesung

Revision ID: 0014
Revises: 0013
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("aufgaben", sa.Column("bild_aufgabe", sa.String(255), nullable=True))
    op.add_column("aufgaben", sa.Column("bild_loesung", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("aufgaben", "bild_loesung")
    op.drop_column("aufgaben", "bild_aufgabe")
