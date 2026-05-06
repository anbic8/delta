from pydantic import BaseModel, field_validator
from app.models.aufgabe import AfbNiveau


class BuchaufgabeRead(BaseModel):
    id: int
    buch: str
    kapitel: str
    seite: int | None
    aufgabennummer: str
    beschreibung: str | None
    afb_niveau: AfbNiveau
    wichtigkeit: int

    model_config = {"from_attributes": True}


class BuchaufgabeImportErgebnis(BaseModel):
    importiert: int
    aktualisiert: int
    fehler: int
    fehler_details: list[str]
