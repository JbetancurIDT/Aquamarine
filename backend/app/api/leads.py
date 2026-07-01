"""Router de leads (E02/E07).

CRUD del ciclo de vida del lead. La lógica + emisión de eventos vive en
`lead_service`; aquí solo va el HTTP (validación, 404, filtros).

Orden de rutas: las rutas literales (`/en-vivo`) deben declararse ANTES de
las rutas parametrizadas (`/{lead_id}`) para evitar conflictos de path.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_lead_or_404, tenant_actual
from app.core.db import get_db
from app.core.enums import Estado, Origen, Temperatura
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.schemas.lead import (
    AsesorUpdate,
    EstadoUpdate,
    LeadConMensajes,
    LeadCreate,
    LeadOut,
    TomarLeadBody,
)
from app.services import lead_service

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("", response_model=LeadOut, status_code=201)
def crear_lead(
    datos: LeadCreate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Lead:
    """Crea un lead (emite `lead_creado`)."""
    return lead_service.create_lead(db, tenant, datos)


@router.get("", response_model=list[LeadOut])
def listar_leads(
    estado: Estado | None = None,
    temperatura: Temperatura | None = None,
    origen: Origen | None = None,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[Lead]:
    """Lista los leads del tenant, con filtros opcionales (más reciente primero)."""
    q = db.query(Lead).filter(Lead.tenant_id == tenant.id)
    if estado is not None:
        q = q.filter(Lead.estado == estado.value)
    if temperatura is not None:
        q = q.filter(Lead.temperatura == temperatura.value)
    if origen is not None:
        q = q.filter(Lead.origen == origen.value)
    return q.order_by(Lead.creado_en.desc()).all()


@router.get("/en-vivo", response_model=list[LeadOut])
def leads_en_vivo(
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> list[Lead]:
    """Leads en calificado o negociando sin asesor asignado (más reciente primero).

    Usado por la vista del asesor para mostrar el panel "En vivo · sin asignar"
    y permitirle tomar una conversación directamente.
    """
    return (
        db.query(Lead)
        .filter(
            Lead.tenant_id == tenant.id,
            Lead.estado.in_(["calificado", "negociando"]),
            Lead.asesor_id.is_(None),
        )
        .order_by(Lead.creado_en.desc())
        .all()
    )


@router.get("/{lead_id}", response_model=LeadConMensajes)
def detalle_lead(
    lead_id: UUID,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Lead:
    """Detalle de un lead con su conversación (mensajes ordenados). 404 si no existe."""
    return get_lead_or_404(lead_id, db, tenant)


@router.patch("/{lead_id}/estado", response_model=LeadOut)
def cambiar_estado(
    lead_id: UUID,
    body: EstadoUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Lead:
    """Cambia el estado del lead (valida y emite `estado_cambiado`). 404 si no existe."""
    lead = get_lead_or_404(lead_id, db, tenant)
    return lead_service.set_estado(db, lead, body.estado)


@router.patch("/{lead_id}/asesor", response_model=LeadOut)
def asignar_asesor(
    lead_id: UUID,
    body: AsesorUpdate,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Lead:
    """Asigna o reasigna asesor al lead (emite `asesor_asignado`). 404 si el lead o asesor no existen."""
    lead = get_lead_or_404(lead_id, db, tenant)
    try:
        return lead_service.set_asesor(db, lead, body.asesor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{lead_id}/tomar", response_model=LeadOut)
def tomar_lead(
    lead_id: UUID,
    body: TomarLeadBody,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> Lead:
    """El asesor toma el chat: apaga la IA, mueve a negociando, emite `tomado_por_humano`.

    Idempotente: si ya estaba tomado, devuelve el lead sin cambios.
    404 si el lead o el asesor no existen (o son de otro tenant).
    """
    lead = get_lead_or_404(lead_id, db, tenant)
    try:
        return lead_service.tomar_lead(db, lead, body.asesor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
