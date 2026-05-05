from __future__ import annotations
import enum
from datetime import date
import sqlalchemy as sa
from sqlalchemy import Boolean, Date, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LeistungArt(str, enum.Enum):
    schulaufgabe = "schulaufgabe"
    kleiner_ln = "kleiner_ln"


class SchriftlicheLeistung(Base):
    __tablename__ = "schriftliche_leistungen"

    id: Mapped[int] = mapped_column(primary_key=True)
    klasse_id: Mapped[int] = mapped_column(ForeignKey("klassen.id"))
    datum: Mapped[date] = mapped_column(Date)
    titel: Mapped[str] = mapped_column(String(200))
    art: Mapped[LeistungArt] = mapped_column(sa.Enum(LeistungArt, native_enum=False, length=20))
    detailliert: Mapped[bool] = mapped_column(Boolean)
    gewichtung: Mapped[float] = mapped_column(Float, default=1.0)

    klasse: Mapped["Klasse"] = relationship(back_populates="schriftliche_leistungen")
    leistung_aufgaben: Mapped[list["LeistungAufgabe"]] = relationship(
        back_populates="leistung", cascade="all, delete-orphan", order_by="LeistungAufgabe.reihenfolge"
    )


class LeistungAufgabe(Base):
    __tablename__ = "leistung_aufgaben"

    id: Mapped[int] = mapped_column(primary_key=True)
    leistung_id: Mapped[int] = mapped_column(ForeignKey("schriftliche_leistungen.id"))
    aufgabe_id: Mapped[int] = mapped_column(ForeignKey("aufgaben.id"))
    reihenfolge: Mapped[int] = mapped_column(Integer, default=1)
    aufgabennummer: Mapped[str] = mapped_column(String(10))

    leistung: Mapped["SchriftlicheLeistung"] = relationship(back_populates="leistung_aufgaben")
    aufgabe: Mapped["Aufgabe"] = relationship(back_populates="leistung_aufgaben")
