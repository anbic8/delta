from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Kompetenz(Base):
    __tablename__ = "kompetenzen"

    id: Mapped[int] = mapped_column(primary_key=True)
    kuerzel: Mapped[str] = mapped_column(String(3), unique=True)
    bezeichnung: Mapped[str] = mapped_column(String(200))

    aufgabe_kompetenzen: Mapped[list["AufgabeKompetenz"]] = relationship(back_populates="kompetenz")
