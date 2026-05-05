from datetime import date, datetime
from pydantic import BaseModel, field_validator
from app.models.klasse import Notensystem

_ERLAUBTE_GEWICHTUNGEN = {0.5, 1.0, 2.0}


def _gewichtung_prüfen(v: float | None) -> float | None:
    if v is not None and v not in _ERLAUBTE_GEWICHTUNGEN:
        raise ValueError("Gewichtung muss 0.5, 1.0 oder 2.0 sein")
    return v


class MuendlicheNoteCreate(BaseModel):
    schueler_id: int
    datum: date
    note: float
    gewichtung: float = 1.0
    beschreibung: str | None = None

    @field_validator("gewichtung")
    @classmethod
    def gewichtung_gültig(cls, v: float) -> float:
        return _gewichtung_prüfen(v)


class MuendlicheNoteRead(BaseModel):
    id: int
    schueler_id: int
    datum: date
    note: float
    notensystem: Notensystem
    gewichtung: float
    beschreibung: str | None
    geloescht_am: datetime | None

    model_config = {"from_attributes": True}


class MuendlicheNoteUpdate(BaseModel):
    note: float | None = None
    datum: date | None = None
    gewichtung: float | None = None
    beschreibung: str | None = None

    @field_validator("gewichtung")
    @classmethod
    def gewichtung_gültig(cls, v: float | None) -> float | None:
        return _gewichtung_prüfen(v)
