from __future__ import annotations
import sqlalchemy as sa
from sqlalchemy import Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.aufgabe import AfbNiveau


class Buchaufgabe(Base):
    __tablename__ = "buchaufgaben"
    __table_args__ = (
        sa.UniqueConstraint("buch", "kapitel", "unterkapitel", "aufgabennummer", name="uq_buchaufgabe"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    buch: Mapped[str] = mapped_column(String(200))
    kapitel: Mapped[str] = mapped_column(String(100))
    unterkapitel: Mapped[str] = mapped_column(String(100), default="", server_default="")
    seite: Mapped[int | None] = mapped_column(Integer, nullable=True)
    aufgabennummer: Mapped[str] = mapped_column(String(20))
    beschreibung: Mapped[str | None] = mapped_column(Text, nullable=True)
    afb_niveau: Mapped[AfbNiveau] = mapped_column(sa.Enum(AfbNiveau, native_enum=False, length=10))
    wichtigkeit: Mapped[int] = mapped_column(Integer, default=2)
    minimalfahrplan: Mapped[bool] = mapped_column(sa.Boolean, default=False)

    kompetenzen: Mapped[list["BuchaufgabeKompetenz"]] = relationship(
        back_populates="buchaufgabe", cascade="all, delete-orphan"
    )


class BuchaufgabeKompetenz(Base):
    __tablename__ = "buchaufgabe_kompetenzen"

    buchaufgabe_id: Mapped[int] = mapped_column(ForeignKey("buchaufgaben.id"), primary_key=True)
    kompetenz_id: Mapped[int] = mapped_column(ForeignKey("kompetenzen.id"), primary_key=True)
    gewichtung: Mapped[float] = mapped_column(Float)

    buchaufgabe: Mapped["Buchaufgabe"] = relationship(back_populates="kompetenzen")
    kompetenz: Mapped["Kompetenz"] = relationship()
