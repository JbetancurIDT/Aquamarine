"""Servicio de leads (E02 · T02.2.2).

Centraliza la lógica del ciclo de vida del lead **y la emisión de eventos** (cada
cambio relevante deja un `Evento`, que es la base de las métricas). Lo reutilizan
la API (E02) y, más adelante, el agente (E03).
"""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.enums import Estado, Temperatura
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.models.tenant import Tenant
from app.schemas.lead import LeadCreate, LeadUpdate
from app.schemas.mensaje import MensajeCreate

DEFAULT_TENANT_NOMBRE = "Aquamarine Group"


def get_or_create_default_tenant(db: Session) -> Tenant:
    """Devuelve el tenant por defecto del MVP (lo crea la primera vez).

    A prueba de carreras: si dos requests concurrentes intentan crearlo, el UNIQUE
    de `tenants.nombre` hace fallar al segundo INSERT; ese perdedor hace rollback y
    recupera la fila que ganó la carrera.
    """
    tenant = db.query(Tenant).filter(Tenant.nombre == DEFAULT_TENANT_NOMBRE).first()
    if tenant is not None:
        return tenant
    tenant = Tenant(nombre=DEFAULT_TENANT_NOMBRE)
    db.add(tenant)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return db.query(Tenant).filter(Tenant.nombre == DEFAULT_TENANT_NOMBRE).first()
    db.refresh(tenant)
    return tenant


def _emitir_evento(db: Session, lead: Lead, tipo: str, payload: dict | None = None) -> Evento:
    """Registra un evento asociado al lead (no hace commit: lo hace quien llama)."""
    evento = Evento(lead_id=lead.id, tipo=tipo, payload=payload)
    db.add(evento)
    return evento


def create_lead(db: Session, tenant: Tenant, datos: LeadCreate) -> Lead:
    """Crea un lead con los defaults del negocio y emite `lead_creado`."""
    lead = Lead(
        tenant_id=tenant.id,
        origen=datos.origen.value if datos.origen is not None else None,
        nombre=datos.nombre,
        contacto=datos.contacto,
        idioma=datos.idioma,
        perfil=datos.perfil or {},
    )
    db.add(lead)
    db.flush()  # asigna lead.id (server_default gen_random_uuid vía RETURNING)
    _emitir_evento(db, lead, "lead_creado", {"origen": lead.origen})
    db.commit()
    db.refresh(lead)
    return lead


def update_lead(db: Session, lead: Lead, datos: LeadUpdate) -> Lead:
    """Actualiza campos editables del lead (no toca estado/score/temperatura)."""
    for campo, valor in datos.model_dump(exclude_unset=True).items():
        setattr(lead, campo, valor)
    db.commit()
    db.refresh(lead)
    return lead


def set_estado(db: Session, lead: Lead, nuevo_estado) -> Lead:
    """Valida y cambia el estado del lead; emite `estado_cambiado`."""
    estado = nuevo_estado.value if isinstance(nuevo_estado, Estado) else str(nuevo_estado)
    if estado not in {e.value for e in Estado}:
        raise ValueError(f"Estado inválido: {estado}")
    anterior = lead.estado
    lead.estado = estado
    _emitir_evento(db, lead, "estado_cambiado", {"anterior": anterior, "nuevo": estado})
    db.commit()
    db.refresh(lead)
    return lead


def set_score(db: Session, lead: Lead, score, temperatura) -> Lead:
    """Actualiza score + temperatura del lead; emite `score_actualizado`.

    `score` puede ser None (lead sin calificar, p.ej. handoff por solicitud → 'desconocido').
    """
    temp = temperatura.value if isinstance(temperatura, Temperatura) else str(temperatura)
    if temp not in {t.value for t in Temperatura}:
        raise ValueError(f"Temperatura inválida: {temp}")
    lead.score = int(score) if score is not None else None
    lead.temperatura = temp
    _emitir_evento(db, lead, "score_actualizado", {"score": lead.score, "temperatura": temp})
    db.commit()
    db.refresh(lead)
    return lead


def agregar_mensaje(db: Session, lead: Lead, datos: MensajeCreate) -> Mensaje:
    """Agrega un mensaje a la conversación del lead."""
    mensaje = Mensaje(
        lead_id=lead.id,
        rol=datos.rol.value,
        contenido=datos.contenido,
        meta=datos.metadata,
    )
    db.add(mensaje)
    db.commit()
    db.refresh(mensaje)
    return mensaje
