from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Grundwissen(Base):
    __tablename__ = "grundwissen"

    id: Mapped[int] = mapped_column(primary_key=True)
    jahrgangsstufe: Mapped[int] = mapped_column(Integer)
    kapitel: Mapped[str] = mapped_column(String(100))
    unterkapitel: Mapped[str | None] = mapped_column(String(100), nullable=True)
    aufgabe: Mapped[str] = mapped_column(Text)
    loesung: Mapped[str | None] = mapped_column(Text, nullable=True)
    theorielink: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    aufgabe_grundwissen: Mapped[list["AufgabeGrundwissen"]] = relationship(
        back_populates="grundwissen", cascade="all, delete-orphan"
    )


class AufgabeGrundwissen(Base):
    __tablename__ = "aufgabe_grundwissen"
    __table_args__ = (UniqueConstraint("aufgabe_id", "grundwissen_id"),)

    aufgabe_id: Mapped[int] = mapped_column(ForeignKey("aufgaben.id"), primary_key=True)
    grundwissen_id: Mapped[int] = mapped_column(ForeignKey("grundwissen.id"), primary_key=True)

    aufgabe: Mapped["Aufgabe"] = relationship(back_populates="grundwissen_eintraege")
    grundwissen: Mapped["Grundwissen"] = relationship(back_populates="aufgabe_grundwissen")


class SchuelerGrundwissenFehler(Base):
    """Markiert welches Grundwissen ein Schüler bei einer bestimmten Aufgabe nicht beherrscht hat."""
    __tablename__ = "schueler_grundwissen_fehler"
    __table_args__ = (UniqueConstraint("schueler_id", "leistung_aufgabe_id", "grundwissen_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    leistung_aufgabe_id: Mapped[int] = mapped_column(ForeignKey("leistung_aufgaben.id"))
    grundwissen_id: Mapped[int] = mapped_column(ForeignKey("grundwissen.id"))

    grundwissen: Mapped["Grundwissen"] = relationship()
