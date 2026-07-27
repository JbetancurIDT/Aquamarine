"""Tests del eje de intención de compra (E11 · comprador vs curioso). Sin red ni SDK.

Cubre: captura de `intencion` por el profiler, `derivar_intencion` (fallback determinista),
emisión del evento `intencion_clasificada` (solo al cambiar), el seam del orquestador y el
backfill idempotente. Rúbrica: [[Decisiones (Decision Log)]] D26.
"""

import importlib.util
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

import app.api.metrics as metrics_mod
from app.agent import insights_tools, orchestrator, profiler
from app.agent.intencion import INTENCIONES, derivar_intencion
from app.agent.profiler import PerfilExtraido
from app.api.metrics import _intencion_metrics
from app.models.evento import Evento
from app.rag.search import _norm
from app.schemas.lead import LeadCreate, LeadUpdate
from app.services import lead_service


# ---------------------------------------------------------------------------
# Dobles mínimos del SDK de Anthropic
# ---------------------------------------------------------------------------

class _BloqueTool:
    type = "tool_use"

    def __init__(self, name: str, input: dict):
        self.name = name
        self.input = input


class _BloqueTexto:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _Respuesta:
    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason


class _FakeMessages:
    def __init__(self, respuestas: list):
        self._respuestas = list(respuestas)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._respuestas.pop(0)


class _FakeClient:
    def __init__(self, respuestas: list):
        self.messages = _FakeMessages(respuestas)


def _lead(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    return lead_service.create_lead(db, tenant, LeadCreate(origen="web"))


def _n_eventos_intencion(db, lead_id=None) -> int:
    q = db.query(Evento).filter(Evento.tipo == "intencion_clasificada")
    if lead_id is not None:
        q = q.filter(Evento.lead_id == lead_id)
    return q.count()


# ===========================================================================
# A) Profiler: PerfilExtraido, schema de la tool y system de extracción
# ===========================================================================

def test_perfil_extraido_intencion_default_none_y_valida():
    assert PerfilExtraido().intencion is None
    assert PerfilExtraido(intencion="comprador").intencion == "comprador"
    with pytest.raises(ValidationError):
        PerfilExtraido(intencion="tibio")  # no es un valor válido del eje


def test_tool_schema_incluye_intencion_con_rubrica():
    props = profiler._EXTRACTION_TOOL["input_schema"]["properties"]
    assert "intencion" in props
    assert props["intencion"]["enum"] == ["comprador", "explorando", "curioso"]
    desc = props["intencion"]["description"].lower()
    assert "curioso" in desc and "comprador" in desc  # enseña la rúbrica


def test_extraction_system_ensena_intencion():
    s = profiler._EXTRACTION_SYSTEM.lower()
    assert "intencion" in s and "curioso" in s and "comprador" in s


def test_extraer_perfil_mapea_curioso(monkeypatch):
    resp = _Respuesta([_BloqueTool("extraer_perfil_cliente", {"intencion": "curioso"})])
    monkeypatch.setattr(profiler, "_build_client", lambda: _FakeClient([resp]))
    out = profiler.extraer_perfil([{"role": "user", "content": "¿cuánto vale ese apto del Poblado?"}])
    assert out.intencion == "curioso"


def test_extraer_perfil_mapea_comprador(monkeypatch):
    resp = _Respuesta([_BloqueTool("extraer_perfil_cliente", {
        "intencion": "comprador", "presupuesto_max": 800000000, "plazo": "corto",
    })])
    monkeypatch.setattr(profiler, "_build_client", lambda: _FakeClient([resp]))
    out = profiler.extraer_perfil([{"role": "user", "content": "hasta 800M, me mudo en 2 meses, ¿lo visito?"}])
    assert out.intencion == "comprador"


def test_profiler_persiste_interes_urgencia(db):
    # E11 rescató `interes_urgencia`: antes se extraía y se DESCARTABA; ahora vive en `perfil`.
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    profiler.fusionar_perfil(db, lead, PerfilExtraido(interes_urgencia="alta", tipo="apartamento"))
    db.refresh(lead)
    assert lead.perfil.get("interes_urgencia") == "alta"


# ===========================================================================
# B) derivar_intencion — fallback determinista (tabla de casos)
# ===========================================================================

@pytest.mark.parametrize("perfil,temp,esperado", [
    ({}, "caliente", "comprador"),                                            # temperatura caliente
    ({"presupuesto_max": 800000000, "plazo": "corto"}, "tibio", "comprador"), # presupuesto + plazo corto
    ({"presupuesto_min": 500000000, "plazo": "medio"}, "frio", "comprador"),  # presupuesto + plazo medio
    ({"inmueble_interes": "9996186"}, "frio", "comprador"),                   # inmueble concreto gana a curioso
    ({"plazo": "largo"}, "frio", "curioso"),                                  # frío, sin presupuesto, "mirando"
    ({}, "frio", "explorando"),                                               # frío pero plazo != largo
    ({"zona": "Poblado", "tipo": "apartamento"}, "tibio", "explorando"),      # señales, sin compromiso
    ({"presupuesto_max": 800000000, "plazo": "largo"}, "frio", "explorando"), # presupuesto pero largo/frío
    ({"plazo": "largo"}, "tibio", "explorando"),                             # curioso exige temperatura fría
    ({"plazo": "largo"}, "desconocido", "explorando"),                       # desconocido != frío
])
def test_derivar_intencion_tabla(perfil, temp, esperado):
    assert derivar_intencion(perfil, temp) == esperado


def test_derivar_intencion_siempre_valida():
    for temp in ("caliente", "tibio", "frio", "desconocido"):
        assert derivar_intencion({}, temp) in INTENCIONES
    # tolerante con perfil None
    assert derivar_intencion(None, "frio") in INTENCIONES


# ===========================================================================
# C) registrar_intencion — evento de auditoría (solo al cambiar)
# ===========================================================================

def test_registrar_intencion_emite_al_cambiar_con_payload(db):
    lead = _lead(db)
    lead_service.update_lead(db, lead, LeadUpdate(perfil={
        "zona": "El Poblado", "ciudad": "Medellín", "inmueble_interes": "9996186",
    }))
    ev = lead_service.registrar_intencion(db, lead, "curioso")
    assert ev is not None
    db.refresh(lead)
    assert lead.perfil["intencion"] == "curioso"
    eventos = (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "intencion_clasificada")
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].payload == {
        "intencion": "curioso", "zona": "El Poblado",
        "ciudad": "Medellín", "inmueble_interes": "9996186",
    }


