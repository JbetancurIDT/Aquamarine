"""Tests de "¿qué hay cerca?" (E09·H8): geo.lugares_cerca + tool + dispatch del orquestador.

Sin red ni SDK: se mockean cargar_pois/cargar_metro, obtener_inmueble_por_codigo y el cliente Claude.
"""

from app.agent import orchestrator
from app.agent.profiler import PerfilExtraido
from app.agent.tools import ejecutar_lugares_cerca
import app.agent.tools as tools_mod
from app.rag import geo as geo_mod
from app.schemas.lead import LeadCreate
from app.services import lead_service


def _poi(lat, lon, nombre="", brand=""):
    return {"lat": lat, "lon": lon, "nombre": nombre, "brand": brand}


# --- geo.lugares_cerca (pura) ---

def test_lugares_cerca_orden_topn_y_omite_vacias(monkeypatch):
    monkeypatch.setattr(geo_mod, "cargar_metro", lambda: [])
    monkeypatch.setattr(geo_mod, "cargar_pois", lambda: {
        "supermercado": [
            _poi(6.201, -75.581, nombre="Éxito"),    # ~157 m
            _poi(6.205, -75.585, nombre="Carulla"),  # ~780 m
            _poi(6.40, -75.70, nombre="Lejano"),     # ~25 km → fuera del radio 1.5 km
        ],
        # sin colegio → esa categoría se OMITE
    })
    out = geo_mod.lugares_cerca(6.20, -75.58, top=3)
    assert list(out.keys()) == ["supermercado"]                 # colegio (vacío) omitido
    assert [x["nombre"] for x in out["supermercado"]] == ["Éxito", "Carulla"]  # orden asc; Lejano fuera
    assert all(isinstance(x["dist_m"], int) for x in out["supermercado"])


def test_lugares_cerca_etiqueta_nombre_brand_generico(monkeypatch):
    monkeypatch.setattr(geo_mod, "cargar_metro", lambda: [])
    monkeypatch.setattr(geo_mod, "cargar_pois", lambda: {
        "supermercado": [
            _poi(6.201, -75.581, nombre="Éxito"),       # usa nombre
            _poi(6.2012, -75.5812, brand="D1"),         # sin nombre → usa brand
            _poi(6.2014, -75.5814),                     # sin nombre ni brand → genérico
        ],
    })
    nombres = [x["nombre"] for x in geo_mod.lugares_cerca(6.20, -75.58, categoria="supermercado", top=5)["supermercado"]]
    assert "Éxito" in nombres and "D1" in nombres and "Supermercado" in nombres


def test_lugares_cerca_top_recorta(monkeypatch):
    monkeypatch.setattr(geo_mod, "cargar_metro", lambda: [])
    monkeypatch.setattr(geo_mod, "cargar_pois", lambda: {
        "supermercado": [_poi(6.200 + i * 0.0001, -75.58, nombre=f"S{i}") for i in range(6)],
    })
    assert len(geo_mod.lugares_cerca(6.20, -75.58, top=3)["supermercado"]) == 3


def test_lugares_cerca_dedup_por_nombre(monkeypatch):
    """Un mismo lugar mapeado como varios nodos OSM (mismo nombre, otras coords) → aparece UNA vez."""
    monkeypatch.setattr(geo_mod, "cargar_metro", lambda: [])
    monkeypatch.setattr(geo_mod, "cargar_pois", lambda: {
        "universidad": [
            _poi(6.201, -75.581, nombre="EAFIT"),   # ~157 m
            _poi(6.203, -75.583, nombre="EAFIT"),   # mismo nombre, otras coords → se descarta
            _poi(6.202, -75.582, nombre="UPB"),     # nombre distinto → entra al top
        ],
    })
    nombres = [x["nombre"] for x in geo_mod.lugares_cerca(6.20, -75.58, categoria="universidad", top=3)["universidad"]]
    assert nombres.count("EAFIT") == 1 and "UPB" in nombres  # dedup por nombre; el distinto no se desplaza


