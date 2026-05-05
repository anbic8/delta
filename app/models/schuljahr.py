from __future__ import annotations
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Schuljahr(Base):
    __tablename__ = "schuljahre"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(10), unique=True)

    klassen: Mapped[list["Klasse"]] = relationship(back_populates="schuljahr")
