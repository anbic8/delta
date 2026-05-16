from __future__ import annotations
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LiveBewertung(Base):
    __tablename__ = "live_bewertungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    klasse_id: Mapped[int] = mapped_column(ForeignKey("klassen.id"))
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    grundwissen_id: Mapped[int] = mapped_column(ForeignKey("grundwissen.id"))
    zustand: Mapped[int] = mapped_column(Integer)          # 0–4
    datum: Mapped[date] = mapped_column(Date)
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    schueler: Mapped["Schueler"] = relationship()
    grundwissen: Mapped["Grundwissen"] = relationship()
