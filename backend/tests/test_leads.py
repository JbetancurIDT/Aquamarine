"""Tests del router de leads (E02 · T02.3.1): happy path + errores + efectos."""

import uuid

from app.models.evento import Evento
from app.models.lead import Lead
from app.models.tenant import Tenant


def test_crear_lead_defaults_y_evento(client, db):
    r = client.post("/leads", json={"origen": "web", "nombre": "Ana"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origen"] == "web"
    assert body["estado"] == "nuevo"       # defaults de negocio
    assert body["temperatura"] == "frio"
    assert body["score"] == 0
    assert body["nombre"] == "Ana"
    assert body["perfil"] == {}
    assert body["id"]
    # Efecto: se emitió el evento `lead_creado`.
    eventos = db.query(Evento).filter(Evento.tipo == "lead_creado").all()
    assert len(eventos) == 1
    assert eventos[0].payload == {"origen": "web"}


def test_crear_lead_origen_invalido_422(client):
    r = client.post("/leads", json={"origen": "telegram"})
    assert r.status_code == 422


def test_listar_leads_vacio(client):
    r = client.get("/leads")
    assert r.status_code == 200
    assert r.json() == []


def test_listar_y_filtrar(client):
    client.post("/leads", json={"origen": "web"})
    client.post("/leads", json={"origen": "meta"})
    client.post("/leads", json={"origen": "web"})

    assert len(client.get("/leads").json()) == 3

    web = client.get("/leads", params={"origen": "web"}).json()
    assert len(web) == 2 and all(le["origen"] == "web" for le in web)
    assert len(client.get("/leads", params={"origen": "meta"}).json()) == 1

    # Todos arrancan frio/nuevo.
    assert len(client.get("/leads", params={"temperatura": "frio"}).json()) == 3
    assert len(client.get("/leads", params={"temperatura": "caliente"}).json()) == 0
    assert len(client.get("/leads", params={"estado": "nuevo"}).json()) == 3
    assert len(client.get("/leads", params={"estado": "calificado"}).json()) == 0


def test_filtro_invalido_422(client):
    assert client.get("/leads", params={"estado": "inexistente"}).status_code == 422


def test_detalle_incluye_mensajes(client):
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    client.post(f"/leads/{lid}/mensajes", json={"rol": "lead", "contenido": "Hola"})
    client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "Buenas"})
    r = client.get(f"/leads/{lid}")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == lid
    assert [m["rol"] for m in body["mensajes"]] == ["lead", "agente"]


def test_detalle_404(client):
    assert client.get(f"/leads/{uuid.uuid4()}").status_code == 404


def test_detalle_id_malformado_422(client):
    assert client.get("/leads/no-es-uuid").status_code == 422


def test_cambiar_estado_y_evento(client, db):
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.patch(f"/leads/{lid}/estado", json={"estado": "contactado"})
    assert r.status_code == 200
    assert r.json()["estado"] == "contactado"
    eventos = db.query(Evento).filter(Evento.tipo == "estado_cambiado").all()
    assert len(eventos) == 1
    assert eventos[0].payload == {"anterior": "nuevo", "nuevo": "contactado"}


def test_cambiar_estado_invalido_422(client):
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    assert client.patch(f"/leads/{lid}/estado", json={"estado": "volando"}).status_code == 422


def test_cambiar_estado_lead_inexistente_404(client):
    r = client.patch(f"/leads/{uuid.uuid4()}/estado", json={"estado": "contactado"})
    assert r.status_code == 404


def test_aislamiento_multitenant(client, db):
    """Un tenant no ve ni cuenta ni puede leer los leads de otro (promesa central de E02)."""
    otro = Tenant(nombre="Otro Tenant")
    db.add(otro)
    db.commit()
    db.refresh(otro)
    ajeno = Lead(tenant_id=otro.id, origen="web")
    db.add(ajeno)
    db.commit()
    db.refresh(ajeno)

    mio = client.post("/leads", json={"origen": "web"}).json()
    # El listado del tenant actual solo trae el lead propio.
    assert [le["id"] for le in client.get("/leads").json()] == [mio["id"]]
    # Las métricas no cuentan el lead ajeno.
    assert client.get("/metrics/overview").json()["total_leads"] == 1
    # No hay fuga por detalle directo.
    assert client.get(f"/leads/{ajeno.id}").status_code == 404