def test_registrar_intencion_no_emite_si_igual(db):
    lead = _lead(db)
    lead_service.registrar_intencion(db, lead, "curioso")
    ev2 = lead_service.registrar_intencion(db, lead, "curioso")  # mismo valor → no cambia
    assert ev2 is None
    assert _n_eventos_intencion(db, lead.id) == 1


def test_registrar_intencion_reemite_al_cambiar(db):
    lead = _lead(db)
    lead_service.registrar_intencion(db, lead, "curioso")
    lead_service.registrar_intencion(db, lead, "comprador")  # curioso → comprador
    assert _n_eventos_intencion(db, lead.id) == 2
    db.refresh(lead)
    assert lead.perfil["intencion"] == "comprador"


def test_registrar_intencion_none_no_hace_nada(db):
    lead = _lead(db)
    ev = lead_service.registrar_intencion(db, lead, None)
    assert ev is None
    assert "intencion" not in (lead.perfil or {})
    assert _n_eventos_intencion(db, lead.id) == 0


# ===========================================================================
# D) Seam en el orquestador (post-turno, tras fusionar el perfil)
# ===========================================================================

def test_orchestrator_registra_intencion_con_payload_fusionado(db, monkeypatch):
    lead = _lead(db)
    fake = _FakeClient([_Respuesta([_BloqueTexto("Con gusto, agendamos la visita.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    # Comprador: zona/propiedad se fusionan y deben viajar en el payload del evento.
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda h: PerfilExtraido(
        intencion="comprador", zona="Envigado", ciudad="Medellín",
        inmueble_interes="9996186", presupuesto_max=800000000, plazo="corto",
    ))
    orchestrator.responder(db, lead, "busco en Envigado hasta 800M, me mudo en 2 meses, ¿lo visito?")
    db.refresh(lead)
    assert lead.perfil.get("intencion") == "comprador"
    eventos = (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "intencion_clasificada")
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].payload["intencion"] == "comprador"
    assert eventos[0].payload["zona"] == "Envigado"           # payload fusionado (no None)
    assert eventos[0].payload["inmueble_interes"] == "9996186"


def test_orchestrator_curioso_sin_datos_extra_no_interroga(db, monkeypatch):
    """Verificación (1): un '¿cuánto cuesta?' pelado → curioso, sin exigir más datos."""
    lead = _lead(db)
    fake = _FakeClient([_Respuesta(
        [_BloqueTexto("Ese apartamento está en $795M. ¿Quieres que te cuente más?")], "end_turn",
    )])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda h: PerfilExtraido(intencion="curioso"))
    orchestrator.responder(db, lead, "¿cuánto cuesta ese apto del Poblado?")
    db.refresh(lead)
    assert lead.perfil.get("intencion") == "curioso"
    eventos = (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "intencion_clasificada")
        .all()
    )
    assert len(eventos) == 1
    assert eventos[0].payload["intencion"] == "curioso"
    assert eventos[0].payload["zona"] is None  # no dio zona; el evento igual se emite


def test_orchestrator_sin_intencion_no_emite(db, monkeypatch):
    lead = _lead(db)
    fake = _FakeClient([_Respuesta([_BloqueTexto("¡Hola! ¿Qué estás buscando?")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda h: PerfilExtraido())  # intencion None
    orchestrator.responder(db, lead, "Hola")
    assert _n_eventos_intencion(db, lead.id) == 0


# ===========================================================================
# E) Backfill idempotente
# ===========================================================================

def _load_backfill():
    ruta = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "scripts", "backfill_intencion.py",
    )
    spec = importlib.util.spec_from_file_location("backfill_intencion", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_backfill_deriva_persiste_y_es_idempotente(db):
    bf = _load_backfill()
    tenant = lead_service.get_or_create_default_tenant(db)

    # frío + "solo mirando" → curioso
    l1 = lead_service.create_lead(db, tenant, LeadCreate(origen="web", perfil={"plazo": "largo"}))
    lead_service.set_score(db, l1, 10, "frio")
    # presupuesto + plazo corto (caliente) → comprador
    l2 = lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"presupuesto_max": 800000000, "plazo": "corto", "zona": "Envigado"},
    ))
    lead_service.set_score(db, l2, 80, "caliente")
    # ya tiene intención → intacto
    l3 = lead_service.create_lead(db, tenant, LeadCreate(origen="web", perfil={"intencion": "explorando"}))

    stats = bf.backfill(db, tenant)
    assert stats["total"] == 3
    assert stats["ya_tenian"] == 1
    assert stats["derivados"] == 2
    assert stats["por_intencion"]["curioso"] == 1
    assert stats["por_intencion"]["comprador"] == 1

    db.refresh(l1); db.refresh(l2); db.refresh(l3)
    assert l1.perfil["intencion"] == "curioso"
    assert l2.perfil["intencion"] == "comprador"
    assert l3.perfil["intencion"] == "explorando"  # no se tocó
    assert _n_eventos_intencion(db) == 2  # un evento por derivado

    # Idempotente: segunda corrida no deriva ni emite.
    stats2 = bf.backfill(db, tenant)
    assert stats2["derivados"] == 0
    assert stats2["ya_tenian"] == 3
    assert _n_eventos_intencion(db) == 2


def test_backfill_dry_run_no_escribe(db):
    bf = _load_backfill()
    tenant = lead_service.get_or_create_default_tenant(db)
    l1 = lead_service.create_lead(db, tenant, LeadCreate(origen="web", perfil={"plazo": "largo"}))
    lead_service.set_score(db, l1, 10, "frio")

    stats = bf.backfill(db, tenant, dry_run=True)
    assert stats["derivados"] == 1
    db.refresh(l1)
    assert "intencion" not in (l1.perfil or {})  # dry-run no persiste
    assert _n_eventos_intencion(db) == 0          # ni emite


def test_backfill_resuelve_tenant_por_defecto_y_nombre(db):
    bf = _load_backfill()
    tenant = lead_service.get_or_create_default_tenant(db)
    assert bf._resolver_tenant(db, None).id == tenant.id
    assert bf._resolver_tenant(db, tenant.nombre).id == tenant.id


# ===========================================================================
# F) Métrica segmentada — GET /metrics/intencion (H2)
# ===========================================================================

def _fl(perfil: dict, temp: str = "tibio"):
    """Lead falso mínimo para la agregación pura (solo .perfil y .temperatura)."""
    return SimpleNamespace(perfil=perfil, temperatura=temp)


def _mock_chroma_inventario(monkeypatch, metas):
    col = MagicMock()
    col.get.return_value = {"ids": [m.get("inmueble_id") for m in metas], "metadatas": metas}
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(metrics_mod, "get_chroma_client", lambda: chroma)


_INVENTARIO = [
    {"inmueble_id": "P1", "titulo": "Apto Poblado", "zona": "Poblado", "ciudad": "Medellín"},
    {"inmueble_id": "E1", "titulo": "Casa Escobero", "zona": "Escobero", "ciudad": "Envigado"},
]


def test_intencion_metrics_global_zona_propiedad_puro():
    leads = [
        _fl({"intencion": "comprador", "zona": "El Poblado", "inmueble_interes": "P1"}),
        _fl({"intencion": "curioso", "zona": "Poblado"}),           # tolerante → mismo bucket Poblado
        _fl({"intencion": "explorando", "zona": "Escobero"}),
        _fl({"intencion": "curioso", "zona": "cerca del metro"}),   # zona basura → solo global
        _fl({"intencion": "comprador"}),                            # sin zona → solo global
    ]
    m = _intencion_metrics(leads, _INVENTARIO)

    # Global cuenta a TODOS (incluye los sin-zona / zona-basura).
    assert m["total_leads"] == 5
    assert m["por_intencion"]["comprador"]["num"] == 2
    assert m["por_intencion"]["curioso"]["num"] == 2
    assert m["por_intencion"]["explorando"]["num"] == 1
    assert m["por_intencion"]["comprador"]["den"] == 5

    # Zona Poblado colapsa "El Poblado" + "Poblado" (match tolerante) = 2, 50% curiosos.
    pob = next(z for z in m["por_zona"] if _norm(z["zona"]) == "poblado")
    assert pob["total"] == 2 and pob["comprador"] == 1 and pob["curioso"] == 1
    assert pob["pct_curioso"] == 0.5

    # El curioso "cerca del metro" NO crea zona (no matchea inventario).
    assert all("metro" not in _norm(z["zona"]) for z in m["por_zona"])
    esc = next(z for z in m["por_zona"] if _norm(z["zona"]) == "escobero")
    assert esc["explorando"] == 1

    # por_propiedad agrupa por inmueble_interes y trae el título del inventario.
    p1 = next(p for p in m["por_propiedad"] if p["inmueble_interes"] == "P1")
    assert p1["comprador"] == 1 and p1["titulo"] == "Apto Poblado"


def test_intencion_metrics_usa_derivar_como_fallback():
    # Lead SIN perfil.intencion → se clasifica con derivar_intencion (presupuesto+plazo corto → comprador).
    leads = [_fl({"presupuesto_max": 800000000, "plazo": "corto"}, temp="caliente")]
    m = _intencion_metrics(leads, [])
    assert m["por_intencion"]["comprador"]["num"] == 1
    assert m["por_zona"] == [] and m["por_propiedad"] == []


def test_intencion_metrics_zona_no_sangra_por_titulo():
    # Regresión (H2): un lead de "El Poblado" NO cae en "El Tesoro" solo porque el TÍTULO de esa
    # propiedad mencione "El Poblado". El match es SOLO contra la zona del inventario.
    inventario = [
        {"inmueble_id": "T1", "titulo": "Apartamento en El Poblado, El Tesoro",
         "zona": "El Tesoro", "ciudad": "Medellín"},
        {"inmueble_id": "P1", "titulo": "Apto", "zona": "Poblado", "ciudad": "Medellín"},
    ]
    m = _intencion_metrics([_fl({"intencion": "curioso", "zona": "El Poblado"})], inventario)
    pob = next(z for z in m["por_zona"] if _norm(z["zona"]) == "poblado")
    assert pob["curioso"] == 1                                   # cuenta en Poblado (tolerante)
    assert all(_norm(z["zona"]) != "el tesoro" for z in m["por_zona"])  # NO sangra a El Tesoro


def test_endpoint_metrics_intencion(client, db, monkeypatch):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"intencion": "comprador", "zona": "El Poblado", "inmueble_interes": "P1"}))
    lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"intencion": "curioso", "zona": "Poblado"}))
    lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"intencion": "curioso", "zona": "cerca del metro"}))  # solo global
    _mock_chroma_inventario(monkeypatch, _INVENTARIO)

    r = client.get("/metrics/intencion")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total_leads"] == 3
    assert body["por_intencion"]["curioso"]["num"] == 2       # global cuenta al "cerca del metro"
    pob = next(z for z in body["por_zona"] if "poblado" in z["zona"].lower())
    assert pob["total"] == 2                                   # El Poblado + Poblado; NO el "cerca del metro"
    assert all("metro" not in z["zona"].lower() for z in body["por_zona"])
    p1 = next(p for p in body["por_propiedad"] if p["inmueble_interes"] == "P1")
    assert p1["comprador"] == 1


def test_insights_tool_intencion_por_zona(db, monkeypatch):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"intencion": "curioso", "zona": "Poblado"}))
    lead_service.create_lead(db, tenant, LeadCreate(
        origen="web", perfil={"intencion": "comprador", "zona": "Escobero"}))
    _mock_chroma_inventario(monkeypatch, _INVENTARIO)

    # Sin zona → global + todas las zonas.
    full = insights_tools.ejecutar_tool("intencion_por_zona", {}, db, tenant)
    assert full["total_leads"] == 2
    assert {z["zona"] for z in full["por_zona"]} == {"Poblado", "Escobero"}

    # Con zona "El Poblado" (tolerante) → filtra a Poblado.
    solo = insights_tools.ejecutar_tool("intencion_por_zona", {"zona": "El Poblado"}, db, tenant)
    assert solo["zona_consultada"] == "El Poblado"
    assert [z["zona"] for z in solo["por_zona"]] == ["Poblado"]
    assert solo["por_zona"][0]["curioso"] == 1
