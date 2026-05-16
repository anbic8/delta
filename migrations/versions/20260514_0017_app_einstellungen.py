"""App-Einstellungen Key-Value-Tabelle

Revision ID: 0017
Revises: 0016
Create Date: 2026-05-14
"""
from typing import Sequence, Union
import sqlalchemy as sa
from alembic import op

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "app_einstellungen",
        sa.Column("schluessel", sa.String(100), primary_key=True),
        sa.Column("wert", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("app_einstellungen")
