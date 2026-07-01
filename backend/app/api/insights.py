"""Endpoint del asistente de métricas para la gerencia (E08).

POST /insights/ask — Aqua responde preguntas de Claudia con tool-use real (Haiku 4.5).
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.insights_agent import responder_gerencia
from app.api.deps import tenant_actual
from app.core.db import get_db
from app.models.tenant import Tenant

router = APIRouter(prefix="/insights", tags=["insights"])


class InsightsRequest(BaseModel):
    pregunta: str = Field(min_length=1)


class InsightsResponse(BaseModel):
    respuesta: str
    datos: dict | None = None


@router.post("/ask", response_model=InsightsResponse)
def ask_insights(
    body: InsightsRequest,
    db: Session = Depends(get_db),
    tenant: Tenant = Depends(tenant_actual),
) -> InsightsResponse:
    """Claudia pregunta; Aqua responde con datos reales del CRM (tool-use Haiku 4.5)."""
    result = responder_gerencia(db, tenant, body.pregunta)
    return InsightsResponse(**result)
