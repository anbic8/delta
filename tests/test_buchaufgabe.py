import pytest
from tests.conftest import TestingSessionLocal
from app.models.kompetenz import Kompetenz

BEISPIEL_CSV = """\
Buch,Kapitel,Seite,Aufgabennummer,Beschreibung,AFB,Wichtigkeit,Kompetenz
Lambacher Schweizer 9 Bayern,1 - Potenzen,14,1,Potenzen berechnen,AFB_I,2,K5
Lambacher Schweizer 9 Bayern,1 - Potenzen,16,2,Wurzeln vereinfachen,AFB_I,3,K5
Lambacher Schweizer 9 Bayern,2 - Gleichungen,32,1,Lineare Gleichungen,AFB_I,2,K2
Lambacher Schweizer 9 Bayern,2 - Gleichungen,34,5,Gleichungssysteme,AFB_II,3,K2
Lambacher Schweizer 10 Bayern,1 - Exponentialfkt,12,1,Exponentialfunktionen,AFB_I,3,K4
"""


@pytest.fixture(autouse=True)
def seed_kompetenzen(client):
    db = TestingSessionLocal()
    for k, b in [("K1", "Argumentieren"), ("K2", "Problemlösen"), ("K3", "Modellieren"),
                 ("K4", "Darstellen"), ("K5", "Technisch"), ("K6", "Kommunizieren")]:
        db.add(Kompetenz(kuerzel=k, bezeichnung=b))
    db.commit()
    db.close()


def _import(client, csv_text=BEISPIEL_CSV):
    return client.post(
        "/buchaufgaben/import",
        files={"file": ("test.csv", csv_text.encode(), "text/csv")},
    ).json()


# --- Import ---

def test_import_happy_path(client):
    r = _import(client)
    assert r["importiert"] == 5
    assert r["aktualisiert"] == 0
    assert r["fehler"] == 0


def test_import_idempotent(client):
    _import(client)
    r = _import(client)
    assert r["importiert"] == 0
    assert r["aktualisiert"] == 5
    assert r["fehler"] == 0


def test_import_50_aufgaben(client):
    import os
    csv_path = os.path.join(os.path.dirname(__file__), "..", "beispiel_buchaufgaben.csv")
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            csv_text = f.read()
        r = client.post("/buchaufgaben/import", files={"file": ("b.csv", csv_text.encode(), "text/csv")}).json()
        assert r["importiert"] == 50
        assert r["fehler"] == 0


def test_import_zweiter_lauf_keine_duplikate(client):
    import os
    csv_path = os.path.join(os.path.dirname(__file__), "..", "beispiel_buchaufgaben.csv")
    if os.path.exists(csv_path):
        with open(csv_path, encoding="utf-8") as f:
            csv_text = f.read()
        client.post("/buchaufgaben/import", files={"file": ("b.csv", csv_text.encode(), "text/csv")})
        r = client.post("/buchaufgaben/import", files={"file": ("b.csv", csv_text.encode(), "text/csv")}).json()
        assert r["importiert"] == 0
        assert r["aktualisiert"] == 50


# --- Filter ---

def test_filter_buch(client):
    _import(client)
    r = client.get("/buchaufgaben/?buch=Lambacher+Schweizer+9+Bayern").json()
    assert len(r) == 4
    assert all("9 Bayern" in b["buch"] for b in r)


def test_filter_afb(client):
    _import(client)
    r = client.get("/buchaufgaben/?afb=AFB_II").json()
    assert len(r) == 1
    assert r[0]["afb_niveau"] == "AFB_II"


def test_filter_kompetenz(client):
    _import(client)
    k2 = TestingSessionLocal().query(Kompetenz).filter(Kompetenz.kuerzel == "K2").first()
    if k2:
        r = client.get(f"/buchaufgaben/?kompetenz_id={k2.id}").json()
        assert len(r) == 2


def test_filter_kombiniert(client):
    _import(client)
    r = client.get("/buchaufgaben/?buch=Lambacher+Schweizer+9+Bayern&afb=AFB_II").json()
    assert len(r) == 1


# --- CRUD ---

def test_get_buchaufgabe(client):
    _import(client)
    alle = client.get("/buchaufgaben/").json()
    r = client.get(f"/buchaufgaben/{alle[0]['id']}").json()
    assert r["buch"] == alle[0]["buch"]


def test_delete_buchaufgabe(client):
    _import(client)
    alle = client.get("/buchaufgaben/").json()
    ba_id = alle[0]["id"]
    assert client.delete(f"/buchaufgaben/{ba_id}").status_code == 204
    assert client.get(f"/buchaufgaben/{ba_id}").status_code == 404
