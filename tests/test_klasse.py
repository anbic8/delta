import pytest


@pytest.fixture
def schuljahr(client):
    return client.post("/schuljahre/", json={"name": "2025/26"}).json()


def test_create_klasse_sechserskala(client, schuljahr):
    r = client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": schuljahr["id"]})
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "8a"
    assert data["notensystem"] == "sechserskala"
    assert data["fach"] == "Mathematik"


def test_create_klasse_punkte(client, schuljahr):
    r = client.post("/klassen/", json={"jahrgangsstufe": 12, "buchstabe": "b", "schuljahr_id": schuljahr["id"]})
    assert r.status_code == 201
    assert r.json()["notensystem"] == "punkte"


def test_create_klasse_jahrgangsstufe_ungültig(client, schuljahr):
    r = client.post("/klassen/", json={"jahrgangsstufe": 3, "buchstabe": "a", "schuljahr_id": schuljahr["id"]})
    assert r.status_code == 422


def test_create_klasse_schuljahr_nicht_gefunden(client):
    r = client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": 999})
    assert r.status_code == 404


def test_list_klassen_filter(client, schuljahr):
    client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": schuljahr["id"]})
    client.post("/klassen/", json={"jahrgangsstufe": 9, "buchstabe": "b", "schuljahr_id": schuljahr["id"]})
    r = client.get(f"/klassen/?schuljahr_id={schuljahr['id']}")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_update_klasse_buchstabe(client, schuljahr):
    k_id = client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": schuljahr["id"]}).json()["id"]
    r = client.patch(f"/klassen/{k_id}", json={"buchstabe": "c"})
    assert r.status_code == 200
    assert r.json()["name"] == "8c"


def test_get_klasse_nicht_gefunden(client):
    assert client.get("/klassen/999").status_code == 404
