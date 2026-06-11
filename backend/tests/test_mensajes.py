"""Tests del router de mensajes (E02 · T02.3.2): happy path + errores + orden."""

import uuid


def _crear_lead(client) -> str:
    return client.post("/leads", json={"origen": "web"}).json()["id"]


def test_listar_mensajes_vacio(client):
    lid = _crear_lead(client)
    r = client.get(f"/leads/{lid}/mensajes")
    assert r.status_code == 200
    assert r.json() == []


def test_crear_y_listar_en_orden(client):
    lid = _crear_lead(client)
    client.post(f"/leads/{lid}/mensajes", json={"rol": "lead", "contenido": "uno"})
    client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "dos"})
    client.post(f"/leads/{lid}/mensajes", json={"rol": "lead", "contenido": "tres"})
    msgs = client.get(f"/leads/{lid}/mensajes").json()
    assert [m["contenido"] for m in msgs] == ["uno", "dos", "tres"]


def test_crear_mensaje_con_metadata(client):
    lid = _crear_lead(client)
    r = client.post(
        f"/leads/{lid}/mensajes",
        json={"rol": "agente", "contenido": "hola", "metadata": {"tokens": 12}},
    )
    assert r.status_code == 201
    assert r.json()["metadata"] == {"tokens": 12}


def test_crear_mensaje_rol_invalido_422(client):
    lid = _crear_lead(client)
    r = client.post(f"/leads/{lid}/mensajes", json={"rol": "robot", "contenido": "x"})
    assert r.status_code == 422


def test_crear_mensaje_contenido_vacio_422(client):
    lid = _crear_lead(client)
    r = client.post(f"/leads/{lid}/mensajes", json={"rol": "lead", "contenido": ""})
    assert r.status_code == 422


def test_crear_mensaje_lead_inexistente_404(client):
    r = client.post(f"/leads/{uuid.uuid4()}/mensajes", json={"rol": "lead", "contenido": "x"})
    assert r.status_code == 404


def test_listar_mensajes_lead_inexistente_404(client):
    assert client.get(f"/leads/{uuid.uuid4()}/mensajes").status_code == 404