def test_lugares_cerca_sin_coords():
    assert geo_mod.lugares_cerca(None, -75.58) == {}


def test_lugares_cerca_metro_es_categoria(monkeypatch):
    monkeypatch.setattr(geo_mod, "cargar_pois", lambda: {})
    monkeypatch.setattr(geo_mod, "cargar_metro",
                        lambda: [{"lat": 6.201, "lon": -75.581, "nombre": "Poblado", "linea": "A"}])
    out = geo_mod.lugares_cerca(6.20, -75.58)
    assert out.get("metro") and out["metro"][0]["nombre"] == "Poblado"


# --- ejecutar_lugares_cerca (handler) ---

def test_ejecutar_lugares_cerca_con_coords(monkeypatch):
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo",
                        lambda c: {"inmueble_id": c, "latitud": 6.20, "longitud": -75.58})
    monkeypatch.setattr(tools_mod, "lugares_cerca", lambda lat, lon, categoria=None: {
        "supermercado": [{"nombre": "Éxito", "dist_m": 400}],
        "universidad": [{"nombre": "UPB", "dist_m": 500}],
    })
    texto, inms = ejecutar_lugares_cerca({"codigo": "9907677"})
    assert inms == []                                   # NO genera tarjetas
    assert "Éxito" in texto and "~400 m" in texto and "UPB" in texto and "~500 m" in texto
    assert "Supermercados" in texto and "Universidades" in texto


def test_ejecutar_lugares_cerca_sin_coords(monkeypatch):
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo", lambda c: {"inmueble_id": c})  # sin lat/lon
    texto, inms = ejecutar_lugares_cerca({"codigo": "X"})
    assert inms == [] and "no tengo la ubicación" in texto.lower()


def test_ejecutar_lugares_cerca_vacio_es_honesto(monkeypatch):
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo",
                        lambda c: {"latitud": 10.0, "longitud": -75.5})  # fuera del Valle → sin POIs
    monkeypatch.setattr(tools_mod, "lugares_cerca", lambda lat, lon, categoria=None: {})
    texto, inms = ejecutar_lugares_cerca({"codigo": "X"})
    assert inms == [] and "no afirmes" in texto.lower()


# --- dispatch del orquestador (dobles del SDK) ---

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


def test_orchestrator_despacha_lugares_cerca(db, monkeypatch):
    tenant = lead_service.get_or_create_default_tenant(db)
    lead = lead_service.create_lead(db, tenant, LeadCreate(origen="web"))

    llamadas = []
    monkeypatch.setattr(orchestrator, "ejecutar_lugares_cerca",
                        lambda args: (llamadas.append(args), ("Cerca: Éxito (~400 m)", []))[1])
    fake = _FakeClient([
        _Respuesta([_BloqueTool("t1", "lugares_cerca", {"codigo": "9907677"})], "tool_use"),
        _Respuesta([_BloqueTexto("Cerca tienes un Éxito.")], "end_turn"),
    ])
    monkeypatch.setattr(orchestrator, "_build_client", lambda: fake)
    monkeypatch.setattr(orchestrator, "extraer_perfil", lambda historial: PerfilExtraido())
    monkeypatch.setattr(orchestrator, "obtener_inmueble_por_codigo",
                        lambda c: {"inmueble_id": c, "titulo": "Foco", "latitud": 6.2, "longitud": -75.5})

    out = orchestrator.responder(db, lead, "¿qué hay cerca?")
    assert llamadas == [{"codigo": "9907677"}]     # se enrutó a lugares_cerca
    # Fix de FOCO: el turno de lugares_cerca muestra SOLO la tarjeta del inmueble en foco.
    assert [i["inmueble_id"] for i in out["inmuebles"]] == ["9907677"]
    assert out["mapa"] and out["mapa"]["codigo"] == "9907677"  # respaldo determinista del mapa
    assert "Éxito" in out["respuesta"]
    nombres_tools = [t["name"] for t in fake.messages.calls[0]["tools"]]
    assert "buscar_inmuebles" in nombres_tools and "lugares_cerca" in nombres_tools  # ambas expuestas
