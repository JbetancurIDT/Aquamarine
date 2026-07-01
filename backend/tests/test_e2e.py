"""Tests e2e críticos del flujo Aquamarine (E07).

Tres flujos completos:
  1. Handoff + takeover: chat → asignación → tomar → IA silenciada.
  2. Sweep escalación: notificaciones acumuladas hasta NOTIF_MAX → reasignación.
  3. Métricas coherentes: fixture conocido → overview + asesores devuelven números exactos.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.services.sweep import _notificar_o_reasignar


# ---------------------------------------------------------------------------
# 1. Flujo handoff + takeover — la IA se silencia después de `POST /leads/{id}/tomar`
# ---------------------------------------------------------------------------

def _mock_responder_basico(db_arg, lead_arg, msg):
    """Fake de orchestrator.responder para el test E2E (no llama a Anthropic)."""
    return {
        "respuesta": "¡Hola! ¿Qué tipo de inmueble buscas?",
        "inmuebles": [],
        "handoff": False,
        "temperatura": "tibio",
        "lead_id": lead_arg.id,
        "atendido_por_humano": False,
    }


def test_e2e_handoff_takeover_silencia_ia(client, db):
    """Flujo completo: chat → forzar calificado/asignado → tomar → IA silenciada.

    Pasos:
      1. POST /chat crea el lead (IA mockeada).
      2. Se fuerza estado=calificado y asesor asignado en la BD.
      3. GET /asesores/{id}/leads muestra el lead.
      4. POST /leads/{id}/tomar → atendido_por_humano=True, estado=negociando.
      5. El mensaje de despedida de la IA está en la conversación.
      6. Un segundo POST /chat del mismo lead NO llama a la IA real (_build_client no invocado).
      7. El mensaje del lead igualmente se persiste.
    """
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Valentina Ruiz", disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)

    # Paso 1 — crear lead vía /chat con IA mockeada
    with patch("app.agent.orchestrator.responder", side_effect=_mock_responder_basico):
        r = client.post("/chat", json={"mensaje": "Busco apartamento en El Poblado, presupuesto 1.200 M"})
    assert r.status_code == 200, r.text
    lead_id = r.json()["lead_id"]

    # Paso 2 — forzar calificado + asignar asesor (simula lo que el sweep haría)
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    lead.estado = "calificado"
    lead.asesor_id = asesor.id
    lead.asignado_en = datetime.now(timezone.utc)
    db.commit()

    # Paso 3 — GET /asesores/{id}/leads debe incluir el lead
    r = client.get(f"/asesores/{asesor.id}/leads")
    assert r.status_code == 200
    ids_en_bandeja = [l["id"] for l in r.json()]
    assert lead_id in ids_en_bandeja

    # Paso 4 — POST /leads/{id}/tomar
    r = client.post(f"/leads/{lead_id}/tomar", json={"asesor_id": str(asesor.id)})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["atendido_por_humano"] is True
    assert body["estado"] == "negociando"

    # Paso 5 — mensaje de despedida de la IA en conversación
    db.expire_all()
    despedida = (
        db.query(Mensaje)
        .filter(
            Mensaje.lead_id == lead_id,
            Mensaje.rol == "agente",
            Mensaje.contenido.like(f"%{asesor.nombre}%"),
        )
        .first()
    )
    assert despedida is not None, "La IA debería haber emitido un mensaje de despedida nombrando al asesor"

    # Paso 6 — segundo POST /chat: IA NO debe ser invocada
    def _raise_if_called(*args, **kwargs):
        raise AssertionError("_build_client no debe llamarse cuando atendido_por_humano=True")

    with patch("app.agent.orchestrator._build_client", side_effect=_raise_if_called):
        r2 = client.post("/chat", json={"lead_id": lead_id, "mensaje": "Gracias, espero su llamada"})

    assert r2.status_code == 200, r2.text
    assert r2.json()["atendido_por_humano"] is True
    assert r2.json()["respuesta"] == ""

    # Paso 7 — el mensaje del lead fue persistido aunque la IA no respondió
    db.expire_all()
    msg_lead = (
        db.query(Mensaje)
        .filter(
            Mensaje.lead_id == lead_id,
            Mensaje.rol == "lead",
            Mensaje.contenido == "Gracias, espero su llamada",
        )
        .first()
    )
    assert msg_lead is not None, "El mensaje del lead debe persistirse aunque la IA esté silenciada"


# ---------------------------------------------------------------------------
# 2. Sweep escalación → reasignación automática
# ---------------------------------------------------------------------------

def test_e2e_sweep_escala_hasta_reasignacion(db):
    """Lead calificado asignado: N sweeps acumulan notificaciones hasta NOTIF_MAX,
    el sweep siguiente dispara reasignación al otro asesor con mensaje de disculpa.

    Verifica el flujo completo de escalación, no solo el paso de reasignación.
    """
    from app.core.config import settings

    tenant = lead_service.get_or_create_default_tenant(db)
    a1 = Asesor(tenant_id=tenant.id, nombre="Asesor Alfa",  disponible=True)
    a2 = Asesor(tenant_id=tenant.id, nombre="Asesor Beta",  disponible=True)
    db.add_all([a1, a2])
    db.commit()

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")

    intervalo = settings.notif_intervalos_seg["caliente"]
    lead.asesor_id = a1.id
    lead.temperatura = "caliente"
    lead.notificaciones_count = 0
    lead.asignado_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 10)
    db.commit()

    max_notif = settings.NOTIF_MAX_ANTES_REASIGNAR

    # Ejecutar max_notif sweeps, cada uno con tiempo transcurrido simulado
    for _ in range(max_notif):
        db.refresh(lead)
        # Avanzar el reloj base para que siempre haya superado el intervalo
        lead.ultima_notificacion_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 10)
        db.commit()
        _notificar_o_reasignar(db, datetime.now(timezone.utc))

    db.refresh(lead)
    assert lead.notificaciones_count == max_notif, (
        f"Esperaba {max_notif} notificaciones, got {lead.notificaciones_count}"
    )
    notif_count = (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "notificacion")
        .count()
    )
    assert notif_count == max_notif

    # Sweep final: supera NOTIF_MAX → reasignación
    db.refresh(lead)
    lead.ultima_notificacion_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 10)
    db.commit()
    _notificar_o_reasignar(db, datetime.now(timezone.utc))

    db.refresh(lead)
    assert lead.asesor_id == a2.id, "Debería haber reasignado a a2"
    assert lead.notificaciones_count == 0, "Contadores deben reiniciarse tras reasignación"
    assert lead.asignado_en is not None

    ev_reasg = (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "reasignado")
        .first()
    )
    assert ev_reasg is not None
    assert ev_reasg.payload["asesor_anterior"] == str(a1.id)
    assert ev_reasg.payload["asesor_nuevo"] == str(a2.id)

    # Mensaje de disculpa de la IA presente
    disculpa = (
        db.query(Mensaje)
        .filter(
            Mensaje.lead_id == lead.id,
            Mensaje.rol == "agente",
            Mensaje.contenido.like("%reasignando%"),
        )
        .first()
    )
    assert disculpa is not None, "La IA debería haber emitido un mensaje de disculpa al reasignar"


# ---------------------------------------------------------------------------
# 3. Métricas coherentes — fixture conocido → números exactos
# ---------------------------------------------------------------------------

@pytest.fixture
def fixture_metricas(db):
    """Fixture con distribución conocida para verificar métricas de forma determinista.

    10 leads:
      3 nuevo    (frio/tibio/caliente)
      2 contactado (tibio/frio)
      2 calificado (asesor A — caliente/tibio)
      1 negociando (asesor A — caliente, atendido_por_humano=True)
      1 cerrado_ganado (asesor A — caliente)
      1 cerrado_perdido (asesor B — frio) → rank 2 en funnel

    Funnel esperado: 10 → 7 → 5 → 2 → 1
    """
    tenant = lead_service.get_or_create_default_tenant(db)
    a1 = Asesor(tenant_id=tenant.id, nombre="Asesor A", disponible=True)
    a2 = Asesor(tenant_id=tenant.id, nombre="Asesor B", disponible=True)
    db.add_all([a1, a2])
    db.flush()

    base = datetime(2026, 1, 10, 10, 0, 0, tzinfo=timezone.utc)

    SPEC = [
        # (temp, estado, asesor, budget)
        ("frio",     "nuevo",          None, 500_000_000),
        ("tibio",    "nuevo",          None, 500_000_000),
        ("caliente", "nuevo",          None, 500_000_000),
        ("tibio",    "contactado",     None, 800_000_000),
        ("frio",     "contactado",     None, 800_000_000),
        ("caliente", "calificado",     a1,   1_000_000_000),
        ("tibio",    "calificado",     a1,   1_000_000_000),
        ("caliente", "negociando",     a1,   1_500_000_000),
        ("caliente", "cerrado_ganado", a1,   2_000_000_000),
        ("frio",     "cerrado_perdido",a2,   1_000_000_000),
    ]

    leads = []
    for i, (temp, estado, asesor, budget) in enumerate(SPEC):
        ts = base - timedelta(hours=len(SPEC) - i)
        lead = Lead(
            tenant_id=tenant.id,
            temperatura=temp,
            estado=estado,
            asesor_id=asesor.id if asesor else None,
            asignado_en=ts + timedelta(minutes=5) if asesor else None,
            atendido_por_humano=(estado == "negociando"),
            perfil={"presupuesto_max": budget},
            creado_en=ts,
        )
        db.add(lead)
        db.flush()
        db.add(Mensaje(lead_id=lead.id, rol="lead",   contenido="hola",       creado_en=ts))
        db.add(Mensaje(lead_id=lead.id, rol="agente", contenido="bienvenido", creado_en=ts + timedelta(seconds=30)))

        # evento tomado_por_humano para los negociando (necesario para tiempo_en_tomar_seg)
        if estado == "negociando" and asesor:
            db.add(Evento(lead_id=lead.id, tipo="tomado_por_humano",
                          payload={"asesor_id": str(asesor.id)},
                          creado_en=ts + timedelta(minutes=10)))

        leads.append(lead)

    db.commit()
    return tenant, a1, a2, leads


def test_e2e_metrics_overview_funnel(client, fixture_metricas):
    """GET /metrics/overview devuelve funnel y conversiones exactos para el fixture conocido."""
    r = client.get("/metrics/overview")
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["total_leads"] == 10

    # Funnel esperado: 10→7→5→2→1
    # rank_ef(cerrado_perdido)=2 → contribuye hasta calificado
    funnel = {step["etapa"]: step["count"] for step in body["funnel"]}
    assert funnel["nuevo"]         == 10
    assert funnel["contactado"]    == 7
    assert funnel["calificado"]    == 5   # 2 cal + 1 neg + 1 ganado + 1 perdido(rank2)
    assert funnel["negociando"]    == 2   # 1 neg + 1 ganado
    assert funnel["cerrado_ganado"] == 1

    # Conversiones
    conv = body["conversion"]
    assert conv["lead_a_cita"]["num"] == 5
    assert conv["lead_a_cita"]["den"] == 10
    assert conv["cita_a_negociacion"]["num"] == 2
    assert conv["cita_a_negociacion"]["den"] == 5

    # Negocios ganados: 1 lead × 2000M
    assert body["negocios_ganados"]["count"] == 1
    assert body["negocios_ganados"]["valor_cerrado_cop"] == 2_000_000_000

    # 1ª respuesta: 30 s (determinista en el fixture)
    assert body["primera_respuesta_seg"] == 30.0

    # % calificados (temp != desconocido): 10/10 = 1.0
    assert body["pct_calificados"]["num"] == 10
    assert body["pct_calificados"]["den"] == 10


def test_e2e_metrics_asesores_ratio_conversion(client, fixture_metricas):
    """GET /metrics/asesores devuelve ratio_conversion correcto por asesor."""
    _, a1, a2, _ = fixture_metricas

    r = client.get("/metrics/asesores")
    assert r.status_code == 200, r.text

    by_nombre = {m["nombre"]: m for m in r.json()}
    assert "Asesor A" in by_nombre
    assert "Asesor B" in by_nombre

    ma = by_nombre["Asesor A"]
    # a1 tiene: 2 calificado + 1 negociando + 1 cerrado_ganado = 4 leads
    assert ma["leads_asignados"] == 4
    assert ma["ganados"] == 1
    assert ma["ratio_conversion"]["num"] == 1
    assert ma["ratio_conversion"]["den"] == 4
    assert ma["tomados"] == 1           # el negociando con atendido_por_humano=True
    assert ma["en_cola"] >= 1           # calificado + negociando

    mb = by_nombre["Asesor B"]
    # a2 tiene: 1 cerrado_perdido = 1 lead, 0 ganados
    assert mb["leads_asignados"] == 1
    assert mb["ganados"] == 0
    assert mb["ratio_conversion"]["num"] == 0
    assert mb["ratio_conversion"]["den"] == 1
