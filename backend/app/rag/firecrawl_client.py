"""Cliente de Firecrawl para la ingesta de inmuebles (E01 · T01.1.x / T01.2.x).

La extracción de datos la hace **Firecrawl** (extracción estructurada JSON), NO Claude.
Este módulo expone:
- `scrape_url(url)` — markdown crudo de una ficha (smoke / depuración).
- `extract_property(url)` — datos estructurados de UNA ficha (formato `json` + schema).
- `to_inmueble(raw, url)` — mapper: combina lo extraído + campos fijos/derivados y
  valida con `InmuebleIn` (Pydantic).
- `map_properties(base_url)` — descubre las URLs de todas las fichas del sitio (endpoint
  `map`, barato; no scrapea).

Notas:
- La API key se lee de `settings.FIRECRAWL_API_KEY`. Si falta, se lanza un error claro
  en español en vez de un traceback confuso del SDK.
- Fuente real (R01 resuelto): `idealrealestate.com.co`. El base URL entra por parámetro,
  no se hardcodea en la lógica.
- Reintentos simples con backoff exponencial (1s, 2s, 4s) ante errores transitorios.
- Control de costo: `extract_property` usa `max_age` (cache 48h) para no re-scrapear
  fichas frescas y gastar créditos de más.
"""

import logging
import re
import time
from urllib.parse import urlparse

from firecrawl import Firecrawl

from app.core.config import settings
from app.schemas.inmueble import InmuebleIn

logger = logging.getLogger(__name__)

# Reintentos para errores transitorios / rate-limit: hasta 3 intentos con backoff
# exponencial de base 1s → esperas planificadas 1s, 2s, 4s entre intentos.
_MAX_INTENTOS = 3
_BACKOFF_BASE_S = 1.0


# Caracteres que suelen colarse al pegar una URL en la terminal y que la invalidan:
# comillas, paréntesis angulares, backticks y espacios en los extremos.
_ENVOLTORIOS = "<>\"'` \t\r\n"


def _normalize_url(url: str) -> str:
    """Limpia y valida la URL antes de scrapear.

    Tolera errores comunes al pegar desde la terminal (Firecrawl exige una URL
    bien formada con esquema; si no, responde 'Invalid URL'):
    - quita envoltorios como ``<'...'>`` o comillas alrededor;
    - agrega ``https://`` si la URL no trae esquema.

    Args:
        url: URL cruda recibida por parámetro.

    Returns:
        URL normalizada (con esquema), lista para Firecrawl.

    Raises:
        ValueError: si tras normalizar sigue sin parecer una URL válida.
    """
    if not url or not url.strip():
        raise ValueError("La URL está vacía")

    limpia = url.strip().strip(_ENVOLTORIOS)
    # Si no trae esquema http(s), asumimos https:// (la mayoría de portales lo soporta).
    if not re.match(r"^https?://", limpia, re.IGNORECASE):
        limpia = "https://" + limpia

    partes = urlparse(limpia)
    if not partes.netloc or "." not in partes.netloc:
        raise ValueError(
            f"URL inválida: {url!r} (normalizada a {limpia!r}). "
            "Pásala completa, p.ej. https://dominio.com/ruta-de-la-ficha"
        )
    return limpia


def _build_client() -> Firecrawl:
    """Crea el cliente Firecrawl validando que exista la API key.

    Raises:
        ValueError: si `FIRECRAWL_API_KEY` no está configurada en `backend/.env`.
    """
    api_key = (settings.FIRECRAWL_API_KEY or "").strip()
    if not api_key:
        raise ValueError("Falta FIRECRAWL_API_KEY en backend/.env")
    return Firecrawl(api_key=api_key)


