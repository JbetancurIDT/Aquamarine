"""Dependencias compartidas de la API (E02).

`tenant_actual`: en el MVP no hay auth, así que siempre devuelve el tenant por
defecto. Cuando exista auth, aquí se resolverá el tenant desde el token/request.
"""

from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.services import lead_service


def tenant_actual(db: Session = Depends(get_db)) -> Tenant:
    """Tenant del request. MVP: siempre el tenant por defecto (sin auth todavía)."""
    return lead_service.get_or_create_default_tenant(db)


def get_lead_or_404(lead_id: UUID, db: Session, tenant: Tenant) -> Lead:
    """Busca un lead del tenant por id o lanza 404 (acota por tenant: multitenant)."""
    lead = (
        db.query(Lead)
        .filter(Lead.id == lead_id, Lead.tenant_id == tenant.id)
        .first()
    )
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead no encontrado")
    return lead
