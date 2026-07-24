"""Test del endpoint del mapa `GET /rag/inmuebles/mapa` (feat/mapa-inmuebles).

Mockea Chroma (`app.api.rag.get_chroma_client`): solo devuelve los inmuebles CON coords e
incluye las `dist_<cat>_m` presentes."""

from unittest.mock import MagicMock

import app.api.rag as rag_mod
from app.models.lead import Lead
from app.services.lead_service import get_or_create_default_tenant


def _mock_chroma(monkeypatch, metas):
    col = MagicMock()
    col.get.return_value = {"ids": [m["inmueble_id"] for m in metas], "metadatas": metas}
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(rag_mod, "get_chroma_client", lambda: chroma)


def test_inmuebles_mapa_solo_con_coords_e_incluye_dist(client, monkeypatch):
    metas = [
        {"inmueble_id": "A", "titulo": "Apto Poblado", "tipo": "apartamento", "zona": "Poblado",
         "ciudad": "Medellín", "precio": 900_000_000, "habitaciones": 3, "banos": 2,
         "area_m2": 90, "imagen_principal": "http://img/a.jpg", "url_fuente": "http://u/a",
         "latitud": 6.21, "longitud": -75.57, "dist_metro_m": 600, "dist_super_m": 300},
        {"inmueble_id": "B", "titulo": "Sin coords", "ciudad": "Guatapé"},  # sin lat/lon → excluido
    ]
    col = MagicMock()
    col.get.return_value = {"ids": ["A", "B"], "metadatas": metas}
    chroma = MagicMock()
    chroma.get_or_create_collection.return_value = col
    monkeypatch.setattr(rag_mod, "get_chroma_client", lambda: chroma)

    r = client.get("/rag/inmuebles/mapa")
    assert r.status_code == 200
    inms = r.json()["inmuebles"]
    assert len(inms) == 1  # B (sin coords) queda fuera
    a = inms[0]
    assert a["inmueble_id"] == "A" and a["latitud"] == 6.21 and a["longitud"] == -75.57
    assert a["imagen_principal"] == "http://img/a.jpg"
    assert a["dist_metro_m"] == 600 and a["dist_super_m"] == 300
    assert "dist_clinica_m" not in a  # solo las distancias que existen


def test_inmuebles_mapa_vacio(client, monkeypatch):
    _mock_chroma(monkeypatch, [])
    r = client.get("/rag/inmuebles/mapa")
    assert r.status_code == 200 and r.json() == {"inmuebles": []}


def test_leads_zona_cuenta_demanda(client, db, monkeypatch):
    """leads_zona: cuenta leads por zona (tolerante) y por ciudad si el lead no tiene zona."""
    tenant = get_or_create_default_tenant(db)
    db.add(Lead(tenant_id=tenant.id, perfil={"zona": "El Poblado", "ciudad": "Medellín"}))
    db.add(Lead(tenant_id=tenant.id, perfil={"zona": "El Poblado", "ciudad": "Medellín"}))
    db.add(Lead(tenant_id=tenant.id, perfil={"ciudad": "Envigado"}))              # sin zona → por ciudad
    db.add(Lead(tenant_id=tenant.id, perfil={"zona": "cerca del metro"}))          # basura → no matchea
    db.commit()

    metas = [
        {"inmueble_id": "P", "titulo": "Apto", "zona": "Poblado", "ciudad": "Medellín",
         "latitud": 6.21, "longitud": -75.57},                                     # "El Poblado" ⊃ "Poblado"
        {"inmueble_id": "E", "titulo": "Casa", "zona": "Escobero", "ciudad": "Envigado",
         "latitud": 6.16, "longitud": -75.56},
    ]
    _mock_chroma(monkeypatch, metas)

    r = client.get("/rag/inmuebles/mapa")
    inms = {i["inmueble_id"]: i for i in r.json()["inmuebles"]}
    assert inms["P"]["leads_zona"] == 2   # 2 leads El Poblado (tolerante con "Poblado")
    assert inms["E"]["leads_zona"] == 1   # 1 lead Envigado por ciudad; el "cerca del metro" no cuenta
