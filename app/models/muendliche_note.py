from __future__ import annotations
from datetime import date, datetime
import sqlalchemy as sa
from sqlalchemy import Date, DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.klasse import Notensystem


class MuendlicheNote(Base):
    __tablename__ = "muendliche_noten"

    id: Mapped[int] = mapped_column(primary_key=True)
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    datum: Mapped[date] = mapped_column(Date)
    note: Mapped[float] = mapped_column(Float)
    notensystem: Mapped[Notensystem] = mapped_column(
        sa.Enum(Notensystem, native_enum=False, length=20)
    )
    gewichtung: Mapped[float] = mapped_column(Float)
    beschreibung: Mapped[str | None] = mapped_column(String(255), nullable=True, default=None)
    geloescht_am: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, default=None)

    schueler: Mapped["Schueler"] = relationship(back_populates="muendliche_noten")
