"""Tests de la búsqueda RAG tolerante + relax-and-retry (E09).

No requieren Chroma real: se mockea `app.rag.search.get_chroma_client` para que
`col.query` devuelva un conjunto de candidatos canónico (el `where` y el `query_texts`
se ignoran en el mock — lo que se prueba es el post-filtro/relajación/ranking en Python).
"""

from unittest.mock import MagicMock

import pytest

import app.agent.tools as tools_mod
from app.agent.tools import ejecutar_buscar_inmuebles
from app.core.config import settings
from app.rag import search as search_mod
from app.rag.search import (
    _cumple_tipo,
    _cumple_ubicacion,
    _tipos_aceptados,
    buscar_inmuebles,
)

T = settings.DEFAULT_TENANT_ID


def _inm(id_, titulo, tipo, zona, ciudad, precio, hab, banos, *, dist=0.2, **extra):
    return {
        "inmueble_id": id_, "tenant_id": T, "titulo": titulo, "tipo": tipo,
        "zona": zona, "ciudad": ciudad, "precio": precio,
        "habitaciones": hab, "banos": banos, "estado": "disponible",
        **extra,
    }, dist


# Inventario sintético inspirado en el inventario real (Medellín/Antioquia).
_9338102 = _inm("9338102", "Casa en Alto de las Palmas", "casa", "Alto de las Palmas", "Envigado",
                5_600_000_000, 4, 4, dist=0.10)
_9727715 = _inm("9727715", "Casa campestre en Las Palmas", "casa", "Las Palmas", "Medellín",
                7_500_000_000, 5, 5, dist=0.15)
_9637369 = _inm("9637369", "Finca en Guatapé", "finca", "Guatapé", "Antioquia",
                2_200_000_000, 4, 3, dist=0.30)
_9718612 = _inm("9718612", "Apartamento de lujo en El Poblado", "apartamento", "Poblado Campestre",
                "Medellín", 4_500_000_000, 3, 4, dist=0.20)
_10009887 = _inm("10009887", "Lote en Alto de las Palmas", "lote", "Alto de las Palmas", "Envigado",
                 950_000_000, 0, 0, dist=0.25)


def _pack(candidatos: list[tuple[dict, float]]) -> dict:
    """Empaqueta (metas + distancias) en el formato de respuesta de col.query."""
    metas = [c for c, _ in candidatos]
    dists = [d for _, d in candidatos]
    ids   = [c["inmueble_id"] for c in metas]
    return {"ids": [ids], "metadatas": [metas], "distances": [dists]}


def _mock_chroma(monkeypatch, candidatos: list[tuple[dict, float]]):
    """Hace que col.query devuelva `candidatos` (metas + distancias) en formato Chroma."""
    col = MagicMock()
    col.query.return_value = _pack(candidatos)
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(search_mod, "get_chroma_client", lambda: chroma)
    return col


def _mock_chroma_seq(monkeypatch, secuencia: list[list[tuple[dict, float]]]):
    """col.query devuelve un pack distinto por llamada (para ejercitar la reconsulta de relax)."""
    col = MagicMock()
    col.query.side_effect = [_pack(c) for c in secuencia]
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(search_mod, "get_chroma_client", lambda: chroma)
    return col


# ---------------------------------------------------------------------------
# Helpers de normalización / aliases
# ---------------------------------------------------------------------------

def test_aliases_tipo_casa_familia():
    """'casa campestre' acepta la familia casa/finca/campestre."""
    acept = _tipos_aceptados("casa campestre")
    assert "casa" in acept and "finca" in acept


def test_aliases_finca_incluye_casa():
    assert _cumple_tipo({"tipo": "casa"}, "finca") is True
    assert _cumple_tipo({"tipo": "finca"}, "casa") is True


def test_aliases_apartamento():
    assert _cumple_tipo({"tipo": "apartamento"}, "penthouse") is True
    assert _cumple_tipo({"tipo": "apartamento"}, "apto") is True


def test_tipo_distinto_no_matchea():
    """Un apartamento NO debe contar como casa."""
    assert _cumple_tipo({"tipo": "apartamento"}, "casa") is False


def test_tipo_no_contamina_lote_casa():
    """Regresión (E09): 'lote' y 'casa' son familias DISJUNTAS.

    El alias 'casa lote' + el match por substring bidireccional bridgeaba ambas familias
    (un lote calzaba como casa exacta y viceversa). Debe estar arreglado.
    """
    assert _cumple_tipo({"tipo": "lote"}, "casa") is False
    assert _cumple_tipo({"tipo": "casa"}, "lote") is False
    assert "casa" not in _tipos_aceptados("lote")
    assert "lote" not in _tipos_aceptados("casa")
    # 'terreno' pertenece a la familia lote, no a casa.
    assert _cumple_tipo({"tipo": "terreno"}, "lote") is True
    assert _cumple_tipo({"tipo": "terreno"}, "casa") is False


