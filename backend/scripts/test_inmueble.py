"""Mini-test offline del schema + mapper (E01 · §6.1). NO gasta créditos de Firecrawl.

Cubre el caso "limpio" original y los casos de regresión de la revisión adversarial:
listas que llegan como string, precio ausente, y separador de miles colombiano.

Uso:
    cd backend && .venv/bin/python scripts/test_inmueble.py
"""

import sys
from pathlib import Path

# Permite ejecutar el script directamente: inserta la raíz de backend/ en sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.rag.firecrawl_client import to_inmueble  # noqa: E402

URL = "https://idealrealestate.com.co/apartamento-venta-poblado-campestre-medellin/9718612"

# Ficha real de referencia (Código 9718612). Simula lo que devuelve extract_property:
# precios con "$" y puntos, tipo capitalizado, longitud negativa, etc.
RAW_EJEMPLO = {
    "titulo": "Apartamento en Venta Poblado Campestre",
    "tipo": "Apartamento",
    "tipo_negocio": "Venta",
    "precio": "$4.500.000.000",
    "pais": "Colombia",
    "departamento": "Antioquia",
    "ciudad": "Medellín",
    "zona": "Poblado Campestre",
    "habitaciones": 3,
    "banos": 4,
    "parqueaderos": 3,
    "area_construida": 373.82,
    "area_privada": 350.0,
    "estrato": 6,
    "pisos": 7,
    "anio_construccion": 2005,
    "administracion": "$1.916.481",
    "condicion": "Usado",
    "caracteristicas": ["Balcón", "Jacuzzi", "Vista panorámica", "Inmueble de Lujo"],
    "descripcion": "Espectacular apartamento con vista panorámica en El Poblado.",
    "imagen_principal": "https://idealrealestate.com.co/img/9718612/principal.jpg",
    "imagenes": [
        "https://idealrealestate.com.co/img/9718612/1.jpg",
        "https://idealrealestate.com.co/img/9718612/2.jpg",
    ],
    "latitud": 6.18924,
    "longitud": -75.56694,
}


def caso_limpio() -> None:
    """Caso 5: la ficha completa de referencia sigue mapeando bien."""
    inmueble = to_inmueble(RAW_EJEMPLO, URL)

    assert inmueble.precio == 4500000000, inmueble.precio
    assert inmueble.ciudad == "Medellín", inmueble.ciudad
    assert inmueble.zona == "Poblado Campestre", inmueble.zona
    assert inmueble.habitaciones == 3, inmueble.habitaciones
    assert inmueble.banos == 4, inmueble.banos
    assert inmueble.tipo == "apartamento", inmueble.tipo
    assert inmueble.inmueble_id == "9718612", inmueble.inmueble_id
    assert inmueble.es_lujo is True, inmueble.es_lujo
    print("[caso limpio] mapeo de campos clave -> OK")

    assert inmueble.tenant_id == "aquamarine"
    assert inmueble.moneda == "COP" and inmueble.fuente == "web" and inmueble.estado == "disponible"
    assert inmueble.administracion == 1916481, inmueble.administracion
    assert inmueble.area_construida == 373.82 and inmueble.area_m2 == 374, inmueble.area_m2
    assert inmueble.longitud == -75.56694, inmueble.longitud  # signo negativo conservado
    assert inmueble.tipo_negocio == "venta" and inmueble.condicion == "usado"
    print("[caso limpio] fijos/derivados + limpieza de números -> OK")

    doc = inmueble.document
    assert "None" not in doc, doc
    assert "Poblado Campestre" in doc and "apartamento" in doc and "Jacuzzi" in doc, doc
    print("[caso limpio] document (texto a embedear) -> OK")

    meta = inmueble.metadata
    for clave, valor in meta.items():
        assert isinstance(valor, (str, int, float, bool)), f"{clave}={valor!r} no es primitivo"
    assert "descripcion" not in meta, "descripcion NO debe ir en metadata"
    assert meta["caracteristicas"] == "Balcón, Jacuzzi, Vista panorámica, Inmueble de Lujo"
    assert meta["imagenes"].startswith("["), "imagenes debe ser un JSON string"
    assert meta["es_lujo"] is True and meta["precio"] == 4500000000
    print("[caso limpio] metadata plana para Chroma -> OK")

    try:
        to_inmueble(RAW_EJEMPLO, "https://idealrealestate.com.co/sin-id-final/")
    except ValueError as exc:
        print(f"[caso limpio] URL sin id -> ValueError esperado ({exc})")
    else:
        raise AssertionError("Se esperaba ValueError cuando la URL no trae id numérico")


def caso_caracteristicas_string() -> None:
    """Caso 1: características como string no debe explotar en caracteres; es_lujo OK."""
    raw = {
        "titulo": "Apto con lujo",
        "ciudad": "Medellín",
        "caracteristicas": "Balcón, Jacuzzi, Inmueble de Lujo",
    }
    inmueble = to_inmueble(raw, URL)
    assert inmueble.caracteristicas == ["Balcón", "Jacuzzi", "Inmueble de Lujo"], inmueble.caracteristicas
    assert inmueble.es_lujo is True, inmueble.es_lujo
    print("[caso 1] caracteristicas string -> lista de 3 + es_lujo True -> OK")


def caso_imagenes_string() -> None:
    """Caso 2: imágenes como string (una sola URL) no se parte por la coma de la URL."""
    raw = {
        "titulo": "Apto con una imagen",
        "ciudad": "Medellín",
        "imagenes": "https://cdn.site.com/img1.jpg",
    }
    inmueble = to_inmueble(raw, URL)
    assert inmueble.imagenes == ["https://cdn.site.com/img1.jpg"], inmueble.imagenes
    print("[caso 2] imagenes string -> 1 elemento con la URL íntegra -> OK")


def caso_precio_none() -> None:
    """Caso 3: precio ausente ('Precio a consultar') NO descarta la ficha válida."""
    raw = {
        "titulo": "Lote campestre sin precio publicado",
        "ciudad": "Rionegro",
        "precio": "Precio a consultar",  # sin dígitos → None
    }
    inmueble = to_inmueble(raw, URL)  # no debe lanzar ValidationError
    assert inmueble.precio is None, inmueble.precio
    assert "precio" not in inmueble.metadata, "precio None debe omitirse de la metadata"
    assert "None" not in inmueble.document, inmueble.document
    print("[caso 3] precio None -> ficha NO descartada, precio omitido en metadata -> OK")


def caso_area_miles() -> None:
    """Caso 4: separador de miles colombiano en área ('1.234 m2' = 1234 m²)."""
    raw = {
        "titulo": "Casa grande",
        "ciudad": "Medellín",
        "area_construida": "1.234 m2",
    }
    inmueble = to_inmueble(raw, URL)
    assert inmueble.area_construida == 1234.0, inmueble.area_construida
    assert inmueble.area_m2 == 1234, inmueble.area_m2
    print("[caso 4] area '1.234 m2' -> 1234.0 / area_m2 1234 -> OK")


def main() -> int:
    caso_caracteristicas_string()
    caso_imagenes_string()
    caso_precio_none()
    caso_area_miles()
    caso_limpio()
    print("\n[OFFLINE] schema + mapper (con regresiones) OK ✅")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
