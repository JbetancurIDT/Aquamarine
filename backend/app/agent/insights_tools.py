"""Herramientas read-only del agente de insights de gerencia (E08).

4 tools que reutilizan los helpers de `app.api.metrics` para que los números
coincidan exactamente con los del dashboard — nunca se duplica la lógica.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session, selectinload

from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.tenant import Tenant

# Reutilizar helpers y constantes de metrics.py (única fuente de verdad)
from app.api.metrics import (
    FUNNEL_ORDEN,
    FUNNEL_RANK,
    PESO_PIPELINE,
    _aware,
    _primera_respuesta_seg,
    _rank_efectivo,
    _rate,
    _valor_lead_cop,
)

# ---------------------------------------------------------------------------
# Definiciones de herramientas (para la API de Anthropic)
# ---------------------------------------------------------------------------

TOOLS: list[dict] = [
    {
        "name": "metricas_generales",
        "description": (
            "Devuelve las métricas generales del pipeline: total leads, leads calientes, "
            "% calificados, conversión lead→cita y cita→negociación, pipeline ponderado COP "
            "y negocios ganados (conteo + valor cerrado)."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "performance_asesores",
        "description": (
            "Devuelve el performance de cada asesor: nombre, leads asignados, en cola, "
            "tomados, ganados, valor cerrado COP, primera respuesta en seg y ratio de conversión."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "resumen_mensual",
        "description": (
            "Devuelve leads nuevos y valor cerrado (COP) por mes. "
            "Útil para ver la tendencia de crecimiento y ventas mes a mes."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "meses": {
                    "type": "integer",
                    "description": "Número de meses a incluir hacia atrás (default 12, máximo 24).",
                }
            },
            "required": [],
        },
    },
    {
        "name": "distribucion_leads",
        "description": "Devuelve la distribución de leads por temperatura, por origen y por estado.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
]

# ---------------------------------------------------------------------------
# Ejecutores
# ---------------------------------------------------------------------------


def _cargar_leads_con_mensajes(db: Session, tenant: Tenant) -> list:
    return (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id)
        .options(selectinload(Lead.mensajes))
        .all()
    )


def ejecutar_metricas_generales(db: Session, tenant: Tenant) -> dict:
    leads = _cargar_leads_con_mensajes(db, tenant)
    n = len(leads)

    n_calientes = sum(1 for l in leads if l.temperatura == "caliente")
    n_clasif    = sum(1 for l in leads if l.temperatura != "desconocido")

    funnel_counts = [
        sum(1 for l in leads if _rank_efectivo(l.estado) >= rank)
        for rank in range(len(FUNNEL_ORDEN))
    ]
    n_cita  = funnel_counts[FUNNEL_RANK["calificado"]]
    n_negoc = funnel_counts[FUNNEL_RANK["negociando"]]

    pipeline = 0
    for lead in leads:
        peso = PESO_PIPELINE.get(lead.estado)
        if peso is not None:
            v = _valor_lead_cop(lead.perfil or {})
            if v is not None:
                pipeline += int(round(v * peso))

    ganados   = [l for l in leads if l.estado == "cerrado_ganado"]
    v_cerrado = sum(_valor_lead_cop(l.perfil or {}) or 0 for l in ganados)

    return {
        "total_leads": n,
        "leads_calientes": n_calientes,
        "pct_calificados": round(n_clasif / n * 100, 1) if n else 0.0,
        "lead_a_cita_pct": round(n_cita / n * 100, 1) if n else 0.0,
        "cita_a_negociacion_pct": round(n_negoc / n_cita * 100, 1) if n_cita else 0.0,
        "pipeline_ponderado_cop": pipeline,
        "negocios_ganados": len(ganados),
        "valor_cerrado_cop": v_cerrado,
        "primera_respuesta_seg": _primera_respuesta_seg(leads),
    }


def ejecutar_performance_asesores(db: Session, tenant: Tenant) -> dict:
    asesores = db.query(Asesor).filter(Asesor.tenant_id == tenant.id).all()
    leads_all = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id, Lead.asesor_id.isnot(None))
        .options(selectinload(Lead.mensajes))
        .all()
    )

    lead_ids = [l.id for l in leads_all]
    tomado_en: dict = {}
    if lead_ids:
        for lid, creado in (
            db.query(Evento.lead_id, Evento.creado_en)
            .filter(Evento.lead_id.in_(lead_ids), Evento.tipo == "tomado_por_humano")
            .all()
        ):
            if lid not in tomado_en or creado < tomado_en[lid]:
                tomado_en[lid] = creado

    leads_por_asesor: dict = {}
    for lead in leads_all:
        leads_por_asesor.setdefault(lead.asesor_id, []).append(lead)

    result = []
    for asesor in asesores:
        leads_a   = leads_por_asesor.get(asesor.id, [])
        en_cola   = sum(1 for l in leads_a if l.estado in ("calificado", "negociando"))
        tomados   = sum(1 for l in leads_a if l.atendido_por_humano)
        ganados   = [l for l in leads_a if l.estado == "cerrado_ganado"]
        v_cerrado = sum(_valor_lead_cop(l.perfil or {}) or 0 for l in ganados)

        tiempos_tomar = []
        for lead in leads_a:
            t = tomado_en.get(lead.id)
            if t is not None and lead.asignado_en is not None:
                tiempos_tomar.append(
                    max(0.0, (_aware(t) - _aware(lead.asignado_en)).total_seconds())
                )

        na = len(leads_a)
        result.append({
            "nombre": asesor.nombre,
            "disponible": asesor.disponible,
            "leads_asignados": na,
            "en_cola": en_cola,
            "tomados": tomados,
            "ganados": len(ganados),
            "valor_cerrado_cop": v_cerrado,
            "primera_respuesta_seg": _primera_respuesta_seg(leads_a),
            "tiempo_en_tomar_seg": (
                round(sum(tiempos_tomar) / len(tiempos_tomar), 2) if tiempos_tomar else None
            ),
            "ratio_conversion_pct": round(len(ganados) / na * 100, 1) if na else 0.0,
        })

    return {"asesores": result}


def ejecutar_resumen_mensual(db: Session, tenant: Tenant, meses: int = 12) -> dict:
    """Leads nuevos y valor cerrado por mes (cohorte por `creado_en`).

    Ambas métricas usan `lead.creado_en` como mes de referencia:
    - leads_nuevos: cuántos leads entraron ese mes.
    - valor_cerrado: suma del presupuesto_max de los leads que entraron ese mes Y cerraron ganado.
    """
    meses = min(max(int(meses), 1), 24)
    now   = datetime.now(timezone.utc)

    # Ventana temporal + set de meses válidos
    cutoff = now - timedelta(days=30 * meses + 5)
    meses_validos: set[str] = set()
    for i in range(meses):
        meses_validos.add((now - timedelta(days=30 * i)).strftime("%Y-%m"))

    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id, Lead.creado_en >= cutoff)
        .all()
    )

    buckets: dict = defaultdict(lambda: {"leads_nuevos": 0, "valor_cerrado": 0})
    for lead in leads:
        if lead.creado_en is None:
            continue
        mes = _aware(lead.creado_en).strftime("%Y-%m")
        if mes in meses_validos:
            buckets[mes]["leads_nuevos"] += 1
            if lead.estado == "cerrado_ganado":
                buckets[mes]["valor_cerrado"] += _valor_lead_cop(lead.perfil or {}) or 0

    resultado = sorted(
        [{"mes": mes, **buckets.get(mes, {"leads_nuevos": 0, "valor_cerrado": 0})}
         for mes in meses_validos],
        key=lambda x: x["mes"],
    )
    return {"meses": resultado}


def ejecutar_distribucion_leads(db: Session, tenant: Tenant) -> dict:
    leads = db.query(Lead).filter(Lead.tenant_id == tenant.id).all()

    por_temperatura: dict = defaultdict(int)
    por_origen: dict      = defaultdict(int)
    por_estado: dict      = defaultdict(int)

    for lead in leads:
        por_temperatura[lead.temperatura or "desconocido"] += 1
        por_origen[lead.origen or "sin_origen"] += 1
        por_estado[lead.estado] += 1

    return {
        "por_temperatura": dict(sorted(por_temperatura.items(), key=lambda x: -x[1])),
        "por_origen":      dict(sorted(por_origen.items(),      key=lambda x: -x[1])),
        "por_estado":      dict(sorted(por_estado.items(),      key=lambda x: -x[1])),
    }


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def ejecutar_tool(nombre: str, inputs: dict, db: Session, tenant: Tenant) -> dict:
    """Ejecuta la tool por nombre y devuelve el resultado como dict JSON-serializable."""
    if nombre == "metricas_generales":
        return ejecutar_metricas_generales(db, tenant)
    if nombre == "performance_asesores":
        return ejecutar_performance_asesores(db, tenant)
    if nombre == "resumen_mensual":
        return ejecutar_resumen_mensual(db, tenant, meses=inputs.get("meses", 12))
    if nombre == "distribucion_leads":
        return ejecutar_distribucion_leads(db, tenant)
    return {"error": f"Tool desconocida: {nombre}"}
