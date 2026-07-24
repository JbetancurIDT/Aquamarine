"""Tests OFFLINE del agente Aqua (E03 · §6). NO llama a la API real de Anthropic.

Se mockea el cliente (`orchestrator._build_client`) para no gastar API, y en el caso
con tool también se mockea `app.rag.search.buscar_inmuebles` (vía `app.agent.tools`).
"""

import uuid

from app.agent import orchestrator, tools
from app.agent.profiler import PerfilExtraido, fusionar_perfil
from app.core.config import settings
from app.models.asesor import Asesor
from app.models.evento import Evento
from app.models.lead import Lead
from app.models.mensaje import Mensaje
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _mock_extraccion(monkeypatch, perfil: PerfilExtraido | None = None):
    """Mockea la extracción del perfil (sin API). Por defecto un perfil vacío."""
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda historial: perfil or PerfilExtraido())


# --- Dobles del SDK de Anthropic (imitan la forma de la respuesta de messages.create) ---

class _BloqueTexto:
    type = "text"

    def __init__(self, text: str):
        self.text = text


class _BloqueTool:
    type = "tool_use"

    def __init__(self, id: str, name: str, input: dict):
        self.id = id
        self.name = name
        self.input = input


class _Respuesta:
    def __init__(self, content: list, stop_reason: str):
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


