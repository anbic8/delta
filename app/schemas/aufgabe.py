from datetime import datetime
from pydantic import BaseModel
from app.models.aufgabe import AfbNiveau


class KompetenzMini(BaseModel):
    id: int
    kuerzel: str
    model_config = {"from_attributes": True}


class AufgabeKompetenzCreate(BaseModel):
    kompetenz_id: int
    gewichtung: float


class AufgabeKompetenzRead(BaseModel):
    kompetenz_id: int
    gewichtung: float
    kompetenz: KompetenzMini

    model_config = {"from_attributes": True}


class AufgabeCreate(BaseModel):
    titel: str
    aufgabenstellung: str
    loesung: str | None = None
    max_punkte: float
    afb_niveau: AfbNiveau
    tags: str | None = None


class AufgabeRead(BaseModel):
    id: int
    titel: str
    aufgabenstellung: str
    loesung: str | None
    max_punkte: float
    afb_niveau: AfbNiveau
    tags: str | None
    kapitel: str | None
    unterkapitel: str | None
    erstellt_am: datetime

    model_config = {"from_attributes": True}


class AufgabeUpdate(BaseModel):
    titel: str | None = None
    aufgabenstellung: str | None = None
    loesung: str | None = None
    max_punkte: float | None = None
    afb_niveau: AfbNiveau | None = None
    tags: str | None = None
    kapitel: str | None = None
    unterkapitel: str | None = None
