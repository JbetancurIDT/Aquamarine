"""Handoff mínimo (E03 → E07).

Asigna el asesor disponible con MENOR cola (balanceo), mueve el estado a
`calificado`, setea `asignado_en` y emite los eventos `handoff` + `asignado`.
Idempotente: si ya existe un evento `handoff`, no re-dispara.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.evento import Evento
from app.models.lead import Lead
from app.services import lead_service

logger = logging.getLogger(__name__)


def _ya_tiene_handoff(db: Session, lead: Lead) -> bool:
    return (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "handoff")
        .first()
        is not None
    )


def ejecutar_handoff_minimo(db: Session, lead: Lead, *, sin_calificar: bool = False) -> bool:
    """Dispara el handoff del lead. Devuelve True si lo ejecutó ahora, False si ya estaba hecho."""
    if _ya_tiene_handoff(db, lead):
        return False

    now = datetime.now(timezone.utc)

    # Asigna el asesor disponible con MENOR cola; si no hay, queda null (sweep asigna luego).
    if lead.asesor_id is None:
        asesor = lead_service.asesor_con_menor_cola(db, lead.tenant_id)
        if asesor is not None:
            lead.asesor_id = asesor.id
            lead.asignado_en = now
            lead.notificaciones_count = 0
            lead.ultima_notificacion_en = None
            # Evento `asignado` (dispara la notificación en la pantalla del asesor)
            db.add(Evento(lead_id=lead.id, tipo="asignado", payload={
                "asesor_id": str(asesor.id),
                "auto": True,
            }))

    # Estado → calificado (si no lo está). set_estado hace commit y emite estado_cambiado.
    if lead.estado != "calificado":
        lead_service.set_estado(db, lead, "calificado")

    # Evento `handoff` con snapshot (base para métricas y notificaciones).
    payload = {
        "nombre": lead.nombre,
        "contacto": lead.contacto,
        "perfil": lead.perfil,
        "temperatura": lead.temperatura,
        "score": lead.score,
        "asesor_id": str(lead.asesor_id) if lead.asesor_id else None,
        "sin_calificar": sin_calificar,
    }
    db.add(Evento(lead_id=lead.id, tipo="handoff", payload=payload))
    db.commit()
    db.refresh(lead)
    logger.info("Handoff ejecutado para lead %s (sin_calificar=%s)", lead.id, sin_calificar)
    return True
