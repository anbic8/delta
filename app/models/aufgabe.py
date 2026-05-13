from __future__ import annotations
import enum
from datetime import datetime, timezone
import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class AfbNiveau(str, enum.Enum):
    AFB_I = "AFB_I"
    AFB_II = "AFB_II"
    AFB_III = "AFB_III"


class Aufgabe(Base):
    __tablename__ = "aufgaben"

    id: Mapped[int] = mapped_column(primary_key=True)
    titel: Mapped[str] = mapped_column(String(200))
    aufgabenstellung: Mapped[str] = mapped_column(Text)
    loesung: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_punkte: Mapped[float] = mapped_column(Float)
    afb_niveau: Mapped[AfbNiveau] = mapped_column(sa.Enum(AfbNiveau, native_enum=False, length=10))
    tags: Mapped[str | None] = mapped_column(Text, nullable=True)
    jahrgangsstufe: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kapitel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    unterkapitel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    kompetenzen: Mapped[list["AufgabeKompetenz"]] = relationship(
        back_populates="aufgabe", cascade="all, delete-orphan"
    )
    leistung_aufgaben: Mapped[list["LeistungAufgabe"]] = relationship(back_populates="aufgabe")
    grundwissen_eintraege: Mapped[list["AufgabeGrundwissen"]] = relationship(
        back_populates="aufgabe", cascade="all, delete-orphan"
    )


class AufgabeKompetenz(Base):
    __tablename__ = "aufgabe_kompetenzen"

    aufgabe_id: Mapped[int] = mapped_column(ForeignKey("aufgaben.id"), primary_key=True)
    kompetenz_id: Mapped[int] = mapped_column(ForeignKey("kompetenzen.id"), primary_key=True)
    gewichtung: Mapped[float] = mapped_column(Float)

    aufgabe: Mapped["Aufgabe"] = relationship(back_populates="kompetenzen")
    kompetenz: Mapped["Kompetenz"] = relationship(back_populates="aufgabe_kompetenzen")
