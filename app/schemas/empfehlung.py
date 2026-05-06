from pydantic import BaseModel
from app.models.aufgabe import AfbNiveau


class EmpfehlungRead(BaseModel):
    buchaufgabe_id: int
    buch: str
    kapitel: str
    seite: int | None
    aufgabennummer: str
    beschreibung: str | None
    afb_niveau: AfbNiveau
    wichtigkeit: int
    kompetenz_kuerzel: str
    kompetenz_score: float
    begruendung: str

    model_config = {"from_attributes": True}
