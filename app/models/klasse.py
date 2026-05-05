from __future__ import annotations
import enum
import sqlalchemy as sa
from sqlalchemy import Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Notensystem(str, enum.Enum):
    sechserskala = "sechserskala"
    punkte = "punkte"


class Klasse(Base):
    __tablename__ = "klassen"

    id: Mapped[int] = mapped_column(primary_key=True)
    jahrgangsstufe: Mapped[int] = mapped_column(Integer)
    buchstabe: Mapped[str] = mapped_column(String(1))
    fach: Mapped[str] = mapped_column(String(50), default="Mathematik")
    notensystem: Mapped[Notensystem] = mapped_column(
        sa.Enum(Notensystem, native_enum=False, length=20)
    )
    schuljahr_id: Mapped[int] = mapped_column(ForeignKey("schuljahre.id"))

    schuljahr: Mapped["Schuljahr"] = relationship(back_populates="klassen")
    schueler: Mapped[list["Schueler"]] = relationship(back_populates="klasse")

    @property
    def name(self) -> str:
        return f"{self.jahrgangsstufe}{self.buchstabe}"