def test_ubicacion_substring_y_acentos():
    """'Las Palmas' ⊂ 'Alto de las Palmas'; acentos/casing no afectan."""
    assert _cumple_ubicacion({"zona": "Alto de las Palmas", "ciudad": "Envigado"}, "Las Palmas") is True
    assert _cumple_ubicacion({"zona": "Alto de las Palmas", "ciudad": "Envigado"}, "envigado") is True
    assert _cumple_ubicacion({"zona": "Poblado", "ciudad": "Medellín"}, "medellin") is True


def test_ubicacion_no_matchea_otra_zona():
    assert _cumple_ubicacion({"zona": "Poblado", "ciudad": "Medellín"}, "Cartagena") is False


# ---------------------------------------------------------------------------
# Caso real del bug: "casa campestre en Las Palmas, 5000-8000M, 4 hab"
# ---------------------------------------------------------------------------

def test_caso_real_devuelve_9338102_sin_codigo(monkeypatch):
    """El inmueble 9338102 (casa, Alto de las Palmas, 5.600M, 4 hab) debe aparecer
    para 'casa campestre en Las Palmas' SIN que el cliente dé el código."""
    _mock_chroma(monkeypatch, [_9338102, _9727715, _9718612, _10009887])

    res = buscar_inmuebles(
        "casa campestre en Las Palmas con jardín, 4 habitaciones",
        {"tipo": "casa campestre", "zona": "Las Palmas",
         "precio_min": 5_000_000_000, "precio_max": 8_000_000_000, "habitaciones": 4},
        k=3,
    )
    ids = [r["inmueble_id"] for r in res]
    assert "9338102" in ids
    # 9338102 calza exacto (tipo casa + "las palmas" ⊂ "alto de las palmas").
    objetivo = next(r for r in res if r["inmueble_id"] == "9338102")
    assert objetivo["coincidencia"] == "exacta"
    # El apartamento NO debería estar entre los exactos (tipo no casa).
    apto = next((r for r in res if r["inmueble_id"] == "9718612"), None)
    assert apto is None or apto["coincidencia"] == "cercana"


def test_finca_trae_casas_y_fincas(monkeypatch):
    """Pedir 'finca' trae casas y fincas como exactas (aliases); el apartamento, si entra
    para rellenar k, es solo alternativa cercana — nunca exacta."""
    _mock_chroma(monkeypatch, [_9338102, _9637369, _9718612])
    res = buscar_inmuebles("finca campestre", {"tipo": "finca"}, k=3)
    por_id = {r["inmueble_id"]: r for r in res}
    assert por_id["9338102"]["coincidencia"] == "exacta"   # casa (entra por la familia)
    assert por_id["9637369"]["coincidencia"] == "exacta"   # finca
    if "9718612" in por_id:                                  # apartamento: solo como relleno cercano
        assert por_id["9718612"]["coincidencia"] == "cercana"


# ---------------------------------------------------------------------------
# Relax-and-retry: nunca vacío si hay algo dentro de precio/habitaciones
# ---------------------------------------------------------------------------

def test_relaja_zona_devuelve_alternativas(monkeypatch):
    """Si no hay casas en la zona pedida pero sí en otra, devuelve alternativas cercanas."""
    _mock_chroma(monkeypatch, [_9338102, _9727715])  # casas en Envigado/Medellín
    res = buscar_inmuebles(
        "casa en Guatapé", {"tipo": "casa", "zona": "Guatapé"}, k=3,
    )
    assert len(res) >= 1
    assert all(r["coincidencia"] == "cercana" for r in res)
    assert all("zona" in r["motivo"] for r in res)


def test_no_devuelve_vacio_aunque_tipo_no_calce(monkeypatch):
    """Pide 'casa' y solo hay apartamentos dentro de precio → relaja tipo, NO vacío."""
    _mock_chroma(monkeypatch, [_9718612])  # solo un apartamento
    res = buscar_inmuebles("casa", {"tipo": "casa", "precio_max": 5_000_000_000}, k=3)
    assert len(res) == 1
    assert res[0]["coincidencia"] == "cercana"


def test_vacio_real_si_chroma_no_trae_nada(monkeypatch):
    """Si Chroma no devuelve ningún candidato, la lista es vacía (vacío honesto)."""
    _mock_chroma(monkeypatch, [])
    res = buscar_inmuebles("casa en la luna", {"tipo": "casa", "zona": "Luna"}, k=3)
    assert res == []


