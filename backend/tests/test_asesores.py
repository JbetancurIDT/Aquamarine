"""Tests del router de asesores (E04/E05): happy path + 404 + aislamiento por tenant."""

import uuid

from app.models.asesor import Asesor
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _crear_asesor(db, tenant, nombre: str = "Carlos López") -> Asesor:
    asesor = Asesor(tenant_id=tenant.id, nombre=nombre, disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)
    return asesor


# ---------------------------------------------------------------------------
# GET /asesores
# ---------------------------------------------------------------------------

def test_listar_asesores_vacio(client):
    r = client.get("/asesores")
    assert r.status_code == 200
    assert r.json() == []


def test_listar_asesores(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    _crear_asesor(db, tenant, "Ana Torres")
    _crear_asesor(db, tenant, "Luis García")
    r = client.get("/asesores")
    assert r.status_code == 200
    nombres = [a["nombre"] for a in r.json()]
    assert "Ana Torres" in nombres
    assert "Luis García" in nombres


def test_asesor_tiene_campos_esperados(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    _crear_asesor(db, tenant)
    asesor = client.get("/asesores").json()[0]
    assert {"id", "nombre", "disponible"} <= asesor.keys()


# ---------------------------------------------------------------------------
# GET /asesores/{id}/leads
# ---------------------------------------------------------------------------

def test_leads_del_asesor_404_inexistente(client):
    r = client.get(f"/asesores/{uuid.uuid4()}/leads")
    assert r.status_code == 404


def test_leads_del_asesor_vacio(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    r = client.get(f"/asesores/{asesor.id}/leads")
    assert r.status_code == 200
    assert r.json() == []


def test_leads_del_asesor_con_leads(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead.asesor_id = asesor.id
    db.commit()
    r = client.get(f"/asesores/{asesor.id}/leads")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["id"] == str(lead.id)


def test_leads_del_asesor_orden_descendente(client, db):
    """El lead más reciente aparece primero."""
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    l1 = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    l2 = lead_service.create_lead(db, tenant, LeadCreate(origen="meta"))
    for lead in [l1, l2]:
        lead.asesor_id = asesor.id
    db.commit()
    ids = [b["id"] for b in client.get(f"/asesores/{asesor.id}/leads").json()]
    assert ids[0] == str(l2.id)  # más reciente primero


# ---------------------------------------------------------------------------
# GET /asesores/{id}/notificaciones
# ---------------------------------------------------------------------------

def test_notificaciones_asesor_404(client):
    r = client.get(f"/asesores/{uuid.uuid4()}/notificaciones")
    assert r.status_code == 404


def test_notificaciones_asesor_vacio(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    r = client.get(f"/asesores/{asesor.id}/notificaciones")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# Aislamiento multitenant
# ---------------------------------------------------------------------------

def test_aislamiento_listado_asesores(client, db):
    """El tenant actual no ve los asesores de otro tenant."""
    otro = Tenant(nombre="Otro Tenant")
    db.add(otro)
    db.commit()
    db.refresh(otro)
    ajeno = Asesor(tenant_id=otro.id, nombre="Asesor Ajeno", disponible=True)
    db.add(ajeno)
    db.commit()
    ids = [a["id"] for a in client.get("/asesores").json()]
    assert str(ajeno.id) not in ids


def test_aislamiento_leads_del_asesor(client, db):
    """No se puede consultar leads de un asesor de otro tenant."""
    otro = Tenant(nombre="Otro Tenant B")
    db.add(otro)
    db.commit()
    db.refresh(otro)
    ajeno = Asesor(tenant_id=otro.id, nombre="Asesor Ajeno B", disponible=True)
    db.add(ajeno)
    db.commit()
    r = client.get(f"/asesores/{ajeno.id}/leads")
    assert r.status_code == 404


def test_aislamiento_notificaciones(client, db):
    """Notificaciones de asesor ajeno → 404."""
    otro = Tenant(nombre="Otro Tenant C")
    db.add(otro)
    db.commit()
    db.refresh(otro)
    ajeno = Asesor(tenant_id=otro.id, nombre="Asesor Ajeno C", disponible=True)
    db.add(ajeno)
    db.commit()
    r = client.get(f"/asesores/{ajeno.id}/notificaciones")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# E07: carga en GET /asesores
# ---------------------------------------------------------------------------

def test_asesor_carga_se_computa(client, db):
    """GET /asesores incluye campo `carga` con count de leads activos."""
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)

    from app.schemas.lead import LeadCreate
    from app.services.lead_service import create_lead, set_estado

    l1 = create_lead(db, tenant, LeadCreate(origen="web"))
    set_estado(db, l1, "calificado")
    l1.asesor_id = asesor.id

    l2 = create_lead(db, tenant, LeadCreate(origen="web"))
    set_estado(db, l2, "negociando")
    l2.asesor_id = asesor.id

    l3 = create_lead(db, tenant, LeadCreate(origen="web"))
    set_estado(db, l3, "cerrado_ganado")
    l3.asesor_id = asesor.id

    db.commit()

    asesores = client.get("/asesores").json()
    datos = next(a for a in asesores if a["id"] == str(asesor.id))
    assert datos["carga"] == 2  # solo calificado + negociando


# ---------------------------------------------------------------------------
# E07: PATCH /asesores/{id}/disponibilidad
# ---------------------------------------------------------------------------

def test_actualizar_disponibilidad_off(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    assert asesor.disponible is True

    r = client.patch(f"/asesores/{asesor.id}/disponibilidad", json={"disponible": False})
    assert r.status_code == 200
    assert r.json()["disponible"] is False


def test_actualizar_disponibilidad_on(client, db):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    asesor.disponible = False
    db.commit()

    r = client.patch(f"/asesores/{asesor.id}/disponibilidad", json={"disponible": True})
    assert r.status_code == 200
    assert r.json()["disponible"] is True


def test_disponibilidad_404_inexistente(client):
    r = client.patch(f"/asesores/{uuid.uuid4()}/disponibilidad", json={"disponible": False})
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# E07: notificaciones incluye nuevos tipos
# ---------------------------------------------------------------------------

def test_notificaciones_incluye_asignado(client, db):
    """El evento `asignado` aparece en las notificaciones del asesor."""
    from app.models.evento import Evento
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)

    from app.schemas.lead import LeadCreate
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead.asesor_id = asesor.id
    db.add(Evento(lead_id=lead.id, tipo="asignado", payload={"asesor_id": str(asesor.id), "auto": True}))
    db.commit()

    r = client.get(f"/asesores/{asesor.id}/notificaciones")
    assert r.status_code == 200
    tipos = [n["tipo"] for n in r.json()]
    assert "asignado" in tipos


def test_notificaciones_atribuye_por_payload_tras_reasignacion(client, db):
    """Tras reasignar, cada asesor ve solo SUS eventos (por payload, no por asesor actual)."""
    from app.models.evento import Evento
    from app.schemas.lead import LeadCreate
    tenant = lead_service.get_or_create_default_tenant(db)
    a1 = _crear_asesor(db, tenant, "Uno")
    a2 = _crear_asesor(db, tenant, "Dos")

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead.asesor_id = a2.id  # estado actual: pertenece a a2 (ya reasignado)
    # Evento histórico de a1 (cuando lo tenía) + evento de reasignación hacia a2.
    db.add(Evento(lead_id=lead.id, tipo="notificacion", payload={"asesor_id": str(a1.id), "intento": 1}))
    db.add(Evento(lead_id=lead.id, tipo="reasignado",
                  payload={"asesor_anterior": str(a1.id), "asesor_nuevo": str(a2.id)}))
    db.commit()

    # a1 conserva su `notificacion` aunque el lead ya no sea suyo.
    tipos_a1 = [n["tipo"] for n in client.get(f"/asesores/{a1.id}/notificaciones").json()]
    assert "notificacion" in tipos_a1
    assert "reasignado" not in tipos_a1

    # a2 ve el `reasignado` (asesor_nuevo) pero no la vieja `notificacion` de a1.
    tipos_a2 = [n["tipo"] for n in client.get(f"/asesores/{a2.id}/notificaciones").json()]
    assert "reasignado" in tipos_a2
    assert "notificacion" not in tipos_a2
