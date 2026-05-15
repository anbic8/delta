from __future__ import annotations
import enum
from datetime import date, datetime, timezone
from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import sqlalchemy as sa
from app.database import Base


class AbfrageErgebnis(str, enum.Enum):
    gewusst = "gewusst"
    teilweise_gewusst = "teilweise_gewusst"
    nicht_gewusst = "nicht_gewusst"


class SchuelerGrundwissenAbfrage(Base):
    __tablename__ = "schueler_grundwissen_abfragen"

    id: Mapped[int] = mapped_column(primary_key=True)
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    grundwissen_id: Mapped[int | None] = mapped_column(ForeignKey("grundwissen.id", ondelete="SET NULL"), nullable=True)
    datum: Mapped[date] = mapped_column(Date)
    ergebnis: Mapped[AbfrageErgebnis] = mapped_column(sa.Enum(AbfrageErgebnis, native_enum=False, length=20))
    grundwissen_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    schueler: Mapped["Schueler"] = relationship()
    grundwissen: Mapped["Grundwissen | None"] = relationship()
