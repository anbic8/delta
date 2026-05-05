from __future__ import annotations
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


def _short_uuid() -> str:
    return uuid.uuid4().hex[:8]


class Schueler(Base):
    __tablename__ = "schueler"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorname: Mapped[str] = mapped_column(String(100))
    nachname: Mapped[str] = mapped_column(String(100))
    pseudonym_id: Mapped[str] = mapped_column(String(8), unique=True, default=_short_uuid)
    klasse_id: Mapped[int] = mapped_column(ForeignKey("klassen.id"))
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    klasse: Mapped["Klasse"] = relationship(back_populates="schueler")
