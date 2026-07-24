"""Endpoint del chat con el agente Aqua (E03 · T03.3.1 → API).

`/chat` está unificado: si no llega `lead_id`, **el agente crea el lead** (emite
`lead_creado`) y devuelve el `lead_id` para continuar la conversación.

`/chat/{origen}` permite que el front pase el canal de origen por la URL
(ej. `/chat/meta`, `/chat/web`). Si ya llega `lead_id`, el origen del path se ignora.
"""

from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent import orchestrator
from app.api.deps import get_lead_or_404, tenant_actual
from app.core.db import get_db
from app.models.tenant import Tenant
from app.schemas.lead import LeadCreate
from app.services import lead_service

router = APIRouter(prefix="/chat", tags=["chat"])

_ORIGENES_VALIDOS = Literal["web", "meta", "portal", "referido", "otro"]


class ChatRequest(BaseModel):
    lead_id: UUID | None = None  # si es None, el agente crea el lead
    mensaje: str = Field(min_length=1)  # mensaje vacío → 422
    # Canal de origen del lead nuevo (lo pasa el front por la URL /chat/<origen>/). None si no se sabe.
    origen: str | None = None


class MapaPreview(BaseModel):
    codigo: str
    titulo: str
    imagen: str | None = None


class ChatResponse(BaseModel):
    respuesta: str
    inmuebles: list[dict]
    handoff: bool
    temperatura: str
    lead_id: UUID
    atendido_por_humano: bool = False  # True = IA silenciada, asesor humano al mando
    mapa: MapaPreview | None = None  # tarjeta "Ver mapa interactivo"; None si no se ofreció mapa


def _procesar_turno(
    db: Session,
    tenant: Tenant,
    body: ChatRequest,
    origen: str | None,
) -> dict:
    """Lógica compartida: crea o recupera el lead y delega al orquestador."""
    if body.lead_id is None:
        lead = lead_service.create_lead(db, tenant, LeadCreate(origen=origen))
    else:
        lead = get_lead_or_404(body.lead_id, db, tenant)
    return orchestrator.responder(db, lead, body.mensaje)


@router.post("", response_model=ChatResponse)
def chat(
    body: ChatRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> dict:
    """Un turno de conversación con Aqua. Crea el lead si no se pasó `lead_id` (404 si el id no existe)."""
    return _procesar_turno(db, tenant, body, body.origen)


@router.post("/{origen}", response_model=ChatResponse)
def chat_con_origen(
    origen: _ORIGENES_VALIDOS,
    body: ChatRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> dict:
    """Turno de conversación con origen fijo en la URL. Si `lead_id` ya existe, el origen del path se ignora."""
    # Para leads nuevos usa el origen del path; para existentes el lead ya tiene su origen original.
    origen_efectivo = None if body.lead_id is not None else origen
    return _procesar_turno(db, tenant, body, origen_efectivo)
