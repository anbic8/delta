from pydantic import BaseModel


class DetailliertEintrag(BaseModel):
    schueler_id: int
    leistung_aufgabe_id: int
    erreichte_punkte: float


class PauschalEintrag(BaseModel):
    schueler_id: int
    pauschalnote: float


class SchuelerErgebnisRead(BaseModel):
    id: int
    schueler_id: int
    leistung_aufgabe_id: int | None
    erreichte_punkte: float | None
    schriftliche_leistung_id: int | None
    pauschalnote: float | None

    model_config = {"from_attributes": True}


# --- SA-Klassenauswertung ---

class AufgabeSpalte(BaseModel):
    aufgabennummer: str
    max_punkte: float


class SchuelerZeile(BaseModel):
    schueler_id: int
    name: str
    punkte_pro_aufgabe: dict[str, float | None]
    summe: float | None
    prozent: float | None
    note: int | None
    grenzfall: bool


class NoteStats(BaseModel):
    anzahl: int
    prozent: float


class SAKlassenauswertung(BaseModel):
    leistung_id: int
    titel: str
    aufgaben: list[AufgabeSpalte]
    max_punkte_gesamt: float
    schueler: list[SchuelerZeile]
    notenverteilung: dict[str, NoteStats]
    klassendurchschnitt: float | None


# --- Kompetenzprofil ---

class KompetenzScore(BaseModel):
    kompetenz_id: int
    kuerzel: str
    bezeichnung: str
    prozent: float


class KompetenzprofilRead(BaseModel):
    schueler_id: int
    scores: list[KompetenzScore]
    leistungen_mit_daten: int
    leistungen_gesamt: int
