"""Tests del lookup exacto por código (RAG) y la tool con campo `codigo`.

No requieren Chroma real: se mockea `get_chroma_client` a nivel de módulo.
"""

from unittest.mock import MagicMock

import pytest

import app.agent.tools as tools_mod
from app.agent.tools import ejecutar_buscar_inmuebles
from app.core.config import settings
from app.rag.search import obtener_inmueble_por_codigo


# Metadata de ejemplo que Chroma devolvería para el inmueble 9718612.
_META_9718612 = {
    "inmueble_id": "9718612",
    "tenant_id": settings.DEFAULT_TENANT_ID,
    "titulo": "Apto El Poblado",
    "tipo": "apartamento",
    "zona": "Poblado",
    "ciudad": "Medellín",
    "precio": 4500000000,
    "habitaciones": 3,
    "banos": 4,
    "estado": "disponible",
    "es_lujo": True,
}


def _mock_col_get(monkeypatch, ids_result: list, metas_result: list) -> MagicMock:
    """Sustituye get_chroma_client por un fake que responde al col.get() con los datos dados."""
    col = MagicMock()
    col.get.return_value = {"ids": ids_result, "metadatas": metas_result}
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr("app.rag.search.get_chroma_client", lambda: chroma)
    return col


# ---------------------------------------------------------------------------
# obtener_inmueble_por_codigo
# ---------------------------------------------------------------------------

def test_obtener_encontrado(monkeypatch):
    _mock_col_get(monkeypatch, ["9718612"], [_META_9718612])
    result = obtener_inmueble_por_codigo("9718612")
    assert result is not None
    assert result["inmueble_id"] == "9718612"
    assert result["ciudad"] == "Medellín"
    assert result["relevancia"] == 1.0


def test_obtener_no_encontrado(monkeypatch):
    _mock_col_get(monkeypatch, [], [])
    result = obtener_inmueble_por_codigo("0000000")
    assert result is None


def test_obtener_respeta_tenant(monkeypatch):
    """La llamada a col.get debe incluir where con el tenant_id correcto."""
    col = _mock_col_get(monkeypatch, [], [])
    obtener_inmueble_por_codigo("9718612")
    col.get.assert_called_once()
    kwargs = col.get.call_args.kwargs
    assert kwargs["where"]["tenant_id"]["$eq"] == settings.DEFAULT_TENANT_ID


def test_obtener_normaliza_int_a_str(monkeypatch):
    """El código puede llegar como int; debe normalizarse a str antes del lookup."""
    col = _mock_col_get(monkeypatch, ["9718612"], [_META_9718612])
    result = obtener_inmueble_por_codigo(9718612)
    assert result is not None
    kwargs = col.get.call_args.kwargs
    assert kwargs["ids"] == ["9718612"]


def test_obtener_deserializa_imagenes(monkeypatch):
    """imagenes almacenada como JSON string debe volver como lista."""
    import json
    meta_con_imgs = dict(_META_9718612, imagenes=json.dumps(["https://img1.jpg", "https://img2.jpg"]))
    _mock_col_get(monkeypatch, ["9718612"], [meta_con_imgs])
    result = obtener_inmueble_por_codigo("9718612")
    assert isinstance(result["imagenes"], list)
    assert result["imagenes"][0] == "https://img1.jpg"


# ---------------------------------------------------------------------------
# ejecutar_buscar_inmuebles con campo `codigo`
# ---------------------------------------------------------------------------

def test_tool_codigo_hit(monkeypatch):
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo", lambda codigo: _META_9718612)
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "", "codigo": "9718612"})
    assert "9718612" in texto
    assert len(inmuebles) == 1
    assert inmuebles[0]["inmueble_id"] == "9718612"


def test_tool_codigo_miss(monkeypatch):
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo", lambda codigo: None)
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "", "codigo": "0000000"})
    assert "0000000" in texto
    assert "no encontré" in texto.lower()
    assert inmuebles == []


def test_tool_codigo_como_int(monkeypatch):
    """El campo codigo puede llegar como int desde el modelo; debe funcionar igual."""
    monkeypatch.setattr(tools_mod, "obtener_inmueble_por_codigo", lambda codigo: _META_9718612)
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "", "codigo": 9718612})
    assert len(inmuebles) == 1


def test_tool_sin_codigo_usa_semantica(monkeypatch):
    """Sin campo codigo, el camino semántico sigue intacto (sin regresión)."""
    monkeypatch.setattr(
        tools_mod,
        "buscar_inmuebles",
        lambda query, filtros, k=3: [_META_9718612],
    )
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "apto en Poblado"})
    assert "Poblado" in texto
    assert len(inmuebles) == 1


def test_tool_sin_codigo_sin_resultados(monkeypatch):
    """Sin codigo y Chroma vacío, retorna el mensaje de sin resultados."""
    monkeypatch.setattr(tools_mod, "buscar_inmuebles", lambda query, filtros, k=3: [])
    texto, inmuebles = ejecutar_buscar_inmuebles({"query": "casa en Marte"})
    assert "sin resultados" in texto.lower()
    assert inmuebles == []
