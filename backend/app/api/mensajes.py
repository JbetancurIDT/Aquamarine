"""Router de mensajes / conversación de un lead (E02 · T02.3.2)."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_lead_or_404, tenant_actual
from app.core.db import get_db
from app.models.mensaje import Mensaje
from app.models.tenant import Tenant
from app.schemas.mensaje import MensajeCreate, MensajeOut
from app.services import lead_service

router = APIRouter(prefix="/leads", tags=["mensajes"])


@router.get("/{lead_id}/mensajes", response_model=list[MensajeOut])
def listar_mensajes(
    lead_id: UUID,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[Mensaje]:
    """Lista la conversación del lead (ordenada por fecha). 404 si el lead no existe."""
    lead = get_lead_or_404(lead_id, db, tenant)
    return (
        db.query(Mensaje)
        .filter(Mensaje.lead_id == lead.id)
        .order_by(Mensaje.creado_en)
        .all()
    )


@router.post("/{lead_id}/mensajes", response_model=MensajeOut, status_code=201)
def crear_mensaje(
    lead_id: UUID,
    datos: MensajeCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Mensaje:
    """Agrega un mensaje a la conversación del lead (rol inválido → 422; lead → 404)."""
    lead = get_lead_or_404(lead_id, db, tenant)
    return lead_service.agregar_mensaje(db, lead, datos)
