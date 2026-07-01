"""Tests del barrido periódico (E07 — sweep.py).

Prueba la lógica de `_sweep_once` directamente (sin asyncio): asignación,
notificación escalonada y reasignación.
"""

from datetime import datetime, timedelta, timezone

from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.schemas.lead import LeadCreate
from app.services import lead_service
from app.services.sweep import _sweep_once


def _crear_asesor(db, tenant, nombre: str = "Asesor Test") -> Asesor:
    a = Asesor(tenant_id=tenant.id, nombre=nombre, disponible=True)
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


# ---------------------------------------------------------------------------
# Asignación automática
# ---------------------------------------------------------------------------

def test_sweep_asigna_lead_sin_asesor(db):
    """_sweep_once asigna al asesor disponible un lead calificado sin asesor."""
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")

    _sweep_once(db)
    db.refresh(lead)

    assert lead.asesor_id == asesor.id
    ev = db.query(Evento).filter(Evento.tipo == "asignado").first()
    assert ev is not None


def test_sweep_no_asigna_sin_asesor_disponible(db):
    """Si no hay asesores disponibles, el lead queda sin asignar."""
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")

    _sweep_once(db)
    db.refresh(lead)

    assert lead.asesor_id is None


# ---------------------------------------------------------------------------
# Notificación escalonada
# ---------------------------------------------------------------------------

def test_sweep_emite_notificacion_cuando_caduco(db):
    """Cuando ha pasado el intervalo, _sweep_once emite evento notificacion."""
    from app.core.config import settings

    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")
    lead.asesor_id = asesor.id
    lead.temperatura = "caliente"
    # Simula que fue asignado hace más tiempo que el intervalo caliente
    intervalo = settings.notif_intervalos_seg["caliente"]
    lead.asignado_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    lead.notificaciones_count = 0
    db.commit()

    _sweep_once(db)
    db.refresh(lead)

    assert lead.notificaciones_count == 1
    ev = db.query(Evento).filter(Evento.tipo == "notificacion").first()
    assert ev is not None


def test_sweep_no_notifica_antes_del_intervalo(db):
    """Si no ha pasado el intervalo, no se emite notificación."""
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")
    lead.asesor_id = asesor.id
    lead.temperatura = "caliente"
    lead.asignado_en = datetime.now(timezone.utc)  # justo ahora → no ha caducado
    lead.notificaciones_count = 0
    db.commit()

    _sweep_once(db)
    db.refresh(lead)

    assert lead.notificaciones_count == 0


# ---------------------------------------------------------------------------
# Reasignación automática
# ---------------------------------------------------------------------------

def test_sweep_reasigna_a_otro_asesor(db):
    """Al superar NOTIF_MAX, reasigna al OTRO asesor (distinto), no al mismo."""
    from app.core.config import settings

    tenant = lead_service.get_or_create_default_tenant(db)
    asesor1 = _crear_asesor(db, tenant, "Asesor Uno")
    asesor2 = _crear_asesor(db, tenant, "Asesor Dos")

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")
    lead.asesor_id = asesor1.id
    lead.temperatura = "caliente"
    lead.notificaciones_count = settings.NOTIF_MAX_ANTES_REASIGNAR  # ya maxeado
    intervalo = settings.notif_intervalos_seg["caliente"]
    lead.asignado_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    lead.ultima_notificacion_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    db.commit()

    _sweep_once(db)
    db.refresh(lead)

    # Reasignado al asesor distinto, contadores reiniciados, evento emitido.
    assert lead.asesor_id == asesor2.id
    assert lead.notificaciones_count == 0
    ev = db.query(Evento).filter(Evento.tipo == "reasignado").first()
    assert ev is not None
    assert ev.payload["asesor_anterior"] == str(asesor1.id)
    assert ev.payload["asesor_nuevo"] == str(asesor2.id)


def test_sweep_no_reasigna_si_un_solo_asesor(db):
    """Con un solo asesor disponible NO reasigna al mismo: sin evento ni disculpa."""
    from app.core.config import settings

    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)

    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")
    lead.asesor_id = asesor.id
    lead.temperatura = "caliente"
    lead.notificaciones_count = settings.NOTIF_MAX_ANTES_REASIGNAR
    intervalo = settings.notif_intervalos_seg["caliente"]
    lead.asignado_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    lead.ultima_notificacion_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    db.commit()

    _sweep_once(db)
    db.refresh(lead)

    # No hay alternativa → sigue con el mismo asesor, sin evento reasignado ni disculpa.
    assert lead.asesor_id == asesor.id
    assert db.query(Evento).filter(Evento.tipo == "reasignado").count() == 0
    from app.models.mensaje import Mensaje
    disculpas = db.query(Mensaje).filter(
        Mensaje.lead_id == lead.id, Mensaje.rol == "agente",
        Mensaje.contenido.like("%reasignando%"),
    ).count()
    assert disculpas == 0


def test_sweep_distribuye_carga_entre_asesores(db, engine):
    """4 leads sin asesor + 2 asesores → 2 y 2 (no todos al mismo, anti-autoflush bug).

    Corre contra una sesión con `autoflush=False`, igual que el `SessionLocal` de
    producción (app/core/db.py). Es lo que hace válido el test: con `autoflush=True`
    (default del fixture `db`) tanto el código bueno como el bug rinden 2/2; solo con
    `autoflush=False` el bug del commit-único apila 4/0 y este test lo detecta.
    """
    from sqlalchemy.orm import sessionmaker

    from app.models.lead import Lead as LeadModel

    sf = sessionmaker(bind=engine, autoflush=False)()
    try:
        tenant = lead_service.get_or_create_default_tenant(sf)
        a1 = _crear_asesor(sf, tenant, "A1")
        a2 = _crear_asesor(sf, tenant, "A2")

        for _ in range(4):
            lead = lead_service.create_lead(sf, tenant, LeadCreate(origen="web"))
            lead_service.set_estado(sf, lead, "calificado")

        _sweep_once(sf)

        c1 = sf.query(LeadModel).filter(LeadModel.asesor_id == a1.id).count()
        c2 = sf.query(LeadModel).filter(LeadModel.asesor_id == a2.id).count()
        assert c1 == 2 and c2 == 2
    finally:
        sf.close()


def test_sweep_no_afecta_lead_tomado_por_humano(db):
    """Un lead ya tomado por humano no recibe notificaciones del sweep."""
    from app.core.config import settings

    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = _crear_asesor(db, tenant)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    lead_service.set_estado(db, lead, "calificado")
    lead.asesor_id = asesor.id
    lead.atendido_por_humano = True
    lead.temperatura = "caliente"
    intervalo = settings.notif_intervalos_seg["caliente"]
    lead.asignado_en = datetime.now(timezone.utc) - timedelta(seconds=intervalo + 5)
    lead.notificaciones_count = 0
    db.commit()

    _sweep_once(db)
    db.refresh(lead)

    assert lead.notificaciones_count == 0
    assert db.query(Evento).filter(Evento.tipo == "notificacion").count() == 0
