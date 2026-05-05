import pytest


@pytest.fixture
def klasse(client):
    sj = client.post("/schuljahre/", json={"name": "2025/26"}).json()
    return client.post("/klassen/", json={"jahrgangsstufe": 8, "buchstabe": "a", "schuljahr_id": sj["id"]}).json()


@pytest.fixture
def aufgabe_factory(client):
    def _make(titel="Aufgabe", punkte=10.0, afb="AFB_I"):
        return client.post("/aufgaben/", json={
            "titel": titel, "aufgabenstellung": f"Text zu {titel}",
            "max_punkte": punkte, "afb_niveau": afb,
        }).json()
    return _make


# --- SchriftlicheLeistung CRUD ---

def test_create_sa(client, klasse):
    r = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA 1", "art": "schulaufgabe", "detailliert": True,
    })
    assert r.status_code == 201
    data = r.json()
    assert data["art"] == "schulaufgabe"
    assert data["detailliert"] is True


def test_create_kleiner_ln_detailliert(client, klasse):
    r = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-02-01",
        "titel": "Kleiner LN 1", "art": "kleiner_ln", "detailliert": True,
    })
    assert r.status_code == 201


def test_create_kleiner_ln_pauschal(client, klasse):
    r = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-02-15",
        "titel": "Kleiner LN pauschal", "art": "kleiner_ln", "detailliert": False,
    })
    assert r.status_code == 201
    assert r.json()["detailliert"] is False


def test_sa_muss_detailliert_sein(client, klasse):
    r = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA falsch", "art": "schulaufgabe", "detailliert": False,
    })
    assert r.status_code == 422


def test_list_leistungen_filter(client, klasse):
    client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA 1", "art": "schulaufgabe", "detailliert": True,
    })
    r = client.get(f"/schriftliche-leistungen/?klasse_id={klasse['id']}")
    assert len(r.json()) == 1


# --- Aufgaben zuordnen ---

def test_aufgabe_zu_sa_hinzufügen(client, klasse, aufgabe_factory):
    sa = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA 1", "art": "schulaufgabe", "detailliert": True,
    }).json()
    aufgabe = aufgabe_factory("Aufgabe 1")
    r = client.post(f"/schriftliche-leistungen/{sa['id']}/aufgaben", json={
        "aufgabe_id": aufgabe["id"], "aufgabennummer": "1", "reihenfolge": 1,
    })
    assert r.status_code == 201
    assert r.json()["aufgabennummer"] == "1"


def test_sa_mit_6_aufgaben(client, klasse, aufgabe_factory):
    sa = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA 1", "art": "schulaufgabe", "detailliert": True,
    }).json()
    for i in range(1, 7):
        aufgabe = aufgabe_factory(f"Aufgabe {i}", punkte=5.0)
        client.post(f"/schriftliche-leistungen/{sa['id']}/aufgaben", json={
            "aufgabe_id": aufgabe["id"], "aufgabennummer": str(i), "reihenfolge": i,
        })
    r = client.get(f"/schriftliche-leistungen/{sa['id']}/aufgaben")
    assert len(r.json()) == 6


def test_kleiner_ln_mit_2_aufgaben(client, klasse, aufgabe_factory):
    ln = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-02-01",
        "titel": "LN 1", "art": "kleiner_ln", "detailliert": True,
    }).json()
    for i in range(1, 3):
        aufgabe = aufgabe_factory(f"Aufgabe {i}")
        client.post(f"/schriftliche-leistungen/{ln['id']}/aufgaben", json={
            "aufgabe_id": aufgabe["id"], "aufgabennummer": str(i), "reihenfolge": i,
        })
    r = client.get(f"/schriftliche-leistungen/{ln['id']}/aufgaben")
    assert len(r.json()) == 2


def test_pauschal_ln_keine_aufgaben_erlaubt(client, klasse, aufgabe_factory):
    ln = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-02-15",
        "titel": "LN pauschal", "art": "kleiner_ln", "detailliert": False,
    }).json()
    aufgabe = aufgabe_factory()
    r = client.post(f"/schriftliche-leistungen/{ln['id']}/aufgaben", json={
        "aufgabe_id": aufgabe["id"], "aufgabennummer": "1", "reihenfolge": 1,
    })
    assert r.status_code == 400


def test_aufgabe_entfernen(client, klasse, aufgabe_factory):
    sa = client.post("/schriftliche-leistungen/", json={
        "klasse_id": klasse["id"], "datum": "2026-03-01",
        "titel": "SA 1", "art": "schulaufgabe", "detailliert": True,
    }).json()
    aufgabe = aufgabe_factory()
    la = client.post(f"/schriftliche-leistungen/{sa['id']}/aufgaben", json={
        "aufgabe_id": aufgabe["id"], "aufgabennummer": "1", "reihenfolge": 1,
    }).json()
    assert client.delete(f"/schriftliche-leistungen/{sa['id']}/aufgaben/{la['id']}").status_code == 204
    assert client.get(f"/schriftliche-leistungen/{sa['id']}/aufgaben").json() == []
