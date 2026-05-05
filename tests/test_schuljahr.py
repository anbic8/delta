def test_create_schuljahr(client):
    r = client.post("/schuljahre/", json={"name": "2025/26"})
    assert r.status_code == 201
    assert r.json()["name"] == "2025/26"


def test_get_schuljahr(client):
    sj_id = client.post("/schuljahre/", json={"name": "2025/26"}).json()["id"]
    r = client.get(f"/schuljahre/{sj_id}")
    assert r.status_code == 200
    assert r.json()["name"] == "2025/26"


def test_list_schuljahre(client):
    client.post("/schuljahre/", json={"name": "2024/25"})
    client.post("/schuljahre/", json={"name": "2025/26"})
    r = client.get("/schuljahre/")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_update_schuljahr(client):
    sj_id = client.post("/schuljahre/", json={"name": "2025/26"}).json()["id"]
    r = client.patch(f"/schuljahre/{sj_id}", json={"name": "2026/27"})
    assert r.status_code == 200
    assert r.json()["name"] == "2026/27"


def test_delete_schuljahr(client):
    sj_id = client.post("/schuljahre/", json={"name": "2025/26"}).json()["id"]
    assert client.delete(f"/schuljahre/{sj_id}").status_code == 204
    assert client.get(f"/schuljahre/{sj_id}").status_code == 404


def test_create_schuljahr_ungültiges_format(client):
    assert client.post("/schuljahre/", json={"name": "2025-26"}).status_code == 422


def test_get_schuljahr_nicht_gefunden(client):
    assert client.get("/schuljahre/999").status_code == 404
