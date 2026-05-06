import pytest
from tests.conftest import TestingSessionLocal
from app.models.kompetenz import Kompetenz
from app.models.buchaufgabe import Buchaufgabe, BuchaufgabeKompetenz
from app.models.aufgabe import AfbNiveau
from app.services.empfehlung import empfehlungen


KOMPETENZEN = [
    ("K1", "Argumentieren"), ("K2", "Problemlösen"), ("K3", "Modellieren"),
    ("K4", "Darstellen"), ("K5", "Technisch"), ("K6", "Kommunizieren"),
]


@pytest.fixture(autouse=True)
def seed_db(client):
    db = TestingSessionLocal()
    for kuerzel, bez in KOMPETENZEN:
        db.add(Kompetenz(kuerzel=kuerzel, bezeichnung=bez))
    db.commit()

    # K2 und K5: je 3 Buchaufgaben (AFB I + II gemischt)
    k2 = db.query(Kompetenz).filter(Kompetenz.kuerzel == "K2").first()
    k5 = db.query(Kompetenz).filter(Kompetenz.kuerzel == "K5").first()
    k1 = db.query(Kompetenz).filter(Kompetenz.kuerzel == "K1").first()

    aufgaben = [
        Buchaufgabe(buch="LS9", kapitel="Kap1", aufgabennummer="1", seite=10,
                    afb_niveau=AfbNiveau.AFB_I, wichtigkeit=3),
        Buchaufgabe(buch="LS9", kapitel="Kap1", aufgabennummer="2", seite=11,
                    afb_niveau=AfbNiveau.AFB_I, wichtigkeit=2),
        Buchaufgabe(buch="LS9", kapitel="Kap2", aufgabennummer="1", seite=20,
                    afb_niveau=AfbNiveau.AFB_II, wichtigkeit=3),
        Buchaufgabe(buch="LS9", kapitel="Kap2", aufgabennummer="2", seite=21,
                    afb_niveau=AfbNiveau.AFB_II, wichtigkeit=1),
        Buchaufgabe(buch="LS10", kapitel="Kap1", aufgabennummer="1", seite=30,
                    afb_niveau=AfbNiveau.AFB_I, wichtigkeit=2),
        Buchaufgabe(buch="LS10", kapitel="Kap1", aufgabennummer="2", seite=31,
                    afb_niveau=AfbNiveau.AFB_III, wichtigkeit=3),
    ]
    for a in aufgaben:
        db.add(a)
    db.flush()

    # Kap1 Aufg1+2 → K2; Kap2 Aufg1+2 → K5; LS10 Kap1 Aufg1 → K2; Aufg2 → K1
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[0].id, kompetenz_id=k2.id, gewichtung=1.0))
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[1].id, kompetenz_id=k2.id, gewichtung=1.0))
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[2].id, kompetenz_id=k5.id, gewichtung=1.0))
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[3].id, kompetenz_id=k5.id, gewichtung=1.0))
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[4].id, kompetenz_id=k2.id, gewichtung=1.0))
    db.add(BuchaufgabeKompetenz(buchaufgabe_id=aufgaben[5].id, kompetenz_id=k1.id, gewichtung=1.0))
    db.commit()
    db.close()


def _k_ids(db):
    return {k.kuerzel: k.id for k in db.query(Kompetenz).all()}


# --- Szenario 1: Alle Kompetenzen gut → keine Empfehlungen ---
def test_keine_empfehlung_wenn_alles_gut(client):
    db = TestingSessionLocal()
    ids = _k_ids(db)
    profil = {ids["K1"]: 80.0, ids["K2"]: 75.0, ids["K5"]: 90.0}
    ergebnis = empfehlungen(schueler_id=1, db=db, profil_override=profil)
    db.close()
    assert ergebnis == []


# --- Szenario 2: Sehr schwache Kompetenz (<40%) → nur AFB_I ---
def test_sehr_schwach_nur_afb_i(client):
    db = TestingSessionLocal()
    ids = _k_ids(db)
    profil = {ids["K2"]: 25.0}
    ergebnis = empfehlungen(schueler_id=1, db=db, anzahl=5, profil_override=profil)
    db.close()
    for e in ergebnis:
        assert e.afb_niveau == AfbNiveau.AFB_I
        assert e.kompetenz_kuerzel == "K2"
    assert len(ergebnis) > 0


# --- Szenario 3: Schwache Kompetenz (40-60%) → AFB_I und AFB_II erlaubt ---
def test_schwach_afb_i_und_ii(client):
    db = TestingSessionLocal()
    ids = _k_ids(db)
    profil = {ids["K5"]: 50.0}
    ergebnis = empfehlungen(schueler_id=1, db=db, anzahl=5, profil_override=profil)
    db.close()
    niveau_menge = {e.afb_niveau for e in ergebnis}
    assert AfbNiveau.AFB_I in niveau_menge or AfbNiveau.AFB_II in niveau_menge
    assert AfbNiveau.AFB_III not in niveau_menge


# --- Szenario 4: Diversitätsbeschränkung (max 2 pro Kapitel) ---
def test_diversitaet_max_pro_kapitel(client):
    db = TestingSessionLocal()
    ids = _k_ids(db)
    # K2 hat 2 Aufgaben in LS9/Kap1 und 1 in LS10/Kap1 → maximal 2 aus Kap1
    profil = {ids["K2"]: 30.0}
    ergebnis = empfehlungen(schueler_id=1, db=db, anzahl=10, profil_override=profil)
    db.close()
    zaehler: dict[str, int] = {}
    for e in ergebnis:
        key = f"{e.buch}::{e.kapitel}"
        zaehler[key] = zaehler.get(key, 0) + 1
    for key, anzahl_val in zaehler.items():
        assert anzahl_val <= 2, f"{key} hat {anzahl_val} Empfehlungen (max 2)"


# --- Szenario 5: Mehrere schwache Kompetenzen → schwächste zuerst ---
def test_mehrere_schwach_schwaechste_zuerst(client):
    db = TestingSessionLocal()
    ids = _k_ids(db)
    profil = {ids["K2"]: 55.0, ids["K5"]: 30.0}
    ergebnis = empfehlungen(schueler_id=1, db=db, anzahl=5, profil_override=profil)
    db.close()
    # K5 ist schwächer (30%) → sollte zuerst erscheinen
    assert len(ergebnis) > 0
    assert ergebnis[0].kompetenz_kuerzel == "K5"


# --- API-Endpoint Test ---
def test_api_empfehlung_404(client):
    r = client.get("/schueler/9999/empfehlung")
    assert r.status_code == 404


def test_api_empfehlung_leer_ohne_daten(client):
    from app.models.klasse import Klasse, Notensystem
    from app.models.schuljahr import Schuljahr
    from app.models.schueler import Schueler
    db = TestingSessionLocal()
    sj = Schuljahr(name="2025/26")
    db.add(sj)
    db.flush()
    kl = Klasse(jahrgangsstufe=9, buchstabe="a", schuljahr_id=sj.id, notensystem=Notensystem.sechserskala)
    db.add(kl)
    db.flush()
    s = Schueler(vorname="Max", nachname="Muster", klasse_id=kl.id)
    db.add(s)
    db.commit()
    s_id = s.id
    db.close()
    r = client.get(f"/schueler/{s_id}/empfehlung")
    assert r.status_code == 200
    assert r.json() == []