def scrape_url(url: str) -> dict:
    """Scrapea UNA ficha de inmueble y devuelve su contenido en markdown.

    Args:
        url: URL de la ficha del inmueble a scrapear (entra por parámetro; nunca
            hardcodeada — ver riesgo R01).

    Returns:
        dict con al menos ``{"url": url, "markdown": <markdown limpio>}``.

    Raises:
        ValueError: si falta `FIRECRAWL_API_KEY` o la URL es inválida.
        RuntimeError: si el scrape sigue fallando tras agotar los reintentos.
    """
    url = _normalize_url(url)
    client = _build_client()

    ultimo_error: Exception | None = None
    for intento in range(1, _MAX_INTENTOS + 1):
        try:
            # Pedimos explícitamente el formato markdown y solo el contenido principal
            # (descarta menús, footers, etc. → markdown más limpio para el RAG).
            documento = client.scrape(url, formats=["markdown"], only_main_content=True)
            markdown = getattr(documento, "markdown", None)
            if not markdown:
                raise RuntimeError("Firecrawl devolvió un documento sin markdown")
            return {"url": url, "markdown": markdown}
        except Exception as exc:
            # Errores permanentes (bad request/auth/créditos/no encontrado) no se
            # reintentan: re-lanzar de una, sin gastar tiempo ni créditos en cada ficha.
            code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            if code in (400, 401, 402, 403, 404):
                raise
            ultimo_error = exc  # transitorio / rate-limit (429) / 5xx → backoff y reintento
            if intento < _MAX_INTENTOS:
                espera = _BACKOFF_BASE_S * (2 ** (intento - 1))  # 1s, 2s, 4s...
                logger.warning(
                    "Firecrawl scrape falló (intento %d/%d) para %s: %s. Reintento en %.0fs.",
                    intento, _MAX_INTENTOS, url, exc, espera,
                )
                time.sleep(espera)
            else:
                logger.error(
                    "Firecrawl scrape agotó los %d intentos para %s: %s",
                    _MAX_INTENTOS, url, exc,
                )

    raise RuntimeError(
        f"No se pudo scrapear {url} tras {_MAX_INTENTOS} intentos"
    ) from ultimo_error


# --------------------------------------------------------------------------- #
# Extracción estructurada (T01.1.1 / T01.2.1)                                  #
# --------------------------------------------------------------------------- #

# Cache de Firecrawl: si una URL se scrapeó hace < 48h, reusa el resultado y NO
# gasta crédito. 48h en milisegundos.
_CACHE_MAX_AGE_MS = 172_800_000

# Base URL por defecto del sitio fuente (web de Claudia). Configurable por parámetro.
BASE_URL_DEFECTO = "https://idealrealestate.com.co"

# Patrón de una FICHA de inmueble: slug + id numérico al final (sin query ni más rutas).
# Excluye listados (/s/...), páginas estáticas (/main-...), asesores, etc.
_FICHA_RE = re.compile(
    r"^https?://(www\.)?idealrealestate\.com\.co/[^/]+/\d+/?$", re.IGNORECASE
)

# Campos de CONTENIDO que se le piden a Firecrawl (los fijos/derivados los pone el mapper).
# Precio y administración se piden como string (vienen con "$" y puntos) y se limpian luego.
_EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string", "description": "Título del inmueble (encabezado H1)"},
        "tipo": {"type": "string", "description": "Tipo de inmueble: apartamento, casa, lote, etc."},
        "tipo_negocio": {"type": "string", "description": "Tipo de negocio: venta o arriendo"},
        "precio": {"type": "string", "description": "Precio tal cual aparece, ej. $4.500.000.000"},
        "pais": {"type": "string"},
        "departamento": {"type": "string"},
        "ciudad": {"type": "string"},
        "zona": {"type": "string", "description": "Zona o barrio"},
        "direccion": {"type": "string"},
        "habitaciones": {"type": "integer", "description": "Número de alcobas"},
        "banos": {"type": "integer", "description": "Número de baños"},
        "parqueaderos": {"type": "integer", "description": "Número de garajes/parqueaderos"},
        "area_construida": {"type": "number", "description": "Área construida en m2"},
        "area_privada": {"type": "number", "description": "Área privada en m2"},
        "estrato": {"type": "integer"},
        "pisos": {"type": "integer", "description": "Número de pisos"},
        "anio_construccion": {"type": "integer", "description": "Año de construcción"},
        "administracion": {"type": "string", "description": "Valor de administración, ej. $1.916.481"},
        "condicion": {"type": "string", "description": "Estado del inmueble: usado o nuevo"},
        "caracteristicas": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Características internas (balcón, jacuzzi, etc.)",
        },
        "descripcion": {"type": "string", "description": "Descripción adicional / detalles del inmueble"},
        "imagen_principal": {"type": "string", "description": "URL de la imagen principal"},
        "imagenes": {
            "type": "array",
            "items": {"type": "string"},
            "description": "URLs de las imágenes de la galería",
        },
        "latitud": {"type": "number"},
        "longitud": {"type": "number"},
    },
}

