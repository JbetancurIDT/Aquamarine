"""Router de métricas (E02 · T02.3.3).

`GET /metrics/overview` calcula desde Postgres (`leads`/`mensajes`) y devuelve SIEMPRE
la misma forma (con `response_model`) para que el dashboard la consuma estable. Lo que
aún no tiene datos se devuelve en 0/null sin romper.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, selectinload

from app.api.deps import tenant_actual
from app.core.db import get_db
from app.core.enums import Estado, Origen, Temperatura
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.schemas.metrics import MetricsOverview

router = APIRouter(prefix="/metrics", tags=["metrics"])


def _bump(bucket: dict[str, int], valor: str) -> None:
    """Suma 1 al bucket del valor; si está fuera de catálogo va a 'otros'.

    Así `sum(bucket.values()) == total_leads` siempre (no se pierde ningún lead,
    aunque el agente escriba un valor inesperado saltándose el API en E03).
    """
    bucket[valor if valor in bucket else "otros"] += 1


def _tiempo_primera_respuesta_seg(leads: list[Lead]) -> float | None:
    """Promedio (seg) entre crear el lead y su primer mensaje de rol 'agente'.

    Devuelve None si ningún lead tiene respuesta del agente todavía.
    """
    tiempos = []
    for lead in leads:
        respuestas = [m.creado_en for m in lead.mensajes if m.rol == "agente"]
        if respuestas:
            delta = (min(respuestas) - lead.creado_en).total_seconds()
            if delta >= 0:
                tiempos.append(delta)
    return round(sum(tiempos) / len(tiempos), 2) if tiempos else None


@router.get("/overview", response_model=MetricsOverview)
def overview(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> dict:
    """Resumen de métricas del embudo para el dashboard."""
    # selectinload de mensajes: evita el N+1 al calcular la primera respuesta.
    leads = (
        db.query(Lead)
        .filter(Lead.tenant_id == tenant.id)
        .options(selectinload(Lead.mensajes))
        .all()
    )

    # Todas las claves del catálogo siempre presentes, más 'otros' (invariante: la suma
    # de cada bucket == total_leads).
    por_origen = {o.value: 0 for o in Origen} | {"otros": 0}
    por_temperatura = {t.value: 0 for t in Temperatura} | {"otros": 0}
    por_estado = {e.value: 0 for e in Estado} | {"otros": 0}
    for lead in leads:
        _bump(por_origen, lead.origen)
        _bump(por_temperatura, lead.temperatura)
        _bump(por_estado, lead.estado)

    return {
        "total_leads": len(leads),
        "por_origen": por_origen,
        "por_temperatura": por_temperatura,
        "por_estado": por_estado,
        "tiempo_primera_respuesta_seg": _tiempo_primera_respuesta_seg(leads),
        # TODO: la "cita" se modela con el handoff (E06); por ahora sin datos → 0.0.
        "conversion": {"lead_a_cita": 0.0, "cita_a_negociacion": 0.0},
    }
