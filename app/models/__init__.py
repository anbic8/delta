from app.models.schuljahr import Schuljahr
from app.models.klasse import Klasse, Notensystem
from app.models.schueler import Schueler
from app.models.muendliche_note import MuendlicheNote
from app.models.kompetenz import Kompetenz
from app.models.aufgabe import Aufgabe, AufgabeKompetenz, AfbNiveau
from app.models.schriftliche_leistung import SchriftlicheLeistung, LeistungAufgabe, LeistungArt
from app.models.schueler_ergebnis import SchuelerErgebnis
from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
from app.models.grundwissen import Grundwissen, AufgabeGrundwissen, SchuelerGrundwissenFehler

__all__ = [
    "Schuljahr", "Klasse", "Notensystem", "Schueler", "MuendlicheNote",
    "Kompetenz", "Aufgabe", "AufgabeKompetenz", "AfbNiveau",
    "SchriftlicheLeistung", "LeistungAufgabe", "LeistungArt",
    "SchuelerErgebnis",
    "Buchaufgabe", "BuchaufgabeKompetenz",
    "Grundwissen", "AufgabeGrundwissen", "SchuelerGrundwissenFehler",
]