_EXTRACTION_PROMPT = (
    "Extrae los datos del inmueble de esta ficha inmobiliaria. Devuelve solo los "
    "campos que encuentres; si un dato no aparece, omítelo. Devuelve el precio y la "
    "administración tal como aparecen (con '$' y puntos). 'tipo_negocio' es 'venta' o "
    "'arriendo'; 'condicion' es 'usado' o 'nuevo'."
)


def extract_property(url: str) -> dict:
    """Extrae los datos estructurados (JSON) de UNA ficha de inmueble.

    Usa la extracción estructurada de Firecrawl (formato `json` + schema). Devuelve
    el dict crudo de **contenido** (sin los campos fijos/derivados, que los pone
    `to_inmueble`).

    Args:
        url: URL de la ficha (entra por parámetro; nunca hardcodeada).

    Returns:
        dict con los campos de contenido que Firecrawl logró extraer.

    Raises:
        ValueError: si falta `FIRECRAWL_API_KEY` o la URL es inválida.
        RuntimeError: si la extracción sigue fallando tras agotar los reintentos.
    """
    url = _normalize_url(url)
    client = _build_client()

    # FormatOption admite un dict; usamos el patrón documentado {"type": "json", ...}.
    formato_json = {
        "type": "json",
        "prompt": _EXTRACTION_PROMPT,
        "schema": _EXTRACTION_SCHEMA,
    }

    ultimo_error: Exception | None = None
    for intento in range(1, _MAX_INTENTOS + 1):
        try:
            documento = client.scrape(
                url,
                only_main_content=True,
                max_age=_CACHE_MAX_AGE_MS,  # cache 48h → ahorra créditos
                formats=[formato_json],
            )
            datos = getattr(documento, "json", None)
            if not datos:
                raise RuntimeError("Firecrawl no devolvió datos estructurados (json vacío)")
            return dict(datos)
        except Exception as exc:
            # Errores permanentes (bad request/auth/créditos/no encontrado) no se
            # reintentan: re-lanzar de una, sin gastar tiempo ni créditos en cada ficha.
            code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
            if code in (400, 401, 402, 403, 404):
                raise
            ultimo_error = exc  # transitorio / rate-limit (429) / 5xx → backoff y reintento
            if intento < _MAX_INTENTOS:
                espera = _BACKOFF_BASE_S * (2 ** (intento - 1))  # 1s, 2s, 4s...
                logger.warning(
                    "Firecrawl extract falló (intento %d/%d) para %s: %s. Reintento en %.0fs.",
                    intento, _MAX_INTENTOS, url, exc, espera,
                )
                time.sleep(espera)
            else:
                logger.error(
                    "Firecrawl extract agotó los %d intentos para %s: %s",
                    _MAX_INTENTOS, url, exc,
                )

    raise RuntimeError(
        f"No se pudo extraer {url} tras {_MAX_INTENTOS} intentos"
    ) from ultimo_error


# --------------------------------------------------------------------------- #
# Mapper: raw extraído → InmuebleIn (T01.2.1 / T01.2.2)                        #
# --------------------------------------------------------------------------- #

