from __future__ import annotations
from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class AppEinstellung(Base):
    __tablename__ = "app_einstellungen"

    schluessel: Mapped[str] = mapped_column(String(100), primary_key=True)
    wert: Mapped[str | None] = mapped_column(Text, nullable=True)
