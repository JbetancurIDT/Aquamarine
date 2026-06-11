"""Tests del servicio (E02 · T02.2.2): emisión de eventos y validaciones."""

import pytest

from app.models.evento import Evento
from app.schemas.lead import LeadCreate
from app.services import lead_service


def test_set_score_emite_evento(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    # Tras crear: 1 evento (lead_creado).
    assert db.query(Evento).filter(Evento.lead_id == lead.id).count() == 1

    lead = lead_service.set_score(db, lead, 80, "caliente")
    assert lead.score == 80 and lead.temperatura == "caliente"

    eventos = (
        db.query(Evento).filter(Evento.lead_id == lead.id).order_by(Evento.creado_en).all()
    )
    assert [e.tipo for e in eventos] == ["lead_creado", "score_actualizado"]
    assert eventos[1].payload == {"score": 80, "temperatura": "caliente"}


def test_eventos_crecen_con_cada_cambio(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    assert db.query(Evento).count() == 1
    lead_service.set_estado(db, lead, "contactado")
    assert db.query(Evento).count() == 2
    lead_service.set_score(db, lead, 50, "tibio")
    assert db.query(Evento).count() == 3


def test_set_estado_invalido_valueerror(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    with pytest.raises(ValueError):
        lead_service.set_estado(db, lead, "inexistente")


def test_get_or_create_default_tenant_idempotente(db):
    t1 = lead_service.get_or_create_default_tenant(db)
    t2 = lead_service.get_or_create_default_tenant(db)
    assert t1.id == t2.id
    assert t1.nombre == "Aquamarine Group"