def _texto(valor, *, lower: bool = False) -> str | None:
    """Normaliza a texto limpio o None si viene vacío."""
    if valor is None:
        return None
    s = str(valor).strip()
    if not s:
        return None
    return s.lower() if lower else s


def _a_entero(valor) -> int | None:
    """Convierte a entero quitando todo lo no numérico: '$4.500.000.000' → 4500000000."""
    if valor is None:
        return None
    if isinstance(valor, bool):  # evita que True/False cuele como 1/0
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float):
        return int(round(valor))
    digitos = re.sub(r"[^\d]", "", str(valor))
    return int(digitos) if digitos else None


def _a_float(valor) -> float | None:
    """Convierte a float tolerando texto ('373.82 m²') y formato colombiano.

    Reglas para strings: punto = separador de miles, coma = decimal. Ejemplos:
    '1.234 m2' → 1234.0 · '373,82' → 373.82 · '12.345.678' → 12345678.0 ·
    '-75.56694' → -75.56694 (coordenada, un solo punto con >3 decimales = decimal).
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    s = str(valor).strip()
    m = re.search(r"-?[\d.,]+", s)  # primer token numérico; ignora "m2", "$", etc.
    if not m:
        return None
    num = m.group()
    if "," in num:  # formato CO: . miles, , decimal
        num = num.replace(".", "").replace(",", ".")
    elif num.count(".") > 1:  # 12.345.678 → todos los puntos son miles
        num = num.replace(".", "")
    else:  # un solo punto: si hay exactamente 3 dígitos detrás, son miles
        ent, _, dec = num.partition(".")
        if dec and len(dec) == 3 and ent.lstrip("-").isdigit():
            num = ent + dec
    try:
        return float(num)
    except ValueError:
        return None


def _a_lista(valor, *, split: bool = True) -> list[str]:
    """Normaliza a list[str] sin explotar un string en caracteres.

    La extracción JSON de Firecrawl (por LLM) a veces devuelve un campo declarado
    `array` como string ('Balcón, Jacuzzi' o una sola URL).

    Args:
        valor: lo recibido (lista, string o escalar).
        split: True separa un string por comas/saltos/; (características);
            False lo trata como un único elemento (URLs, que no se parten por coma).
    """
    if valor is None:
        return []
    if isinstance(valor, str):
        partes = re.split(r"[,\n;]", valor) if split else [valor]
    elif isinstance(valor, (list, tuple)):
        partes = valor
    else:
        partes = [valor]
    return [str(p).strip() for p in partes if p is not None and str(p).strip()]


def _id_desde_url(url: str) -> str | None:
    """El "Código" del inmueble = id numérico final de la URL (.../<slug>/<id>)."""
    m = re.search(r"/(\d+)/?$", url)
    return m.group(1) if m else None


def to_inmueble(raw: dict, url: str) -> InmuebleIn:
    """Combina lo extraído por Firecrawl con los campos fijos/derivados y valida.

    Args:
        raw: dict de contenido devuelto por `extract_property`.
        url: URL de la ficha (de aquí salen `inmueble_id` y `url_fuente`).

    Returns:
        `InmuebleIn` validado.

    Raises:
        ValueError: si la URL no trae el id, o si la validación Pydantic falla
            (registro inválido → el orquestador lo descarta sin romper la ingesta).
    """
    raw = raw or {}

    inmueble_id = _id_desde_url(url)
    if not inmueble_id:
        raise ValueError(f"No se pudo extraer el inmueble_id (código) de la URL: {url}")

    # Normaliza a lista ANTES de calcular es_lujo (un string no debe explotar en chars).
    caracteristicas = _a_lista(raw.get("caracteristicas"), split=True)
    es_lujo = any("lujo" in c.lower() for c in caracteristicas)

    area_construida = _a_float(raw.get("area_construida"))
    area_m2 = int(round(area_construida)) if area_construida is not None else None

    # Firecrawl a veces devuelve 0.0/0.0 cuando no halla la geo en el contenido principal.
    # (0,0) es el golfo de Guinea: no es una coordenada real de Colombia → ausente.
    latitud = _a_float(raw.get("latitud"))
    longitud = _a_float(raw.get("longitud"))
    if latitud == 0 and longitud == 0:
        latitud = longitud = None

    datos = {
        # fijos / derivados (los pone el mapper, no Firecrawl)
        "inmueble_id": inmueble_id,
        "tenant_id": settings.DEFAULT_TENANT_ID,
        "moneda": "COP",
        "estado": "disponible",
        "es_lujo": es_lujo,
        "area_m2": area_m2,
        "url_fuente": url,
        "fuente": "web",
        # contenido extraído
        "titulo": _texto(raw.get("titulo")),
        "tipo": _texto(raw.get("tipo"), lower=True),
        "tipo_negocio": _texto(raw.get("tipo_negocio"), lower=True),
        "precio": _a_entero(raw.get("precio")),
        "pais": _texto(raw.get("pais")),
        "departamento": _texto(raw.get("departamento")),
        "ciudad": _texto(raw.get("ciudad")),
        "zona": _texto(raw.get("zona")),
        "direccion": _texto(raw.get("direccion")),
        "habitaciones": _a_entero(raw.get("habitaciones")),
        "banos": _a_entero(raw.get("banos")),
        "parqueaderos": _a_entero(raw.get("parqueaderos")),
        "area_construida": area_construida,
        "area_privada": _a_float(raw.get("area_privada")),
        "estrato": _a_entero(raw.get("estrato")),
        "pisos": _a_entero(raw.get("pisos")),
        "anio_construccion": _a_entero(raw.get("anio_construccion")),
        "administracion": _a_entero(raw.get("administracion")),
        "condicion": _texto(raw.get("condicion"), lower=True),
        "caracteristicas": caracteristicas,
        "descripcion": _texto(raw.get("descripcion")),
        "imagen_principal": _texto(raw.get("imagen_principal")),
        "imagenes": _a_lista(raw.get("imagenes"), split=False),  # no partir URLs por coma
        "latitud": latitud,
        "longitud": longitud,
    }
    # Pydantic valida: si faltan campos requeridos (titulo, tipo, precio, ciudad, zona…)
    # lanza ValidationError y el orquestador descarta la ficha.
    return InmuebleIn(**datos)


# --------------------------------------------------------------------------- #
# Descubrimiento de fichas (T01.1.2)                                          #
# --------------------------------------------------------------------------- #

def map_properties(base_url: str = BASE_URL_DEFECTO) -> list[str]:
    """Descubre las URLs de todas las fichas de inmueble del sitio.

    Usa el endpoint `map` de Firecrawl (barato: lista URLs, no scrapea contenido) y
    filtra solo las fichas individuales (slug + id numérico), deduplicadas.

    Args:
        base_url: raíz del sitio a mapear (configurable; por defecto la web de Claudia).

    Returns:
        Lista deduplicada de URLs de fichas de inmueble.
    """
    base_url = _normalize_url(base_url)
    client = _build_client()

    # ignore_query_parameters reduce duplicados por ?utm=, ?id_property_type=, etc.
    resultado = client.map(base_url, ignore_query_parameters=True, limit=5000)
    enlaces = getattr(resultado, "links", None) or []

    urls: list[str] = []
    vistos: set[str] = set()
    for item in enlaces:
        # Cada link es un objeto con .url; toleramos también strings por robustez.
        cruda = getattr(item, "url", None) or (item if isinstance(item, str) else None)
        if not cruda:
            continue
        limpia = cruda.rstrip("/")
        if _FICHA_RE.match(limpia) and limpia not in vistos:
            vistos.add(limpia)
            urls.append(limpia)

    # TODO(R01-fallback): si `map` no trae todas las fichas, crawlear los listados
    # /s/ventas y /s/alquileres y extraer de ahí las URLs de cada inmueble.
    logger.info("map_properties: %d fichas descubiertas en %s", len(urls), base_url)
    return urls
