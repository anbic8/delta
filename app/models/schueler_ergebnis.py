from __future__ import annotations
from sqlalchemy import Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SchuelerErgebnis(Base):
    __tablename__ = "schueler_ergebnisse"
    __table_args__ = (
        UniqueConstraint("schueler_id", "leistung_aufgabe_id", name="uq_ergebnis_detailliert"),
        UniqueConstraint("schueler_id", "schriftliche_leistung_id", name="uq_ergebnis_pauschal"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    schueler_id: Mapped[int] = mapped_column(ForeignKey("schueler.id"))
    # Variante A – detailliert: Punkte pro Aufgabe
    leistung_aufgabe_id: Mapped[int | None] = mapped_column(ForeignKey("leistung_aufgaben.id"), nullable=True)
    erreichte_punkte: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Variante B – pauschal: direkte Note für die Leistung
    schriftliche_leistung_id: Mapped[int | None] = mapped_column(
        ForeignKey("schriftliche_leistungen.id"), nullable=True
    )
    pauschalnote: Mapped[float | None] = mapped_column(Float, nullable=True)

    schueler: Mapped["Schueler"] = relationship(back_populates="ergebnisse")
    leistung_aufgabe: Mapped["LeistungAufgabe | None"] = relationship()
    schriftliche_leistung: Mapped["SchriftlicheLeistung | None"] = relationship()
