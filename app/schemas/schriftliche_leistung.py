from datetime import date
from pydantic import BaseModel, field_validator, model_validator
from app.models.schriftliche_leistung import LeistungArt

_ERLAUBTE_GEWICHTUNGEN = {0.5, 1.0, 2.0}


class SchriftlicheLeistungCreate(BaseModel):
    klasse_id: int
    datum: date
    titel: str
    art: LeistungArt
    detailliert: bool = True
    gewichtung: float = 1.0

    @model_validator(mode="after")
    def sa_muss_detailliert_sein(self) -> "SchriftlicheLeistungCreate":
        if self.art == LeistungArt.schulaufgabe and not self.detailliert:
            raise ValueError("Schulaufgaben müssen immer detailliert sein")
        return self

    @field_validator("gewichtung")
    @classmethod
    def gewichtung_gültig(cls, v: float) -> float:
        if v not in _ERLAUBTE_GEWICHTUNGEN:
            raise ValueError("Gewichtung muss 0.5, 1.0 oder 2.0 sein")
        return v


class SchriftlicheLeistungRead(BaseModel):
    id: int
    klasse_id: int
    datum: date
    titel: str
    art: LeistungArt
    detailliert: bool
    gewichtung: float

    model_config = {"from_attributes": True}


class SchriftlicheLeistungUpdate(BaseModel):
    datum: date | None = None
    titel: str | None = None
    gewichtung: float | None = None

    @field_validator("gewichtung")
    @classmethod
    def gewichtung_gültig(cls, v: float | None) -> float | None:
        if v is not None and v not in _ERLAUBTE_GEWICHTUNGEN:
            raise ValueError("Gewichtung muss 0.5, 1.0 oder 2.0 sein")
        return v


class LeistungAufgabeCreate(BaseModel):
    aufgabe_id: int
    aufgabennummer: str
    reihenfolge: int = 1


class LeistungAufgabeRead(BaseModel):
    id: int
    leistung_id: int
    aufgabe_id: int
    reihenfolge: int
    aufgabennummer: str

    model_config = {"from_attributes": True}
