"""
Integrationstest Phase 4: Ergebnisse, Schnitte, Auswertung, Kompetenzprofil.
Handrechnung-Verifikation des Akzeptanzkriteriums.
"""
import pytest
from tests.conftest import TestingSessionLocal
from app.models.kompetenz import Kompetenz


@pytest.fixture(autouse=True)
def seed_kompetenzen(client):
    # client muss zuerst laufen (erstellt Tabellen via Base.metadata.create_all)
    db = TestingSessionLocal()
    for k, b in [("K1", "Argumentieren"), ("K2", "Problemlösen"), ("K3", "Modellieren")]:
        db.add(Kompetenz(kuerzel=k, bezeichnung=b))
    db.commit()
    db.close()


@pytest.fixture
def setup(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    kl = client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()
    s = client.post("/schueler/", json={"vorname": "Max", "nachname": "Muster", "klasse_id": kl["id"]}).json()
    return {"klasse": kl, "schueler": s}


def _aufgabe(client, punkte=10.0):
    return client.post("/aufgaben/", json={
        "titel": "A", "aufgabenstellung": "x", "max_punkte": punkte, "afb_niveau": "AFB_I",
    }).json()


def _sa_mit_aufgaben(client, klasse_id, aufgaben_punkte):
    sa = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse_id, "datum": "2026-03-01", "titel": "SA",
        "art": "schulaufgabe", "detailliert": True, "gewichtung": 1.0,
    }).json()
    las = []
    for i, p in enumerate(aufgaben_punkte, 1):
        a = _aufgabe(client, p)
        la = client.post(f"/schriftliche-leistungen/{sa['id']}/aufgaben", json={
            "aufgabe_id": a["id"], "aufgabennummer": str(i), "reihenfolge": i,
        }).json()
        las.append(la)
    return sa, las


# --- Ergebnisse eintragen ---

def test_ergebnisse_detailliert(client, setup):
    sa, las = _sa_mit_aufgaben(client, setup["klasse"]["id"], [10.0, 10.0])
    s_id = setup["schueler"]["id"]
    r = client.put(f"/schriftliche-leistungen/{sa['id']}/ergebnisse/detailliert", json=[
        {"schueler_id": s_id, "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": 8.0},
        {"schueler_id": s_id, "leistung_aufgabe_id": las[1]["id"], "erreichte_punkte": 7.0},
    ])
    assert r.status_code == 204


def test_ergebnisse_punkte_zu_hoch(client, setup):
    sa, las = _sa_mit_aufgaben(client, setup["klasse"]["id"], [10.0])
    r = client.put(f"/schriftliche-leistungen/{sa['id']}/ergebnisse/detailliert", json=[
        {"schueler_id": setup["schueler"]["id"], "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": 11.0},
    ])
    assert r.status_code == 422


def test_ergebnisse_pauschal(client, setup):
    ln = client.post("/schriftliche-leistungen/", json={
        "klasse_id": setup["klasse"]["id"], "datum": "2026-02-01",
        "titel": "LN pauschal", "art": "kleiner_ln", "detailliert": False,
    }).json()
    r = client.put(f"/schriftliche-leistungen/{ln['id']}/ergebnisse/pauschal", json=[
        {"schueler_id": setup["schueler"]["id"], "pauschalnote": 3.0},
    ])
    assert r.status_code == 204


# --- Schnitte (Handrechnung) ---

def test_gesamtschnitt_handrechnung(client, setup):
    """
    SA (gewichtung=1): 17/20 Punkte = 85% → Note 1
    Kleiner LN pauschal (gewichtung=1): Note 3
    Mündlich (gewichtung=1): Note 2

    Schnitt große LN = 1.0
    Schnitt kleine LN = (3*1 + 2*1) / 2 = 2.5
    Gesamtschnitt = (2*1 + 2.5) / 3 = 4.5/3 = 1.5
    """
    s_id = setup["schueler"]["id"]
    kl_id = setup["klasse"]["id"]

    # SA
    sa, las = _sa_mit_aufgaben(client, kl_id, [10.0, 10.0])
    client.put(f"/schriftliche-leistungen/{sa['id']}/ergebnisse/detailliert", json=[
        {"schueler_id": s_id, "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": 9.0},
        {"schueler_id": s_id, "leistung_aufgabe_id": las[1]["id"], "erreichte_punkte": 8.0},
    ])

    # Kleiner LN pauschal
    ln = client.post("/schriftliche-leistungen/", json={
        "klasse_id": kl_id, "datum": "2026-02-01", "titel": "LN", "art": "kleiner_ln",
        "detailliert": False, "gewichtung": 1.0,
    }).json()
    client.put(f"/schriftliche-leistungen/{ln['id']}/ergebnisse/pauschal", json=[
        {"schueler_id": s_id, "pauschalnote": 3.0},
    ])

    # Mündlich
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-01-10", "note": 2.0, "gewichtung": 1.0})

    r = client.get(f"/schueler/{s_id}/schnitt")
    data = r.json()
    assert data["schnitt_grosse_ln"] == 1.0
    assert data["schnitt_kleine_ln"] == 2.5
    assert data["gesamtschnitt"] == round((2 * 1.0 + 2.5) / 3, 2)