def _nuevo_lead(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    return lead_service.create_lead(db, tenant, LeadCreate(origen="web"))


def _roles(db, lead_id):
    filas = (
        db.query(Mensaje).filter(Mensaje.lead_id == lead_id).order_by(Mensaje.creado_en).all()
    )
    return [m.rol for m in filas]


# --- Caso A: sin tool ---

def test_responder_sin_tool(db, monkeypatch):
    lead = _nuevo_lead(db)
    fake = _FakeClient([_Respuesta([_BloqueTexto("¡Hola! Soy Aqua. ¿Qué estás buscando?")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    out = orchestrator.responder(db, lead, "Hola")

    assert out["respuesta"].startswith("¡Hola! Soy Aqua")
    assert out["inmuebles"] == []
    assert out["handoff"] is False
    # Persistió el mensaje del lead y el del agente.
    assert _roles(db, lead.id) == ["lead", "agente"]
    # El request lleva el modelo de settings y el system con cache_control.
    call = fake.messages.calls[0]
    assert call["model"] == settings.ANTHROPIC_MODEL
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["tools"][0]["name"] == "buscar_inmuebles"


# --- Caso B: con tool ---

def test_responder_con_tool(db, monkeypatch):
    lead = _nuevo_lead(db)
    # Mock de la búsqueda RAG (no toca Chroma).
    monkeypatch.setattr(
        tools,
        "buscar_inmuebles",
        lambda query, filtros, k=3, preferencias=None: [
            {
                "inmueble_id": "9718612", "titulo": "Apto Poblado", "tipo": "apartamento",
                "zona": "Poblado", "ciudad": "Medellín", "precio": 4500000000,
                "habitaciones": 3, "banos": 4,
            }
        ],
    )
    # 1ª llamada → tool_use; 2ª llamada → end_turn con el texto final.
    fake = _FakeClient([
        _Respuesta([_BloqueTool("toolu_1", "buscar_inmuebles", {"query": "apto en Poblado"})], "tool_use"),
        _Respuesta([_BloqueTexto("Tengo una opción en El Poblado que te puede encantar.")], "end_turn"),
    ])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    out = orchestrator.responder(db, lead, "Quiero ver apartamentos en El Poblado")

    assert "Poblado" in out["respuesta"]
    assert [i["inmueble_id"] for i in out["inmuebles"]] == ["9718612"]
    # Hubo dos llamadas (la del tool_use y la final).
    assert len(fake.messages.calls) == 2
    # El mensaje del agente quedó persistido con la metadata de inmuebles.
    agente = (
        db.query(Mensaje).filter(Mensaje.lead_id == lead.id, Mensaje.rol == "agente").first()
    )
    assert agente.meta == {"inmuebles": ["9718612"]}


# --- Endpoint /chat ---

def test_chat_endpoint(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("¡Hola! Soy Aqua.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.post("/chat", json={"lead_id": lid, "mensaje": "Hola"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["respuesta"].startswith("¡Hola! Soy Aqua")
    assert body["inmuebles"] == []
    assert body["handoff"] is False
    assert body["lead_id"] == lid
    assert body["temperatura"] in ("frio", "tibio", "caliente")


def test_chat_crea_lead_si_no_se_pasa_id(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("¡Hola! Soy Aqua.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    r = client.post("/chat", json={"mensaje": "Hola, estoy mirando apartamentos"})
    assert r.status_code == 200, r.text
    lid = r.json()["lead_id"]
    assert lid
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(lid)).first()
    assert lead is not None
    assert lead.estado == "contactado"  # el agente movió nuevo → contactado
    # Se emitió `lead_creado`.
    assert db.query(Evento).filter(Evento.lead_id == lead.id, Evento.tipo == "lead_creado").count() == 1


def test_chat_continua_no_crea_otro_lead(client, db, monkeypatch):
    fake = _FakeClient([
        _Respuesta([_BloqueTexto("uno")], "end_turn"),
        _Respuesta([_BloqueTexto("dos")], "end_turn"),
    ])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    lid = client.post("/chat", json={"mensaje": "Hola"}).json()["lead_id"]
    n_leads = db.query(Lead).count()
    r2 = client.post("/chat", json={"lead_id": lid, "mensaje": "Sigo aquí"})
    assert r2.status_code == 200
    assert r2.json()["lead_id"] == lid
    assert db.query(Lead).count() == n_leads  # no creó un segundo lead


def test_perfil_y_scoring_integrados(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("Claro, con gusto.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    perfil_caliente = PerfilExtraido(
        zona="Poblado", presupuesto_max=5000000000, plazo="corto", tipo="apartamento",
        interes_urgencia="alta", inmueble_interes="9718612",
    )
    _mock_extraccion(monkeypatch, perfil_caliente)

    r = client.post("/chat", json={"mensaje": "Quiero ese apto en El Poblado, ~5000M, decido este mes"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["temperatura"] == "caliente"
    assert body["handoff"] is True

    lead = db.query(Lead).filter(Lead.id == uuid.UUID(body["lead_id"])).first()
    assert lead.temperatura == "caliente"
    assert lead.estado == "calificado"
    assert lead.score >= 70
    assert (
        db.query(Evento)
        .filter(Evento.lead_id == lead.id, Evento.tipo == "score_actualizado")
        .count()
        >= 1
    )


def test_fusionar_perfil_no_borra_previo(db):
    lead = _nuevo_lead(db)
    fusionar_perfil(db, lead, PerfilExtraido(nombre="Ana", zona="Poblado"))
    assert lead.nombre == "Ana"
    assert (lead.perfil or {}).get("zona") == "Poblado"

    # Un perfil nuevo con esos campos en None NO los borra.
    fusionar_perfil(db, lead, PerfilExtraido(ciudad="Medellín"))
    assert lead.nombre == "Ana"                       # se conserva
    assert lead.perfil.get("zona") == "Poblado"       # se conserva
    assert lead.perfil.get("ciudad") == "Medellín"    # se agrega


# --- Origen del lead (Parte 3) ---

def test_chat_sin_origen_queda_null(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("hola")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    lid = client.post("/chat", json={"mensaje": "hola"}).json()["lead_id"]
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(lid)).first()
    assert lead.origen is None


def test_chat_con_origen_lo_guarda(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("hola")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch)

    lid = client.post("/chat", json={"mensaje": "hola", "origen": "metrocuadrado"}).json()["lead_id"]
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(lid)).first()
    assert lead.origen == "metrocuadrado"


def test_fusionar_deduce_origen_si_lead_sin_origen(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen=None))
    assert lead.origen is None
    fusionar_perfil(db, lead, PerfilExtraido(origen="meta"))
    assert lead.origen == "meta"  # deducido por el agente


def test_fusionar_no_pisa_origen_de_url(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))
    fusionar_perfil(db, lead, PerfilExtraido(origen="meta"))
    assert lead.origen == "web"  # el de la URL NO se sobrescribe


# --- Mensaje de confirmación de handoff (Parte 3) ---

def test_handoff_por_solicitud_retorna_mensaje_confirmacion(db, monkeypatch):
    """Si pide_humano=True y el handoff se ejecuta, la respuesta es el mensaje de confirmación."""
    lead = _nuevo_lead(db)
    fake = _FakeClient([_Respuesta([_BloqueTexto("Claro, te conecto con un asesor.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch, PerfilExtraido(
        pide_humano=True, zona="Poblado", presupuesto_max=5000000000, plazo="corto",
    ))

    out = orchestrator.responder(db, lead, "quiero hablar con un humano")

    assert "conecté con uno de nuestros asesores" in out["respuesta"]
    assert out["handoff"] is True


def test_handoff_ya_ejecutado_no_sobrescribe_respuesta(db, monkeypatch):
    """Si el handoff ya estaba hecho (idempotente), texto_final no se sobreescribe con el mensaje de confirmación."""
    from app.agent.handoff import ejecutar_handoff_minimo as _handoff

    lead = _nuevo_lead(db)
    # Pre-ejecutar el handoff para que sea idempotente (retorna False la segunda vez).
    _handoff(db, lead, sin_calificar=True)

    fake = _FakeClient([_Respuesta([_BloqueTexto("Ya estás en contacto con un asesor.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch, PerfilExtraido(pide_humano=True))  # perfil vacío → sin_calificar

    out = orchestrator.responder(db, lead, "quiero un humano otra vez")

    # El handoff ya estaba hecho → hecho=False → no se sobreescribe texto_final
    assert "conecté con uno de nuestros asesores" not in out["respuesta"]
    assert out["handoff"] is True


# --- Handoff por solicitud (Parte 3) ---

def test_chat_pide_humano_dispara_handoff(client, db, monkeypatch):
    tenant = lead_service.get_or_create_default_tenant(db)
    asesor = Asesor(tenant_id=tenant.id, nombre="Daniela", disponible=True)
    db.add(asesor)
    db.commit()
    db.refresh(asesor)

    fake = _FakeClient([_Respuesta([_BloqueTexto("Claro, te conecto con un asesor.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch, PerfilExtraido(
        pide_humano=True, zona="Poblado", presupuesto_max=5000000000, plazo="corto",
    ))

    body = client.post("/chat", json={"mensaje": "quiero hablar con un asesor humano"}).json()
    assert body["handoff"] is True
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(body["lead_id"])).first()
    assert lead.estado == "calificado"
    assert lead.asesor_id == asesor.id
    assert db.query(Evento).filter(Evento.lead_id == lead.id, Evento.tipo == "handoff").count() == 1


def test_chat_pide_humano_sin_calificar(client, db, monkeypatch):
    fake = _FakeClient([_Respuesta([_BloqueTexto("Claro, te conecto.")], "end_turn")])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    _mock_extraccion(monkeypatch, PerfilExtraido(pide_humano=True))  # perfil vacío

    body = client.post("/chat", json={"mensaje": "no quiero una máquina, quiero un humano"}).json()
    assert body["handoff"] is True
    assert body["temperatura"] == "desconocido"
    lead = db.query(Lead).filter(Lead.id == uuid.UUID(body["lead_id"])).first()
    assert lead.score is None
    assert lead.temperatura == "desconocido"
    assert db.query(Evento).filter(Evento.lead_id == lead.id, Evento.tipo == "handoff").count() == 1


def test_chat_lead_inexistente_404(client):
    r = client.post("/chat", json={"lead_id": str(uuid.uuid4()), "mensaje": "Hola"})
    assert r.status_code == 404


def test_chat_mensaje_vacio_422(client):
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    r = client.post("/chat", json={"lead_id": lid, "mensaje": ""})
    assert r.status_code == 422
