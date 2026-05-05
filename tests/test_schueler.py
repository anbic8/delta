import pytest


@pytest.fixture
def klasse(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    return client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()


def test_create_schueler(client, klasse):
    r = client.post("/schueler/", json={"vorname": "Max", "nachname": "Mustermann", "klasse_id": klasse["id"]})
    assert r.status_code == 201
    data = r.json()
    assert data["vorname"] == "Max"
    assert data["pseudonym_id"] is not None
    assert len(data["pseudonym_id"]) == 8


def test_drei_schueler_anlegen_und_liste(client, klasse):
    for vorname, nachname in [("Anna", "Schmidt"), ("Ben", "Müller"), ("Clara", "Weber")]:
        client.post("/schueler/", json={"vorname": vorname, "nachname": nachname, "klasse_id": klasse["id"]})
    r = client.get(f"/klassen/{klasse['id']}/schueler")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_pseudonym_id_eindeutig(client, klasse):
    ids = {
        client.post("/schueler/", json={"vorname": f"S{i}", "nachname": "Test", "klasse_id": klasse["id"]}).json()["pseudonym_id"]
        for i in range(5)
    }
    assert len(ids) == 5


def test_soft_delete(client, klasse):
    s_id = client.post("/schueler/", json={"vorname": "Max", "nachname": "Muster", "klasse_id": klasse["id"]}).json()["id"]
    assert client.delete(f"/schueler/{s_id}").status_code == 204
    # Schüler noch direkt abrufbar
    r = client.get(f"/schueler/{s_id}")
    assert r.status_code == 200
    assert r.json()["geloescht_am"] is not None
    # Nicht mehr in Klassenliste
    assert len(client.get(f"/klassen/{klasse['id']}/schueler").json()) == 0


def test_update_schueler(client, klasse):
    s_id = client.post("/schueler/", json={"vorname": "Max", "nachname": "Muster", "klasse_id": klasse["id"]}).json()["id"]
    r = client.patch(f"/schueler/{s_id}", json={"vorname": "Maximilian"})
    assert r.status_code == 200
    assert r.json()["vorname"] == "Maximilian"


def test_create_schueler_klasse_nicht_gefunden(client):
    r = client.post("/schueler/", json={"vorname": "Max", "nachname": "Muster", "klasse_id": 999})
    assert r.status_code == 404
