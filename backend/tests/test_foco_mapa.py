"""Tests del fix de FOCO + mapa como tarjeta (orquestador). Sin red ni SDK."""

from app.agent import orchestrator
from app.agent.profiler import PerfilExtraido
from app.schemas.lead import LeadCreate
from app.services import lead_service


# --- Dobles del SDK (misma forma que test_agent/test_lugares) ---

class _BloqueTexto:
    type = "text"

    def __init__(self, text):
        self.text = text


class _BloqueTool:
    type = "tool_use"

    def __init__(self, id, name, input):
        self.id, self.name, self.input = id, name, input


class _Respuesta:
    def __init__(self, content, stop_reason):
        self.content, self.stop_reason = content, stop_reason


class _FakeMessages:
    def __init__(self, respuestas):
        self._r = list(respuestas)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._r.pop(0)


class _FakeClient:
    def __init__(self, respuestas):
        self.messages = _FakeMessages(respuestas)


def _lead(db):
    tenant = lead_service.get_or_create_default_tenant(db)
    return lead_service.create_lead(db, tenant, LeadCreate(origen="web"))


def _prep(monkeypatch, respuestas, ficha=None):
    monkeypatch.setattr(orchestrator, "_build_client", lambda: _FakeClient(respuestas))
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda h: PerfilExtraido())
    if ficha is not None:
        monkeypatch.setattr(orchestrator, "obtener_inmueble_por_codigo", lambda c: dict(ficha, inmueble_id=c))


def test_foco_descarta_busqueda_general(db, monkeypatch):
    """lugares_cerca(codigo) + buscar general en el mismo turno → SOLO la ficha en foco (0 arriendos)."""
    monkeypatch.setattr(orchestrator, "ejecutar_lugares_cerca", lambda a: ("Cerca: Éxito", []))
    monkeypatch.setattr(orchestrator, "ejecutar_buscar_inmuebles",
                        lambda a: ("otras", [{"inmueble_id": "48M"}, {"inmueble_id": "25M"}]))
    _prep(monkeypatch, [
        _Respuesta([_BloqueTool("t1", "lugares_cerca", {"codigo": "9718612"}),
                    _BloqueTool("t2", "buscar_inmuebles", {"query": "apartamentos las palmas"})], "tool_use"),
        _Respuesta([_BloqueTexto("Listo, eso hay cerca.")], "end_turn"),
    ], ficha={"titulo": "La Loma", "latitud": 6.2, "longitud": -75.5})

    out = orchestrator.responder(db, _lead(db), "me gusta la de la loma, ¿qué tiene cerca?")
    assert [i["inmueble_id"] for i in out["inmuebles"]] == ["9718612"]           # solo el foco
    assert not any(i["inmueble_id"] in ("48M", "25M") for i in out["inmuebles"])  # 0 arriendos


def test_marcador_mapa_se_extrae_y_limpia(db, monkeypatch):
    """[[MAPA:codigo]] → objeto mapa; el cliente no ve el marcador."""
    _prep(monkeypatch,
          [_Respuesta([_BloqueTexto("Cerca tienes muchas cosas 🗺️ [[MAPA:9718612]]")], "end_turn")],
          ficha={"titulo": "La Loma", "imagen_principal": "http://img/a.jpg", "latitud": 6.2, "longitud": -75.5})

    out = orchestrator.responder(db, _lead(db), "cuéntame")
    assert out["mapa"]["codigo"] == "9718612" and out["mapa"]["titulo"] == "La Loma"
    assert out["mapa"]["imagen"] == "http://img/a.jpg"
    assert "[[MAPA" not in out["respuesta"] and "🗺️" in out["respuesta"]


def test_respaldo_mapa_desde_lugares_cerca(db, monkeypatch):
    """Sin marcador pero con lugares_cerca(codigo) → el mapa usa ese codigo (respaldo determinista)."""
    monkeypatch.setattr(orchestrator, "ejecutar_lugares_cerca", lambda a: ("Cerca...", []))
    _prep(monkeypatch, [
        _Respuesta([_BloqueTool("t1", "lugares_cerca", {"codigo": "9718612"})], "tool_use"),
        _Respuesta([_BloqueTexto("Cerca tienes varias cosas (sin marcador).")], "end_turn"),
    ], ficha={"titulo": "La Loma", "latitud": 6.2, "longitud": -75.5})

    out = orchestrator.responder(db, _lead(db), "¿qué hay cerca?")
    assert out["mapa"]["codigo"] == "9718612"


def test_mapa_none_sin_coords(db, monkeypatch):
    """Ficha sin coords → mapa None (la página no puede dibujar), pero el marcador igual se limpia."""
    _prep(monkeypatch,
          [_Respuesta([_BloqueTexto("Mira 🗺️ [[MAPA:9718612]]")], "end_turn")],
          ficha={"titulo": "Sin coords"})  # sin latitud/longitud

    out = orchestrator.responder(db, _lead(db), "cuéntame")
    assert out["mapa"] is None
    assert "[[MAPA" not in out["respuesta"]


def test_handoff_descarta_mapa_y_tarjetas(db, monkeypatch):
    """Si el turno dispara handoff, el mensaje de handoff reemplaza al texto → sin mapa ni tarjetas huérfanas."""
    from app.agent.profiler import PerfilExtraido as _PE
    _prep(monkeypatch,
          [_Respuesta([_BloqueTexto("Con gusto, mira esto 🗺️ [[MAPA:9718612]]")], "end_turn")],
          ficha={"titulo": "La Loma", "latitud": 6.2, "longitud": -75.5})
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda h: _PE(pide_humano=True))  # pide humano

    out = orchestrator.responder(db, _lead(db), "quiero hablar con un asesor")
    assert out["handoff"] is True
    assert out["mapa"] is None and out["inmuebles"] == []   # descartados por el handoff
    assert "asesor" in out["respuesta"].lower()
