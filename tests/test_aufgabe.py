import pytest


@pytest.fixture
def aufgabe(client):
    return client.post("/aufgaben/", json={
        "titel": "Quadratische Gleichungen",
        "aufgabenstellung": "Löse die quadratische Funktion f(x) = x² - 4",
        "loesung": "x = ±2",
        "max_punkte": 10.0,
        "afb_niveau": "AFB_II",
        "tags": "quadratische Funktion, Parabel, Nullstellen",
    }).json()


@pytest.fixture
def kompetenzen(client):
    # Kompetenzen werden durch Migration geseedet – in Tests via conftest SQLite erstellt
    # Wir legen sie manuell an, da SQLite keine Migration ausführt
    from tests.conftest import TestingSessionLocal
    from app.models.kompetenz import Kompetenz
    db = TestingSessionLocal()
    for k, b in [
        ("K1", "Mathematisch argumentieren"),
        ("K2", "Probleme mathematisch lösen"),
        ("K3", "Mathematisch modellieren"),
    ]:
        db.add(Kompetenz(kuerzel=k, bezeichnung=b))
    db.commit()
    db.close()
    return client.get("/kompetenzen/").json()


# --- CRUD ---

def test_create_aufgabe(client, aufgabe):
    assert aufgabe["titel"] == "Quadratische Gleichungen"
    assert aufgabe["max_punkte"] == 10.0
    assert aufgabe["afb_niveau"] == "AFB_II"


def test_get_aufgabe(client, aufgabe):
    r = client.get(f"/aufgaben/{aufgabe['id']}")
    assert r.status_code == 200


def test_update_aufgabe(client, aufgabe):
    r = client.patch(f"/aufgaben/{aufgabe['id']}", json={"max_punkte": 12.0})
    assert r.status_code == 200
    assert r.json()["max_punkte"] == 12.0


def test_delete_aufgabe(client, aufgabe):
    assert client.delete(f"/aufgaben/{aufgabe['id']}").status_code == 204
    assert client.get(f"/aufgaben/{aufgabe['id']}").status_code == 404


# --- Suche ---

def test_suche_nach_aufgabenstellung(client, aufgabe):
    r = client.get("/aufgaben/?suche=quadratische")
    assert r.status_code == 200
    assert any(a["id"] == aufgabe["id"] for a in r.json())


def test_suche_nach_tag(client, aufgabe):
    r = client.get("/aufgaben/?suche=Parabel")
    assert any(a["id"] == aufgabe["id"] for a in r.json())


def test_suche_kein_treffer(client, aufgabe):
    r = client.get("/aufgaben/?suche=Integralrechnung")
    assert r.json() == []


def test_suche_nach_afb(client, aufgabe):
    r = client.get("/aufgaben/?afb=AFB_II")
    assert any(a["id"] == aufgabe["id"] for a in r.json())
    r2 = client.get("/aufgaben/?afb=AFB_III")
    assert not any(a["id"] == aufgabe["id"] for a in r2.json())


# --- Kompetenz-Zuweisung ---

def test_set_kompetenzen_gültig(client, aufgabe, kompetenzen):
    k1_id = next(k["id"] for k in kompetenzen if k["kuerzel"] == "K1")
    k2_id = next(k["id"] for k in kompetenzen if k["kuerzel"] == "K2")
    r = client.put(f"/aufgaben/{aufgabe['id']}/kompetenzen", json=[
        {"kompetenz_id": k1_id, "gewichtung": 0.6},
        {"kompetenz_id": k2_id, "gewichtung": 0.4},
    ])
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_set_kompetenzen_summe_falsch(client, aufgabe, kompetenzen):
    k1_id = kompetenzen[0]["id"]
    r = client.put(f"/aufgaben/{aufgabe['id']}/kompetenzen", json=[
        {"kompetenz_id": k1_id, "gewichtung": 0.5},
    ])
    assert r.status_code == 400


def test_set_kompetenzen_leer(client, aufgabe):
    r = client.put(f"/aufgaben/{aufgabe['id']}/kompetenzen", json=[])
    assert r.status_code == 200
    assert r.json() == []
