"""Buchaufgabe: unterkapitel in Unique-Constraint aufnehmen

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-06
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL-Werte auf Leerstring setzen (damit der NOT NULL-Constraint greift)
    op.execute("UPDATE buchaufgaben SET unterkapitel = '' WHERE unterkapitel IS NULL")
    op.alter_column("buchaufgaben", "unterkapitel",
                    existing_type=sa.String(100),
                    nullable=False,
                    server_default="")
    # Alte Constraint entfernen, neue mit unterkapitel anlegen
    op.drop_constraint("uq_buchaufgabe", "buchaufgaben", type_="unique")
    op.create_unique_constraint(
        "uq_buchaufgabe",
        "buchaufgaben",
        ["buch", "kapitel", "unterkapitel", "aufgabennummer"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_buchaufgabe", "buchaufgaben", type_="unique")
    op.create_unique_constraint(
        "uq_buchaufgabe",
        "buchaufgaben",
        ["buch", "kapitel", "aufgabennummer"],
    )
    op.alter_column("buchaufgaben", "unterkapitel",
                    existing_type=sa.String(100),
                    nullable=True,
                    server_default=None)