# --- SA-Auswertung + Grenzfall ---

def test_auswertung_grenzfall(client, setup):
    """
    SA mit 40 Punkten. Grenze Note 2→1: 85% = 34 Punkte.
    Schüler mit 33.5 Punkte → Grenzfall.
    Schüler mit 33.4 Punkte → kein Grenzfall.
    """
    kl_id = setup["klasse"]["id"]
    sj = client.post("/schuljahre/", json={"name": "2024/25"}).json()
    kl2 = client.post("/klassen/", json={"jahrgangsstufe": 9, "buchstabe": "b", "schuljahr_id": sj["id"]}).json()
    s1 = client.post("/schueler/", json={"vorname": "A", "nachname": "B", "klasse_id": kl2["id"]}).json()
    s2 = client.post("/schueler/", json={"vorname": "C", "nachname": "D", "klasse_id": kl2["id"]}).json()

    sa, las = _sa_mit_aufgaben(client, kl2["id"], [20.0, 20.0])

    client.put(f"/schriftliche-leistungen/{sa['id']}/ergebnisse/detailliert", json=[
        {"schueler_id": s1["id"], "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": 20.0},
        {"schueler_id": s1["id"], "leistung_aufgabe_id": las[1]["id"], "erreichte_punkte": 13.5},
        {"schueler_id": s2["id"], "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": 20.0},
        {"schueler_id": s2["id"], "leistung_aufgabe_id": las[1]["id"], "erreichte_punkte": 13.4},
    ])

    r = client.get(f"/schriftliche-leistungen/{sa['id']}/auswertung")
    assert r.status_code == 200
    zeilen = {z["schueler_id"]: z for z in r.json()["schueler"]}
    assert zeilen[s1["id"]]["grenzfall"] is True   # 33.5 → Grenzfall
    assert zeilen[s2["id"]]["grenzfall"] is False  # 33.4 → kein Grenzfall


def test_auswertung_notenverteilung(client, setup):
    kl_id = setup["klasse"]["id"]
    sj = client.post("/schuljahre/", json={"name": "2024/25"}).json()
    kl = client.post("/klassen/", json={"jahrgangsstufe": 7, "buchstabe": "c", "schuljahr_id": sj["id"]}).json()
    schueler_ids = [
        client.post("/schueler/", json={"vorname": f"S{i}", "nachname": "X", "klasse_id": kl["id"]}).json()["id"]
        for i in range(3)
    ]
    sa, las = _sa_mit_aufgaben(client, kl["id"], [100.0])
    # Noten: 1 (90%), 3 (60%), 6 (10%)
    punkte_pro_schueler = [90.0, 60.0, 10.0]
    eintraege = [
        {"schueler_id": s_id, "leistung_aufgabe_id": las[0]["id"], "erreichte_punkte": p}
        for s_id, p in zip(schueler_ids, punkte_pro_schueler)
    ]
    client.put(f"/schriftliche-leistungen/{sa['id']}/ergebnisse/detailliert", json=eintraege)

    r = client.get(f"/schriftliche-leistungen/{sa['id']}/auswertung")
    data = r.json()
    assert data["notenverteilung"]["1"]["anzahl"] == 1
    assert data["notenverteilung"]["3"]["anzahl"] == 1
    assert data["notenverteilung"]["6"]["anzahl"] == 1
    assert data["klassendurchschnitt"] == round((1 + 3 + 6) / 3, 2)


# --- Kompetenzprofil ---

def test_kompetenzprofil(client, setup):
    """Schüler mit nur Pauschal-Noten → Profil leer, Schnitt korrekt."""
    s_id = setup["schueler"]["id"]
    ln = client.post("/schriftliche-leistungen/", json={
        "klasse_id": setup["klasse"]["id"], "datum": "2026-02-01",
        "titel": "LN", "art": "kleiner_ln", "detailliert": False,
    }).json()
    client.put(f"/schriftliche-leistungen/{ln['id']}/ergebnisse/pauschal", json=[
        {"schueler_id": s_id, "pauschalnote": 2.0},
    ])
    r = client.get(f"/schueler/{s_id}/kompetenzprofil")
    assert r.status_code == 200
    data = r.json()
    assert data["scores"] == []
    assert data["leistungen_mit_daten"] == 0
