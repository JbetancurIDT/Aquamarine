"""Vocabulario congelado de la búsqueda por cercanía (E09 · T09.1.1).

**Única fuente de verdad** de los nombres de categoría, sus claves de metadata en Chroma
(`dist_<cat>_m`) y sus etiquetas legibles. El enriquecimiento (`geo.py`, `seed_geo.py`),
el esquema (`schemas/inmueble.py`), la búsqueda (`search.py`, E09·S4) y la tool
(`agent/tools.py`, E09·S5) **importan de aquí**; ningún otro archivo escribe estos strings
a mano. Así el filtro que escribe la distancia y el filtro que la consulta nunca divergen
(divergencia = "no hay nada cerca" siendo mentira).

Convención de coordenadas (decisión E09): **todos** los JSON y funciones de este proyecto
usan `lat`/`lon` (nunca `lng`). Los campos del inmueble en Chroma siguen siendo
`latitud`/`longitud` (schema E01, no se renombra); los datos geográficos nuevos usan `lat`/`lon`.
Archivos de datos (en `app/rag/data/`): `metro_estaciones.json` y `centroides_zona.json`.
"""

import unicodedata

# Clave de coords en los JSON de datos geográficos (POIs, centroides).
COORD_LAT_KEY = "lat"
COORD_LON_KEY = "lon"

# Nombres EXACTOS de los archivos de datos versionados (en app/rag/data/).
DATA_METRO_FILE = "metro_estaciones.json"
DATA_CENTROIDES_FILE = "centroides_zona.json"

# Los 7 slugs congelados de categoría → su clave de metadata plana en Chroma.
# El orden es estable (se usa para enums en la tool). NO agregar/renombrar sin
# migrar el backfill y los tests.
CERCANIA_KEYS: dict[str, str] = {
    "metro":            "dist_metro_m",
    "supermercado":     "dist_super_m",
    "centro_comercial": "dist_mall_m",
    "colegio":          "dist_colegio_m",
    "universidad":      "dist_universidad_m",
    "parque":           "dist_parque_m",
    "clinica":          "dist_clinica_m",
}

# Frase legible por categoría, para que Aqua diga "a ~600 m de una estación de metro".
ETIQUETA_CAT: dict[str, str] = {
    "metro":            "una estación de metro",
    "supermercado":     "un supermercado",
    "centro_comercial": "un centro comercial",
    "colegio":          "un colegio",
    "universidad":      "una universidad",
    "parque":           "un parque",
    "clinica":          "una clínica",
}


def _norm(s) -> str:
    """Normaliza para comparar/clavar tolerante: minúsculas, sin acentos, sin espacios sobrantes.

    Misma regla que `app.rag.search._norm` (se replica aquí para evitar el import circular:
    `search` importará este módulo en E09·S4, no al revés).
    """
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def clave_geocache(zona, ciudad) -> str:
    """Clave normalizada `"{zona}|{ciudad}"` para el centroide de un (barrio, municipio).

    Sin sufijo de departamento/país. Colapsa acentos y casing, así
    `"Santa Fe De Antioquia"` y `"Santa Fe de Antioquia"` caen en la misma clave.
    """
    return f"{_norm(zona)}|{_norm(ciudad)}"
