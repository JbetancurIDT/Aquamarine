"""Servicio de leads (E02 · T02.2.2).

Centraliza la lógica del ciclo de vida del lead **y la emisión de eventos** (cada
cambio relevante deja un `Evento`, que es la base de las métricas). Lo reutilizan
la API (E02) y, más adelante, el agente (E03).
"""

from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
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


def set_asesor(db: Session, lead: Lead, asesor_id) -> Lead:
    """Asigna o desasigna asesor al lead; emite `asesor_asignado`.

    Valida que el asesor exista y pertenezca al mismo tenant. `asesor_id=None` desasigna.
    Lanza `ValueError` si el asesor no existe o es de otro tenant.
    """
    from app.models.asesor import Asesor  # import local para evitar circular

    if asesor_id is not None:
        asesor = (
            db.query(Asesor)
            .filter(Asesor.id == asesor_id, Asesor.tenant_id == lead.tenant_id)
            .first()
        )
        if asesor is None:
            raise ValueError(f"Asesor no encontrado: {asesor_id}")

    anterior = str(lead.asesor_id) if lead.asesor_id else None
    lead.asesor_id = asesor_id
    _emitir_evento(db, lead, "asesor_asignado", {
        "asesor_id": str(asesor_id) if asesor_id else None,
        "anterior": anterior,
    })
    db.commit()
    db.refresh(lead)
    return lead


def asesor_con_menor_cola(db: Session, tenant_id, excluir=None) -> "Asesor | None":
    """Devuelve el asesor disponible con menos leads activos del tenant.

    Respeta el cap (MAX_LEADS_ACTIVOS_POR_ASESOR) como preferencia: primero elige
    asesores bajo el cap. Si todos superan el cap, igual devuelve el de menor cola
    (nunca deja el lead sin asesor solo por eso). Devuelve None si no hay disponibles.

    `excluir` (opcional): id de un asesor a descartar de la elección **si hay otra
    opción** (lo usa la reasignación para no caer en el mismo asesor). Si el único
    disponible es el excluido, devuelve None (no hay alternativa real).
    """
    from app.models.asesor import Asesor  # local para evitar circular

    asesores = (
        db.query(Asesor)
        .filter(Asesor.tenant_id == tenant_id, Asesor.disponible.is_(True))
        .all()
    )
    if excluir is not None:
        # Descarta el excluido; si no queda nadie, no hay alternativa → None.
        asesores = [a for a in asesores if a.id != excluir]
    if not asesores:
        return None

    asesor_ids = [a.id for a in asesores]
    conteos = dict(
        db.query(Lead.asesor_id, func.count(Lead.id))
        .filter(
            Lead.asesor_id.in_(asesor_ids),
            Lead.estado.in_(["calificado", "negociando"]),
        )
        .group_by(Lead.asesor_id)
        .all()
    )

    cap = settings.MAX_LEADS_ACTIVOS_POR_ASESOR
    bajo_cap = [a for a in asesores if conteos.get(a.id, 0) < cap]
    pool = bajo_cap if bajo_cap else asesores
    return min(pool, key=lambda a: conteos.get(a.id, 0))


def tomar_lead(db: Session, lead: Lead, asesor_id) -> Lead:
    """El asesor humano toma el chat: apaga la IA, despedida, estado → negociando.

    Idempotente: si `atendido_por_humano` ya es True, devuelve el lead sin cambios.
    """
    from app.models.asesor import Asesor

    asesor = (
        db.query(Asesor)
        .filter(Asesor.id == asesor_id, Asesor.tenant_id == lead.tenant_id)
        .first()
    )
    if asesor is None:
        raise ValueError(f"Asesor no encontrado: {asesor_id}")

    if lead.atendido_por_humano:
        return lead  # ya tomado, idempotente

    now = datetime.now(timezone.utc)
    lead.asesor_id = asesor_id
    lead.atendido_por_humano = True
    lead.notificaciones_count = 0
    lead.ultima_notificacion_en = None
    if lead.asignado_en is None:
        lead.asignado_en = now

    # Mueve el estado a negociando si no estaba ya en un estado terminal
    if lead.estado in ("nuevo", "contactado", "calificado"):
        estado_anterior = lead.estado
        lead.estado = "negociando"
        _emitir_evento(db, lead, "estado_cambiado", {"anterior": estado_anterior, "nuevo": "negociando"})

    # Mensaje de despedida de la IA
    despedida = (
        f"Con gusto te dejo con {asesor.nombre}, uno de nuestros asesores, "
        "que seguirá ayudándote personalmente. ¡Fue un placer acompañarte hasta aquí! 🙌"
    )
    db.add(Mensaje(lead_id=lead.id, rol="agente", contenido=despedida))
    _emitir_evento(db, lead, "tomado_por_humano", {
        "asesor_id": str(asesor_id),
        "nombre_asesor": asesor.nombre,
    })

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
