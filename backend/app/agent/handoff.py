"""Handoff mínimo (E03 · adelanta parte de T06.1.2).

Asigna un asesor disponible, mueve el estado a `calificado` y emite el evento `handoff`
con un snapshot del lead. **Idempotente**. El handoff REAL (notificación, UI, impersonación)
se completa en E06.
"""

import logging

from sqlalchemy.orm import Session

from app.models.asesor import Asesor
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
    """Dispara el handoff del lead. Devuelve True si lo ejecutó ahora, False si ya estaba hecho.

    Idempotente: si el lead ya tiene un evento `handoff`, no re-dispara.
    """
    if _ya_tiene_handoff(db, lead):
        return False

    # Asigna un asesor disponible del tenant; si no hay, queda en null (E06 reasigna).
    if lead.asesor_id is None:
        asesor = (
            db.query(Asesor)
            .filter(Asesor.tenant_id == lead.tenant_id, Asesor.disponible.is_(True))
            .first()
        )
        if asesor is not None:
            lead.asesor_id = asesor.id

    # Estado → calificado (si no lo está). set_estado hace commit y emite estado_cambiado.
    if lead.estado != "calificado":
        lead_service.set_estado(db, lead, "calificado")

    # Evento `handoff` con snapshot del lead (base para la notificación al asesor en E06).
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
