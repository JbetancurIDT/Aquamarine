"""Barrido periódico de notificaciones escalonadas y auto-reasignación (E07).

`_sweep_once(db)` — una pasada; se puede llamar directamente en tests.
`sweep_loop()`    — bucle async para el lifespan de FastAPI.

Lógica por pasada:
  1. Asigna leads `calificado` sin asesor al disponible con menor cola.
  2. Para cada lead `calificado` asignado y no tomado por humano:
     - Si pasó ≥ intervalo (según temperatura) desde la última notificación / asignación:
       * Si `notificaciones_count < NOTIF_MAX`: emite evento `notificacion` y actualiza contadores.
       * Si `notificaciones_count >= NOTIF_MAX`: la IA se disculpa, reasigna al asesor con menor
         cola **distinto** al actual, resetea contadores, emite `reasignado`. Si no hay otro asesor
         disponible, solo refresca el reloj (no reasigna al mismo ni spamea eventos).

El job es robusto: **commit por lead** (un fallo no descarta el trabajo de los demás) e idempotente.
El commit por lead también hace visibles las asignaciones dentro de la misma pasada, para que el
balanceo de carga (`asesor_con_menor_cola`) no apile todos los leads sobre el mismo asesor.
"""

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.db import SessionLocal
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.services.lead_service import asesor_con_menor_cola

logger = logging.getLogger(__name__)


def _ts(dt: datetime) -> datetime:
    """Garantiza que el datetime sea timezone-aware (UTC)."""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def _asignar_sin_asesor(db: Session, now: datetime) -> None:
    """Paso 1: asigna leads calificados sin asesor al disponible con menor cola.

    Commit por lead → cada asignación es visible para el conteo del siguiente
    (con `autoflush=False` un solo commit al final apilaría todos sobre uno).
    """
    sin_asesor = (
        db.query(Lead)
        .filter(Lead.estado == "calificado", Lead.asesor_id.is_(None))
        .all()
    )
    for lead in sin_asesor:
        try:
            asesor = asesor_con_menor_cola(db, lead.tenant_id)
            if asesor is None:
                continue
            lead.asesor_id = asesor.id
            lead.asignado_en = now
            lead.notificaciones_count = 0
            lead.ultima_notificacion_en = None
            db.add(Evento(lead_id=lead.id, tipo="asignado", payload={
                "asesor_id": str(asesor.id),
                "auto": True,
            }))
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("Sweep: fallo asignando lead %s: %s", lead.id, exc)


def _notificar_o_reasignar(db: Session, now: datetime) -> None:
    """Paso 2: escala notificaciones y reasigna leads sin tomar. Commit por lead."""
    intervalos = settings.notif_intervalos_seg
    max_notif = settings.NOTIF_MAX_ANTES_REASIGNAR

    asignados = (
        db.query(Lead)
        .filter(
            Lead.estado == "calificado",
            Lead.asesor_id.is_not(None),
            Lead.atendido_por_humano.is_(False),
        )
        .all()
    )
    for lead in asignados:
        try:
            intervalo_seg = intervalos.get(lead.temperatura, intervalos["desconocido"])
            base = _ts(lead.ultima_notificacion_en) or _ts(lead.asignado_en) or _ts(lead.creado_en)
            if base is None:
                continue

            elapsed = (now - base).total_seconds()
            if elapsed < intervalo_seg:
                continue

            if (lead.notificaciones_count or 0) >= max_notif:
                _reasignar(db, lead, now)
            else:
                lead.notificaciones_count = (lead.notificaciones_count or 0) + 1
                lead.ultima_notificacion_en = now
                db.add(Evento(lead_id=lead.id, tipo="notificacion", payload={
                    "intento": lead.notificaciones_count,
                    "temperatura": lead.temperatura,
                    "asesor_id": str(lead.asesor_id),
                }))
                db.commit()
        except Exception as exc:
            db.rollback()
            logger.exception("Sweep: fallo procesando lead %s: %s", lead.id, exc)


def _reasignar(db: Session, lead: Lead, now: datetime) -> None:
    """Reasigna el lead a un asesor distinto. Si no hay alternativa, solo refresca el reloj."""
    asesor_anterior_id = lead.asesor_id
    asesor_nuevo = asesor_con_menor_cola(db, lead.tenant_id, excluir=asesor_anterior_id)

    if asesor_nuevo is None or asesor_nuevo.id == asesor_anterior_id:
        # No hay otro asesor disponible: no reasignamos al mismo ni emitimos disculpa/evento.
        # Refrescamos el reloj para no spamear y reintentar en el próximo intervalo.
        lead.ultima_notificacion_en = now
        db.commit()
        return

    # Mensaje de disculpa de la IA (solo cuando sí hay a quién reasignar).
    db.add(Mensaje(
        lead_id=lead.id,
        rol="agente",
        contenido=(
            "Lamento la demora en conectarte con un asesor; te estoy reasignando "
            "a otro de nuestro equipo para atenderte mejor. "
            "¡Ya estarás en muy buenas manos! 🙏"
        ),
    ))
    lead.asesor_id = asesor_nuevo.id
    lead.asignado_en = now
    lead.notificaciones_count = 0
    lead.ultima_notificacion_en = None
    db.add(Evento(lead_id=lead.id, tipo="reasignado", payload={
        "asesor_anterior": str(asesor_anterior_id),
        "asesor_nuevo": str(asesor_nuevo.id),
        "auto": True,
    }))
    db.commit()


def _sweep_once(db: Session) -> None:
    """Una pasada del barrido. Robusta: un fallo en un lead no detiene los demás."""
    now = datetime.now(timezone.utc)
    _asignar_sin_asesor(db, now)
    _notificar_o_reasignar(db, now)


def _run_sweep() -> None:
    """Crea sesión, ejecuta _sweep_once y cierra. Para uso en asyncio.to_thread."""
    db = SessionLocal()
    try:
        _sweep_once(db)
    except Exception as exc:
        logger.exception("Sweep global error: %s", exc)
    finally:
        db.close()


async def sweep_loop() -> None:
    """Bucle asíncrono para FastAPI lifespan. Corre cada SWEEP_INTERVALO_SEG segundos."""
    while True:
        await asyncio.sleep(settings.SWEEP_INTERVALO_SEG)
        await asyncio.to_thread(_run_sweep)
