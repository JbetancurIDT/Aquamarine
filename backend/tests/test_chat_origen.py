"""Tests del router /chat/{origen} (E03 · Parte 3).

Verifica que el origen llegue desde la URL al lead y que no se sobreescriba
si el lead ya existe. No llama a la API de Anthropic (se mockea orchestrator.responder).
"""

import uuid
from unittest.mock import patch

from app.models.lead import Lead
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _mock_responder(db_arg, lead_arg, msg):
    """Fake de orchestrator.responder que devuelve una respuesta mínima válida."""
    return {
        "respuesta": "hola",
        "inmuebles": [],
        "handoff": False,
        "temperatura": "desconocido",
        "lead_id": lead_arg.id,
    }


def test_post_chat_con_origen_path_crea_lead_con_origen(client, db):
    """POST /chat/meta crea un lead con origen='meta'."""
    with patch("app.agent.orchestrator.responder", side_effect=_mock_responder):
        r = client.post("/chat/meta", json={"mensaje": "hola"})
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead_id"]
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
    assert lead is not None
    assert lead.origen == "meta"


def test_post_chat_raiz_sin_origen_crea_lead_con_origen_none(client, db):
    """POST /chat sin origen crea lead con origen=None."""
    with patch("app.agent.orchestrator.responder", side_effect=_mock_responder):
        r = client.post("/chat", json={"mensaje": "hola"})
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead_id"]
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(lead_id)).first()
    assert lead is not None
    assert lead.origen is None


def test_post_chat_origen_path_con_lead_existente_no_cambia_origen(client, db):
    """POST /chat/portal con lead_id existente (origen='web') no modifica el origen."""
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    db.flush()
    with patch("app.agent.orchestrator.responder", side_effect=_mock_responder):
        r = client.post("/chat/portal", json={"mensaje": "hola", "lead_id": str(lead.id)})
    assert r.status_code == 200, r.text
    db.refresh(lead)
    assert lead.origen == "web"


def test_post_chat_origen_invalido_retorna_422(client, db):
    """POST /chat/<valor_no_permitido> devuelve 422 (no es un origen válido)."""
    r = client.post("/chat/invalidoXYZ", json={"mensaje": "hola"})
    assert r.status_code == 422
