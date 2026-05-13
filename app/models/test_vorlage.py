from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TestVorlage(Base):
    __tablename__ = "test_vorlagen"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    aufgaben: Mapped[list["TestVorlageAufgabe"]] = relationship(
        back_populates="vorlage", cascade="all, delete-orphan",
        order_by="TestVorlageAufgabe.reihenfolge",
    )


class TestVorlageAufgabe(Base):
    __tablename__ = "test_vorlage_aufgaben"

    id: Mapped[int] = mapped_column(primary_key=True)
    vorlage_id: Mapped[int] = mapped_column(ForeignKey("test_vorlagen.id"))
    aufgabe_id: Mapped[int] = mapped_column(ForeignKey("aufgaben.id"))
    aufgabennummer: Mapped[str] = mapped_column(String(10))
    reihenfolge: Mapped[int] = mapped_column(Integer, default=1)

    vorlage: Mapped["TestVorlage"] = relationship(back_populates="aufgaben")
    aufgabe: Mapped["Aufgabe"] = relationship()
