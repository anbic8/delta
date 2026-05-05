import pytest


@pytest.fixture
def schueler_6er(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    kl = client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()
    return client.post("/schueler/", json={"vorname": "Max", "nachname": "Muster", "klasse_id": kl["id"]}).json()


@pytest.fixture
def schueler_punkte(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    kl = client.post("/klassen/", json={"jahrgangsstufe": 12, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()
    return client.post("/schueler/", json={"vorname": "Anna", "nachname": "Muster", "klasse_id": kl["id"]}).json()


# --- CRUD ---

def test_create_note_sechserskala(client, schueler_6er):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 2.0, "gewichtung": 1.0,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["note"] == 2.0
    assert data["notensystem"] == "sechserskala"
    assert data["gewichtung"] == 1.0


def test_create_note_punkte(client, schueler_punkte):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_punkte["id"], "datum": "2026-01-15", "note": 11.0, "gewichtung": 1.0,
    })
    assert r.status_code == 201
    assert r.json()["notensystem"] == "punkte"


def test_soft_delete_note(client, schueler_6er):
    n_id = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 3.0, "gewichtung": 1.0,
    }).json()["id"]
    assert client.delete(f"/muendliche-noten/{n_id}").status_code == 204
    r = client.get(f"/muendliche-noten/{n_id}")
    assert r.json()["geloescht_am"] is not None
    assert len(client.get(f"/muendliche-noten/?schueler_id={schueler_6er['id']}").json()) == 0


def test_update_note(client, schueler_6er):
    n_id = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 3.0, "gewichtung": 1.0,
    }).json()["id"]
    r = client.patch(f"/muendliche-noten/{n_id}", json={"note": 2.0})
    assert r.status_code == 200
    assert r.json()["note"] == 2.0


# --- Validierung ---

def test_note_zu_hoch_sechserskala(client, schueler_6er):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 7.0, "gewichtung": 1.0,
    })
    assert r.status_code == 422


def test_note_zu_niedrig_sechserskala(client, schueler_6er):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 0.0, "gewichtung": 1.0,
    })
    assert r.status_code == 422


def test_note_zu_hoch_punkte(client, schueler_punkte):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_punkte["id"], "datum": "2026-01-15", "note": 16.0, "gewichtung": 1.0,
    })
    assert r.status_code == 422


def test_ungültige_gewichtung(client, schueler_6er):
    r = client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 3.0, "gewichtung": 1.5,
    })
    assert r.status_code == 422


# --- Schnitt-Berechnung ---

def test_schnitt_keine_noten(client, schueler_6er):
    r = client.get(f"/schueler/{schueler_6er['id']}/schnitt")
    assert r.status_code == 200
    assert r.json()["schnitt_kleine_ln"] is None
    assert r.json()["gesamtschnitt"] is None


def test_schnitt_eine_note(client, schueler_6er):
    client.post("/muendliche-noten/", json={
        "schueler_id": schueler_6er["id"], "datum": "2026-01-15", "note": 3.0, "gewichtung": 1.0,
    })
    r = client.get(f"/schueler/{schueler_6er['id']}/schnitt")
    assert r.json()["schnitt_kleine_ln"] == 3.0


def test_schnitt_gemischte_gewichtungen(client, schueler_6er):
    s_id = schueler_6er["id"]
    # Note 2.0 einfach + Note 4.0 doppelt → (2*1 + 4*2) / (1+2) = 10/3 ≈ 3.33
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-01-10", "note": 2.0, "gewichtung": 1.0})
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-02-10", "note": 4.0, "gewichtung": 2.0})
    r = client.get(f"/schueler/{s_id}/schnitt")
    assert r.json()["schnitt_kleine_ln"] == round(10 / 3, 2)


def test_schnitt_gelöschte_noten_ignoriert(client, schueler_6er):
    s_id = schueler_6er["id"]
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-01-10", "note": 1.0, "gewichtung": 1.0})
    n_id = client.post("/muendliche-noten/", json={
        "schueler_id": s_id, "datum": "2026-02-10", "note": 6.0, "gewichtung": 1.0,
    }).json()["id"]
    client.delete(f"/muendliche-noten/{n_id}")
    r = client.get(f"/schueler/{s_id}/schnitt")
    assert r.json()["schnitt_kleine_ln"] == 1.0


def test_schnitt_halbe_gewichtung(client, schueler_6er):
    s_id = schueler_6er["id"]
    # (1.0 * 1.0 + 3.0 * 0.5) / (1.0 + 0.5) = 2.5 / 1.5 ≈ 1.67
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-01-10", "note": 1.0, "gewichtung": 1.0})
    client.post("/muendliche-noten/", json={"schueler_id": s_id, "datum": "2026-02-10", "note": 3.0, "gewichtung": 0.5})
    r = client.get(f"/schueler/{s_id}/schnitt")
    assert r.json()["schnitt_kleine_ln"] == round(2.5 / 1.5, 2)
