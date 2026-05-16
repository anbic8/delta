from __future__ import annotations
from sqlalchemy import ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SitzplanPlatz(Base):
    __tablename__ = "sitzplan_plaetze"
    __table_args__ = (
        UniqueConstraint("klasse_id", "reihe", "spalte"),
        UniqueConstraint("klasse_id", "schueler_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    klasse_id: Mapped[int] = mapped_column(ForeignKey("klassen.id"))
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    reihe: Mapped[int] = mapped_column(Integer)
    spalte: Mapped[int] = mapped_column(Integer)

    schueler: Mapped["Schueler"] = relationship()
