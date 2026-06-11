"""Tests del router de métricas (E02 · T02.3.3): estructura estable + conteos + invariante."""

from datetime import datetime, timedelta, timezone

from app.models.lead import Lead
from app.models.mensaje import Mensaje


def test_overview_estructura_vacia(client):
    r = client.get("/metrics/overview")
    assert r.status_code == 200
    body = r.json()
    assert body["total_leads"] == 0
    assert body["por_origen"] == {"web": 0, "meta": 0, "metrocuadrado": 0, "fincaraiz": 0, "otros": 0}
    assert body["por_temperatura"] == {"caliente": 0, "tibio": 0, "frio": 0, "desconocido": 0, "otros": 0}
    assert body["por_estado"] == {
        "nuevo": 0, "contactado": 0, "calificado": 0, "negociando": 0,
        "cerrado_ganado": 0, "cerrado_perdido": 0, "descartado": 0, "otros": 0,
    }
    assert body["tiempo_primera_respuesta_seg"] is None
    assert body["conversion"] == {"lead_a_cita": 0.0, "cita_a_negociacion": 0.0}


def test_overview_conteos_cuadran(client):
    client.post("/leads", json={"origen": "web"})
    client.post("/leads", json={"origen": "web"})
    lid = client.post("/leads", json={"origen": "meta"}).json()["id"]
    client.patch(f"/leads/{lid}/estado", json={"estado": "contactado"})

    body = client.get("/metrics/overview").json()
    assert body["total_leads"] == 3
    assert body["por_origen"]["web"] == 2
    assert body["por_origen"]["meta"] == 1
    assert body["por_origen"]["fincaraiz"] == 0
    assert body["por_estado"]["nuevo"] == 2
    assert body["por_estado"]["contactado"] == 1
    assert body["por_temperatura"]["frio"] == 3


def test_overview_invariante_suma_igual_total(client):
    """Ningún lead se pierde: la suma de cada bucket == total_leads."""
    client.post("/leads", json={"origen": "web"})
    client.post("/leads", json={"origen": "meta"})
    body = client.get("/metrics/overview").json()
    assert sum(body["por_estado"].values()) == body["total_leads"]
    assert sum(body["por_origen"].values()) == body["total_leads"]
    assert sum(body["por_temperatura"].values()) == body["total_leads"]


def test_overview_tiempo_primera_respuesta(client, db):
    """Con timestamps deterministas: 60s entre crear el lead y la respuesta del agente."""
    lid = client.post("/leads", json={"origen": "web"}).json()["id"]
    client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "resp"})
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    db.query(Lead).filter(Lead.id == lid).update({Lead.creado_en: base})
    db.query(Mensaje).filter(Mensaje.lead_id == lid).update(
        {Mensaje.creado_en: base + timedelta(seconds=60)}
    )
    db.commit()
    assert client.get("/metrics/overview").json()["tiempo_primera_respuesta_seg"] == 60.0


def test_overview_tiempo_primera_respuesta_promedio(client, db):
    """Dos leads con deltas 60 y 120 → promedio 90.0."""
    base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    for delta in (60, 120):
        lid = client.post("/leads", json={"origen": "web"}).json()["id"]
        client.post(f"/leads/{lid}/mensajes", json={"rol": "agente", "contenido": "resp"})
        db.query(Lead).filter(Lead.id == lid).update({Lead.creado_en: base})
        db.query(Mensaje).filter(Mensaje.lead_id == lid).update(
            {Mensaje.creado_en: base + timedelta(seconds=delta)}
        )
    db.commit()
    assert client.get("/metrics/overview").json()["tiempo_primera_respuesta_seg"] == 90.0
