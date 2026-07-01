"""Tests del router de leads (E02 · T02.3.1): happy path + errores + efectos."""

import uuid

from app.models.evento import Evento
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.schemas.lead import LeadCreate
from app.services import lead_service


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


def test_asignar_asesor_happy(client, db):
    """PATCH /leads/{id}/asesor asigna asesor y emite evento asesor_asignado."""
    from app.models.asesor import Asesor
    from app.models.evento import Evento
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Ana Gómez", disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.patch(f"/leads/{lid}/asesor", json={"asesor_id": str(asesor.id)})
    assert r.status_code == 200
    assert r.json()["asesor_id"] == str(asesor.id)
    ev = db.query(Evento).filter(Evento.tipo == "asesor_asignado").first()
    assert ev is not None
    assert ev.payload["asesor_id"] == str(asesor.id)
    assert ev.payload["anterior"] is None


def test_asignar_asesor_desasignar(client, db):
    """Pasar asesor_id=null desasigna el asesor."""
    from app.models.asesor import Asesor
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Luis Pérez", disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    client.patch(f"/leads/{lid}/asesor", json={"asesor_id": str(asesor.id)})
    r = client.patch(f"/leads/{lid}/asesor", json={"asesor_id": None})
    assert r.status_code == 200
    assert r.json()["asesor_id"] is None


def test_asignar_asesor_lead_404(client):
    """Lead inexistente → 404."""
    r = client.patch(f"/leads/{uuid.uuid4()}/asesor", json={"asesor_id": str(uuid.uuid4())})
    assert r.status_code == 404


def test_asignar_asesor_asesor_404(client, db):
    """Asesor inexistente → 404."""
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.patch(f"/leads/{lid}/asesor", json={"asesor_id": str(uuid.uuid4())})
    assert r.status_code == 404


def test_asignar_asesor_otro_tenant_404(client, db):
    """Asesor de otro tenant → 404 (aislamiento)."""
    from app.models.asesor import Asesor
    otro = Tenant(nombre="Otro Tenant Asesor")
    db.add(otro)
    db.commit()
    db.refresh(otro)
    ajeno = Asesor(tenant_id=otro.id, nombre="Asesor Ajeno", disponible=True)
    db.add(ajeno)
    db.commit()
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.patch(f"/leads/{lid}/asesor", json={"asesor_id": str(ajeno.id)})
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


# ---------------------------------------------------------------------------
# E07: GET /leads/en-vivo
# ---------------------------------------------------------------------------

def test_leads_en_vivo_solo_sin_asesor(client, db):
    """Solo aparecen leads calificado/negociando sin asesor."""
    from app.models.asesor import Asesor
    tenant = lead_service.get_or_create_default_tenant(db)

    l_sin = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, l_sin, "calificado")

    asesor = Asesor(tenant_id=tenant.id, nombre="A", disponible=True)
    db.add(asesor)
    db.commit(); db.refresh(asesor)

    l_con = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, l_con, "calificado")
    l_con.asesor_id = asesor.id
    db.commit()

    r = client.get("/leads/en-vivo")
    assert r.status_code == 200
    ids = [x["id"] for x in r.json()]
    assert str(l_sin.id) in ids
    assert str(l_con.id) not in ids


def test_leads_en_vivo_excluye_nuevo(client, db):
    """Leads en estado nuevo NO aparecen en en-vivo."""
    tenant = lead_service.get_or_create_default_tenant(db)
    lead_service.create_lead(db, tenant, LeadCreate(origen="web"))  # estado=nuevo
    r = client.get("/leads/en-vivo")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# E07: POST /leads/{id}/tomar
# ---------------------------------------------------------------------------

def test_tomar_lead_happy(client, db):
    """POST /leads/{id}/tomar apaga IA, mueve a negociando, emite tomado_por_humano."""
    from app.models.asesor import Asesor
    from app.models.evento import Evento
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Lucía", disponible=True)
    db.add(asesor)
    db.commit(); db.refresh(asesor)

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")

    r = client.post(f"/leads/{lead.id}/tomar", json={"asesor_id": str(asesor.id)})
    assert r.status_code == 200
    body = r.json()
    assert body["atendido_por_humano"] is True
    assert body["estado"] == "negociando"
    assert body["asesor_id"] == str(asesor.id)

    ev = db.query(Evento).filter(Evento.tipo == "tomado_por_humano").first()
    assert ev is not None
    assert ev.payload["asesor_id"] == str(asesor.id)


def test_tomar_lead_idempotente(client, db):
    """Tomar un lead ya tomado devuelve 200 sin cambios."""
    from app.models.asesor import Asesor
    from app.models.evento import Evento
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Pedro", disponible=True)
    db.add(asesor)
    db.commit(); db.refresh(asesor)

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    client.post(f"/leads/{lead.id}/tomar", json={"asesor_id": str(asesor.id)})
    client.post(f"/leads/{lead.id}/tomar", json={"asesor_id": str(asesor.id)})

    # Solo debe haber un evento tomado_por_humano
    count = db.query(Evento).filter(Evento.tipo == "tomado_por_humano").count()
    assert count == 1


def test_tomar_lead_404_lead_inexistente(client, db):
    from app.models.asesor import Asesor
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="X", disponible=True)
    db.add(asesor); db.commit(); db.refresh(asesor)
    r = client.post(f"/leads/{uuid.uuid4()}/tomar", json={"asesor_id": str(asesor.id)})
    assert r.status_code == 404


def test_tomar_lead_404_asesor_inexistente(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    r = client.post(f"/leads/{lead.id}/tomar", json={"asesor_id": str(uuid.uuid4())})
    assert r.status_code == 404
