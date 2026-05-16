from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import ForeignKey, String, Text
from app.database import Base


class JahresplanStunde(Base):
    __tablename__ = "jahresplan_stunden"

    id: Mapped[int] = mapped_column(primary_key=True)
    jahrgangsstufe: Mapped[int]
    stunden_nr: Mapped[int]
    kapitel: Mapped[str | None] = mapped_column(String(200))
    unterkapitel: Mapped[str | None] = mapped_column(String(200))
    gw1_id: Mapped[int | None] = mapped_column(ForeignKey("grundwissen.id", ondelete="SET NULL"))
    gw2_id: Mapped[int | None] = mapped_column(ForeignKey("grundwissen.id", ondelete="SET NULL"))
    gw3_id: Mapped[int | None] = mapped_column(ForeignKey("grundwissen.id", ondelete="SET NULL"))
    notizen: Mapped[str | None] = mapped_column(Text)

    gw1: Mapped["Grundwissen | None"] = relationship("Grundwissen", foreign_keys="[JahresplanStunde.gw1_id]")
    gw2: Mapped["Grundwissen | None"] = relationship("Grundwissen", foreign_keys="[JahresplanStunde.gw2_id]")
    gw3: Mapped["Grundwissen | None"] = relationship("Grundwissen", foreign_keys="[JahresplanStunde.gw3_id]")
