"""Router de asesores (E04/E05/E07).

GET    /asesores                          → lista asesores con carga computada.
GET    /asesores/{id}/leads               → leads asignados al asesor.
GET    /asesores/{id}/notificaciones      → eventos recientes (handoff/asignado/notificacion/reasignado/tomado).
PATCH  /asesores/{id}/disponibilidad      → toggle disponible/no disponible.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.api.deps import tenant_actual
from app.core.db import get_db
from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.schemas.asesor import AsesorOut, DisponibilidadUpdate
from app.schemas.lead import LeadOut

router = APIRouter(prefix="/asesores", tags=["asesores"])

_TIPOS_NOTIFICACION = {
    "handoff",
    "asignado",
    "notificacion",
    "reasignado",
    "tomado_por_humano",
}


class NotificacionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    evento_id: UUID
    lead_id: UUID
    tipo: str
    temperatura: str | None
    perfil_resumen: dict
    creado_en: datetime


def _get_asesor_o_404(asesor_id: UUID, db: Session, tenant: Tenant) -> Asesor:
    asesor = (
        db.query(Asesor).filter(Asesor.id == asesor_id, Asesor.tenant_id == tenant.id).first()
    )
    if asesor is None:
        raise HTTPException(status_code=404, detail="Asesor no encontrado")
    return asesor


def _carga_por_asesor(db: Session, asesor_ids: list) -> dict:
    """Cuenta leads activos (calificado + negociando) por asesor_id."""
    if not asesor_ids:
        return {}
    rows = (
        db.query(Lead.asesor_id, func.count(Lead.id))
        .filter(
            Lead.asesor_id.in_(asesor_ids),
            Lead.estado.in_(["calificado", "negociando"]),
        )
        .group_by(Lead.asesor_id)
        .all()
    )
    return {asesor_id: count for asesor_id, count in rows}


@router.get("", response_model=list[AsesorOut])
def listar_asesores(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[dict]:
    """Lista los asesores del tenant con su carga actual (leads activos)."""
    asesores = db.query(Asesor).filter(Asesor.tenant_id == tenant.id).all()
    cargas = _carga_por_asesor(db, [a.id for a in asesores])
    result = []
    for a in asesores:
        result.append({
            "id": a.id,
            "nombre": a.nombre,
            "disponible": a.disponible,
            "carga": cargas.get(a.id, 0),
        })
    return result


@router.get("/{asesor_id}/leads", response_model=list[LeadOut])
def leads_del_asesor(
    asesor_id: UUID,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[Lead]:
    """Leads asignados al asesor, más reciente primero. 404 si el asesor no existe."""
    _get_asesor_o_404(asesor_id, db, tenant)
    return (
        db.query(Lead)
        .filter(Lead.asesor_id == asesor_id, Lead.tenant_id == tenant.id)
        .order_by(Lead.creado_en.desc())
        .all()
    )


@router.get("/{asesor_id}/notificaciones", response_model=list[NotificacionOut])
def notificaciones(
    asesor_id: UUID,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[dict]:
    """Eventos de actividad dirigidos a este asesor, más reciente primero.

    Incluye: handoff, asignado, notificacion, reasignado, tomado_por_humano.

    La pertenencia se decide por el `asesor_id` guardado en el payload del evento
    (o `asesor_nuevo` para `reasignado`), NO por el asesor actual del lead: así, tras
    una reasignación, cada asesor sigue viendo solo los eventos que le correspondieron
    (el join al lead se usa únicamente para acotar por tenant).
    """
    _get_asesor_o_404(asesor_id, db, tenant)
    asesor_str = str(asesor_id)
    filas = (
        db.query(Evento, Lead)
        .join(Lead, Evento.lead_id == Lead.id)
        .filter(
            Lead.tenant_id == tenant.id,
            Evento.tipo.in_(_TIPOS_NOTIFICACION),
            or_(
                Evento.payload["asesor_id"].astext == asesor_str,
                Evento.payload["asesor_nuevo"].astext == asesor_str,
            ),
        )
        .order_by(Evento.creado_en.desc())
        .limit(50)
        .all()
    )
    return [
        {
            "evento_id": ev.id,
            "lead_id": lead.id,
            "tipo": ev.tipo,
            "temperatura": lead.temperatura,
            "perfil_resumen": lead.perfil or {},
            "creado_en": ev.creado_en,
        }
        for ev, lead in filas
    ]


@router.patch("/{asesor_id}/disponibilidad", response_model=AsesorOut)
def actualizar_disponibilidad(
    asesor_id: UUID,
    body: DisponibilidadUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> dict:
    """Cambia la disponibilidad del asesor (disponible/no disponible)."""
    asesor = _get_asesor_o_404(asesor_id, db, tenant)
    asesor.disponible = body.disponible
    db.commit()
    db.refresh(asesor)
    cargas = _carga_por_asesor(db, [asesor.id])
    return {
        "id": asesor.id,
        "nombre": asesor.nombre,
        "disponible": asesor.disponible,
        "carga": cargas.get(asesor.id, 0),
    }
