import pytest


@pytest.fixture
def klasse(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    return client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()


@pytest.fixture
def sa_mit_aufgaben(client, klasse):
    sa = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01", "titel": "SA 1",
        "art": "schulaufgabe", "detailliert": True,
    }).json()
    for nr, p in [("1", 10.0), ("2", 10.0), ("3", 5.0)]:
        a = client.post("/aufgaben/", json={"titel": f"Aufgabe {nr}", "aufgabenstellung": "x", "max_punkte": p, "afb_niveau": "AFB_I"}).json()
        client.post(f"/schriftliche-leistungen/{sa['id']}/aufgaben", json={"aufgabe_id": a["id"], "aufgabennummer": nr, "reihenfolge": int(nr)})
    return sa


# ── Schüler-Import ────────────────────────────────────────────

def test_schueler_import_happy_path(client, klasse):
    csv = "Nachname,Vorname\nMuster,Max\nSchmidt,Anna\nMüller,Klaus"
    r = client.post(
        f"/ui/klassen/{klasse['id']}/schueler-import",
        files={"file": ("s.csv", csv.encode("utf-8"), "text/csv")},
        follow_redirects=False,
    )
    assert r.status_code == 303
    schueler = client.get(f"/klassen/{klasse['id']}/schueler").json()
    assert len(schueler) == 3


def test_schueler_import_ohne_header(client, klasse):
    csv = "Braun,Lisa\nHuber,Thomas"
    client.post(
        f"/ui/klassen/{klasse['id']}/schueler-import",
        files={"file": ("s.csv", csv.encode(), "text/csv")},
    )
    assert len(client.get(f"/klassen/{klasse['id']}/schueler").json()) == 2


def test_schueler_import_duplikat_uebersprungen(client, klasse):
    csv1 = "Muster,Max\nSchmidt,Anna"
    client.post(f"/ui/klassen/{klasse['id']}/schueler-import", files={"file": ("s.csv", csv1.encode(), "text/csv")})
    csv2 = "Muster,Max\nWeber,Clara"
    client.post(f"/ui/klassen/{klasse['id']}/schueler-import", files={"file": ("s.csv", csv2.encode(), "text/csv")})
    schueler = client.get(f"/klassen/{klasse['id']}/schueler").json()
    assert len(schueler) == 3  # Muster, Schmidt, Weber – kein Duplikat


def test_schueler_import_bom_utf8(client, klasse):
    csv = "﻿Nachname,Vorname\nLange,Peter"  # BOM
    client.post(f"/ui/klassen/{klasse['id']}/schueler-import", files={"file": ("s.csv", csv.encode("utf-8-sig"), "text/csv")})
    assert len(client.get(f"/klassen/{klasse['id']}/schueler").json()) == 1


# ── Punkte-Import ─────────────────────────────────────────────

def _schueler_anlegen(client, klasse_id, namen):
    ids = []
    for vorname, nachname in namen:
        s = client.post("/schueler/", json={"vorname": vorname, "nachname": nachname, "klasse_id": klasse_id}).json()
        ids.append(s)
    return ids


def test_punkte_import_vorschau(client, klasse, sa_mit_aufgaben):
    _schueler_anlegen(client, klasse["id"], [("Max", "Muster"), ("Anna", "Schmidt")])
    csv = "Nachname,Vorname,1,2,3\nMuster,Max,8,7,4\nSchmidt,Anna,9,8,5"
    r = client.post(
        f"/ui/schriftliche-leistungen/{sa_mit_aufgaben['id']}/punkte-import",
        files={"file": ("p.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "Muster" in r.text
    assert "Schmidt" in r.text
    assert "s_" in r.text  # hidden inputs vorhanden


def test_punkte_import_nicht_gefunden(client, klasse, sa_mit_aufgaben):
    _schueler_anlegen(client, klasse["id"], [("Max", "Muster")])
    csv = "Nachname,Vorname,1,2,3\nMuster,Max,8,7,4\nUnbekannt,Person,5,5,3"
    r = client.post(
        f"/ui/schriftliche-leistungen/{sa_mit_aufgaben['id']}/punkte-import",
        files={"file": ("p.csv", csv.encode(), "text/csv")},
        follow_redirects=False,
    )
    assert r.status_code == 200
    assert "nicht gefunden" in r.text.lower()
    assert "Unbekannt" in r.text


def test_punkte_import_bestaetigen(client, klasse, sa_mit_aufgaben):
    schueler = _schueler_anlegen(client, klasse["id"], [("Max", "Muster")])[0]
    las = client.get(f"/schriftliche-leistungen/{sa_mit_aufgaben['id']}/aufgaben").json()
    la_by_nr = {la["aufgabennummer"]: la for la in las}

    r = client.post(
        f"/ui/schriftliche-leistungen/{sa_mit_aufgaben['id']}/punkte-import/bestaetigen",
        data={
            f"s_{schueler['id']}_{la_by_nr['1']['id']}": "8.0",
            f"s_{schueler['id']}_{la_by_nr['2']['id']}": "7.0",
            f"s_{schueler['id']}_{la_by_nr['3']['id']}": "4.0",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    auswertung = client.get(f"/schriftliche-leistungen/{sa_mit_aufgaben['id']}/auswertung").json()
    zeile = next(z for z in auswertung["schueler"] if z["schueler_id"] == schueler["id"])
    assert zeile["summe"] == 19.0


def test_punkte_import_ueberschreibt(client, klasse, sa_mit_aufgaben):
    schueler = _schueler_anlegen(client, klasse["id"], [("Max", "Muster")])[0]
    las = client.get(f"/schriftliche-leistungen/{sa_mit_aufgaben['id']}/aufgaben").json()
    la1_id = las[0]["id"]

    client.post(
        f"/ui/schriftliche-leistungen/{sa_mit_aufgaben['id']}/punkte-import/bestaetigen",
        data={f"s_{schueler['id']}_{la1_id}": "5.0"},
    )
    client.post(
        f"/ui/schriftliche-leistungen/{sa_mit_aufgaben['id']}/punkte-import/bestaetigen",
        data={f"s_{schueler['id']}_{la1_id}": "9.0"},
    )
    from app.models.schueler_ergebnis import SchuelerErgebnis
    from tests.conftest import TestingSessionLocal
    db = TestingSessionLocal()
    e = db.query(SchuelerErgebnis).filter(
        SchuelerErgebnis.schueler_id == schueler["id"],
        SchuelerErgebnis.leistung_aufgabe_id == la1_id,
    ).first()
    db.close()
    assert e.erreichte_punkte == 9.0