def test_lote_pedido_no_marca_casa_como_exacta(monkeypatch):
    """Pedir tipo='lote' con [lote, casa]: el lote es exacta; la casa, si entra a rellenar,
    es alternativa CERCANA — nunca 'exacta' (regresión de la contaminación lote↔casa)."""
    casa = _inm("C1", "Casa en Las Palmas", "casa", "Las Palmas", "Medellín",
                5_000_000_000, 4, 4, dist=0.10)
    lote = _inm("L1", "Lote en Las Palmas", "lote", "Las Palmas", "Medellín",
                900_000_000, 0, 0, dist=0.20)
    _mock_chroma(monkeypatch, [casa, lote])
    res = buscar_inmuebles("lote para construir en Las Palmas",
                           {"tipo": "lote", "zona": "Las Palmas"}, k=3)
    por_id = {r["inmueble_id"]: r for r in res}
    assert por_id["L1"]["coincidencia"] == "exacta"
    assert "C1" not in por_id or por_id["C1"]["coincidencia"] == "cercana"


def test_relax_precio_reconsulta_nivel3(monkeypatch):
    """Nivel 3: si nada calza en el rango original, ensancha precio ±15% y reconsulta → cercana."""
    casa = _inm("C9", "Casa un poco por encima del rango", "casa", "El Poblado", "Medellín",
                8_900_000_000, 4, 4, dist=0.10)
    # 1ª consulta (rango original) vacía; 2ª consulta (rango ±15%) trae la casa.
    col = _mock_chroma_seq(monkeypatch, [[], [casa]])
    res = buscar_inmuebles("casa en El Poblado",
                           {"tipo": "casa", "precio_max": 8_000_000_000}, k=3)
    assert col.query.call_count == 2
    # El where de la 2ª llamada lleva el precio ensanchado (+15% → 9_200_000_000).
    segundo_where = str(col.query.call_args_list[1].kwargs["where"])
    assert "9200000000" in segundo_where
    assert len(res) == 1
    assert res[0]["inmueble_id"] == "C9"
    assert res[0]["coincidencia"] == "cercana"
    assert "precio" in res[0]["motivo"]


def test_exacta_tiene_prioridad_sobre_cercana(monkeypatch):
    """Cuando hay exactas suficientes, no se rellenan con cercanas."""
    _mock_chroma(monkeypatch, [_9338102, _9727715, _9718612])
    res = buscar_inmuebles(
        "casa en Las Palmas", {"tipo": "casa", "zona": "Las Palmas"}, k=2,
    )
    # _9727715 (Las Palmas) y _9338102 (Alto de las Palmas) son casas que matchean la zona.
    assert len(res) == 2
    assert all(r["coincidencia"] == "exacta" for r in res)
    assert "9718612" not in [r["inmueble_id"] for r in res]  # el apto queda fuera


# ---------------------------------------------------------------------------
# where duro: tipo/zona NO van como $eq; numéricos sí
# ---------------------------------------------------------------------------

def test_where_no_incluye_tipo_ni_zona(monkeypatch):
    """El where de Chroma NO debe filtrar por tipo/zona/ciudad (causa de los 0 resultados)."""
    col = _mock_chroma(monkeypatch, [_9338102])
    buscar_inmuebles("casa", {"tipo": "casa", "zona": "Las Palmas", "ciudad": "Envigado",
                              "precio_max": 8_000_000_000, "habitaciones": 4}, k=3)
    where = col.query.call_args.kwargs["where"]
    where_str = str(where)
    assert "tipo" not in where_str
    assert "zona" not in where_str
    assert "ciudad" not in where_str
    # pero sí los numéricos y el tenant
    assert "precio" in where_str
    assert "habitaciones" in where_str
    assert "tenant_id" in where_str


# ---------------------------------------------------------------------------
# Handler: surface de exacta vs cercana en el texto para Claude
# ---------------------------------------------------------------------------

def test_handler_marca_alternativa_cercana(monkeypatch):
    """El texto que recibe Claude distingue alternativa cercana de match exacto."""
    monkeypatch.setattr(
        tools_mod, "buscar_inmuebles",
        lambda query, filtros, k=3: [
            {"inmueble_id": "9637369", "titulo": "Finca en Guatapé", "tipo": "finca",
             "zona": "Guatapé", "ciudad": "Antioquia", "precio": 2_200_000_000,
             "habitaciones": 4, "banos": 3, "coincidencia": "cercana",
             "motivo": "mismo tipo, en otra zona"},
        ],
    )
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "finca en Las Palmas",
                                                  "filtros": {"tipo": "finca", "zona": "Las Palmas"}})
    assert "ALTERNATIVA CERCANA" in texto
    assert "[COINCIDENCIA EXACTA]" not in texto          # todas son cercanas → no hay etiqueta exacta
    assert "sin decir que 'no hay nada'" in texto.lower()  # el encabezado instruye honestidad explícita
    assert "9637369" in texto
    assert len(inmuebles) == 1


def test_handler_vacio_no_dice_no_existe(monkeypatch):
    """Con búsqueda vacía, el texto NO afirma tajante que no existe nada."""
    monkeypatch.setattr(tools_mod, "buscar_inmuebles", lambda query, filtros, k=3: [])
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "casa en Marte"})
    assert inmuebles == []
    assert "sin resultados" in texto.lower()
    assert "no afirmes" in texto.lower()  # instrucción de honestidad para el agente
