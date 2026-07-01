"""Tests del módulo de insights de gerencia (E08).

1. `ejecutar_resumen_mensual` agrupa correctamente leads y valor cerrado por mes.
2. `POST /insights/ask` responde 200 con el SDK de Anthropic mockeado.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from app.models.lead import Lead
from app.schemas.lead import LeadCreate
from app.services import lead_service


# ---------------------------------------------------------------------------
# Test 1 — resumen_mensual agrupa por mes
# ---------------------------------------------------------------------------

def test_resumen_mensual_agrupa_leads_y_valor_por_mes(db):
    """Leads en meses distintos → buckets independientes de leads_nuevos y valor_cerrado."""
    from app.agent.insights_tools import ejecutar_resumen_mensual

    tenant = lead_service.get_or_create_default_tenant(db)

    # Lead en mayo 2026 — no cerrado
    ts_may = datetime(2026, 5, 20, 10, 0, tzinfo=timezone.utc)
    l1 = Lead(
        tenant_id=tenant.id,
        estado="nuevo",
        temperatura="frio",
        perfil={"presupuesto_max": 1_000_000},
        creado_en=ts_may,
    )

    # Lead en junio 2026 — cerrado ganado (valor 2 M)
    ts_jun = datetime(2026, 6, 5, 12, 0, tzinfo=timezone.utc)
    l2 = Lead(
        tenant_id=tenant.id,
        estado="cerrado_ganado",
        temperatura="caliente",
        perfil={"presupuesto_max": 2_000_000},
        creado_en=ts_jun,
    )

    # Lead en junio 2026 — nuevo (no cerrado)
    l3 = Lead(
        tenant_id=tenant.id,
        estado="nuevo",
        temperatura="tibio",
        perfil={"presupuesto_max": 800_000},
        creado_en=ts_jun,
    )

    db.add_all([l1, l2, l3])
    db.commit()

    result = ejecutar_resumen_mensual(db, tenant, meses=12)
    assert "meses" in result

    meses_dict = {m["mes"]: m for m in result["meses"]}

    assert "2026-05" in meses_dict, "Debería incluir mayo 2026"
    assert meses_dict["2026-05"]["leads_nuevos"] == 1
    assert meses_dict["2026-05"]["valor_cerrado"] == 0  # l1 no es cerrado_ganado

    assert "2026-06" in meses_dict, "Debería incluir junio 2026"
    assert meses_dict["2026-06"]["leads_nuevos"] == 2   # l2 + l3
    assert meses_dict["2026-06"]["valor_cerrado"] == 2_000_000  # solo l2

    # Meses ordenados cronológicamente
    fechas = [m["mes"] for m in result["meses"]]
    assert fechas == sorted(fechas)


def test_resumen_mensual_respeta_limite_meses(db):
    """Leads fuera del rango de meses NO aparecen en el resultado."""
    from app.agent.insights_tools import ejecutar_resumen_mensual

    tenant = lead_service.get_or_create_default_tenant(db)

    # Lead muy antiguo (hace 2 años)
    ts_old = datetime(2024, 1, 15, tzinfo=timezone.utc)
    db.add(Lead(
        tenant_id=tenant.id, estado="nuevo", temperatura="frio",
        perfil={}, creado_en=ts_old,
    ))
    db.commit()

    result = ejecutar_resumen_mensual(db, tenant, meses=6)
    meses_dict = {m["mes"]: m for m in result["meses"]}

    assert "2024-01" not in meses_dict, "Lead de 2 años atrás no debe aparecer en ventana de 6 meses"


# ---------------------------------------------------------------------------
# Test 2 — POST /insights/ask con SDK mockeado
# ---------------------------------------------------------------------------

def test_insights_ask_responde_200_con_sdk_mockeado(client):
    """POST /insights/ask devuelve 200 y la respuesta del agente (Anthropic SDK mockeado)."""
    mock_response = MagicMock()
    mock_response.stop_reason = "end_turn"
    mock_message  = MagicMock()
    mock_message.type = "text"
    mock_message.text = "Tienes 5 leads en total, de los cuales 2 son calientes."
    mock_response.content = [mock_message]

    with patch("app.agent.insights_agent._build_client") as mock_build:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_build.return_value = mock_client

        r = client.post("/insights/ask", json={"pregunta": "¿Cuántos leads tengo?"})

    assert r.status_code == 200, r.text
    body = r.json()
    assert "respuesta" in body
    assert body["respuesta"] == "Tienes 5 leads en total, de los cuales 2 son calientes."
    assert "datos" in body
    assert body["datos"] is None  # no hubo tool_use en este mock


def test_insights_ask_con_tool_use_mockeado(client, db):
    """Cuando el SDK responde con tool_use, se ejecuta la tool y se devuelven los datos."""
    tenant = lead_service.get_or_create_default_tenant(db)

    # Primera respuesta: pide tool_use
    mock_resp1 = MagicMock()
    mock_resp1.stop_reason = "tool_use"
    tool_bloque = MagicMock()
    tool_bloque.type       = "tool_use"
    tool_bloque.name       = "metricas_generales"
    tool_bloque.id         = "tu_001"
    tool_bloque.input      = {}
    mock_resp1.content     = [tool_bloque]

    # Segunda respuesta: texto final
    mock_resp2 = MagicMock()
    mock_resp2.stop_reason = "end_turn"
    texto_bloque = MagicMock()
    texto_bloque.type = "text"
    texto_bloque.text = "En total tienes 0 leads y el pipeline ponderado es $0 M."
    mock_resp2.content = [texto_bloque]

    with patch("app.agent.insights_agent._build_client") as mock_build:
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [mock_resp1, mock_resp2]
        mock_build.return_value = mock_client

        r = client.post("/insights/ask", json={"pregunta": "Dame el resumen general del pipeline."})

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["respuesta"] == "En total tienes 0 leads y el pipeline ponderado es $0 M."
    # datos debe incluir el resultado de metricas_generales
    assert body["datos"] is not None
    assert "metricas_generales" in body["datos"]
    assert "total_leads" in body["datos"]["metricas_generales"]


def test_insights_ask_pregunta_vacia_422(client):
    """Pregunta vacía debe devolver 422."""
    r = client.post("/insights/ask", json={"pregunta": ""})
    assert r.status_code == 422
