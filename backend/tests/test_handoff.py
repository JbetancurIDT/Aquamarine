"""Tests del handoff mínimo (E03 · adelanto de T06.1.2). Sin API: solo BD."""

from app.agent.handoff import ejecutar_handoff_minimo
from app.models.asesor import Asesor
from app.models.evento import Evento
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _lead(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    return tenant, lead_service.create_lead(db, tenant, LeadCreate(origen="web"))


def _n_handoffs(db, lead):
    return db.query(Evento).filter(Evento.lead_id == lead.id, Evento.tipo == "handoff").count()


def test_handoff_asigna_asesor_y_emite_evento(db):
    tenant, lead = _lead(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Daniela", disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)

    hecho = ejecutar_handoff_minimo(db, lead)
    assert hecho is True
    assert lead.asesor_id == asesor.id
    assert lead.estado == "calificado"
    assert _n_handoffs(db, lead) == 1


def test_handoff_es_idempotente(db):
    _, lead = _lead(db)
    assert ejecutar_handoff_minimo(db, lead) is True
    assert ejecutar_handoff_minimo(db, lead) is False  # ya tenía handoff → no re-dispara
    assert _n_handoffs(db, lead) == 1


def test_handoff_sin_asesores_igual_marca_el_lead(db):
    _, lead = _lead(db)  # sin asesores sembrados
    hecho = ejecutar_handoff_minimo(db, lead)
    assert hecho is True
    assert lead.asesor_id is None  # no había a quién asignar (E06 reasigna)
    assert lead.estado == "calificado"
    assert _n_handoffs(db, lead) == 1


def test_handoff_snapshot_en_payload(db):
    _, lead = _lead(db)
    ejecutar_handoff_minimo(db, lead, sin_calificar=True)
    evento = db.query(Evento).filter(Evento.lead_id == lead.id, Evento.tipo == "handoff").first()
    assert evento.payload["sin_calificar"] is True
    assert "perfil" in evento.payload and "temperatura" in evento.payload
