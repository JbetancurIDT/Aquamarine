"""Búsqueda semántica de inmuebles en Chroma (E01 · T01.4.1 · endurecida en E09).

Problema que resuelve: filtrar `tipo`/`zona`/`ciudad` con igualdad exacta `$eq` en Chroma
producía **0 resultados** aunque existieran inmuebles que calzaban (p.ej. pedir
`tipo="casa campestre"` cuando el inmueble es `tipo="casa"`, o "Las Palmas" cuando la zona
es "Alto de las Palmas"). Aqua entonces decía "no hay" — inaceptable.

Estrategia (tolerante + relax-and-retry):
1. En el `where` de Chroma van SOLO los filtros numéricos/confiables: `tenant_id`,
   `tipo_negocio`, `precio_min/max`, `habitaciones/banos` (≥), `es_lujo`.
2. `tipo`/`zona`/`ciudad` se inyectan en el TEXTO de la consulta (señal semántica) y se
   aplican como POST-FILTRO TOLERANTE: normalización sin acentos + `contains` + aliases de
   tipo (familias: casa↔finca↔campestre, apartamento↔apto↔penthouse, lote↔terreno).
3. Over-fetch (`_OVERFETCH`) y, si quedan < k, se RELAJA en orden (zona → tipo → precio ±15%)
   reintentando. Cada resultado se marca `coincidencia: "exacta"|"cercana"` (+ `motivo`) para
   que el agente lo comunique con honestidad. **Nunca** devuelve vacío si hay inmuebles dentro
   de precio/habitaciones.

`obtener_inmueble_por_codigo(codigo)` (R07) sin cambios: lookup exacto por id, sin embedding.
"""

import json
import unicodedata

from app.core.config import settings
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client

# Cuántos candidatos pedir a Chroma antes de post-filtrar y rankear.
_OVERFETCH = 20
# Ensanche relativo del precio en el último nivel de relajación (±15%).
_PRICE_RELAX = 0.15

# Grupos de alias de tipo: dentro de un grupo los términos son intercambiables para el
# POST-FILTRO (no para mostrar). Así "casa campestre"/"finca"/"casa de campo" no excluyen
# una "casa", y "penthouse"/"apto" cuentan como "apartamento".
_ALIAS_GRUPOS = [
    {"casa", "casa campestre", "casa de campo", "campestre", "finca", "chalet"},
    {"apartamento", "apto", "apartaestudio", "aparta estudio", "penthouse", "loft", "duplex"},
    {"lote", "terreno", "parcela"},
    {"local", "local comercial", "oficina", "consultorio", "bodega"},
]


def _norm(s) -> str:
    """Normaliza para comparar tolerante: minúsculas, sin acentos, sin espacios sobrantes."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return " ".join(s.lower().split())


def _sig_tokens(s) -> set[str]:
    """Tokens significativos (≥4 chars) del texto normalizado.

    Compara TIPOS por palabra completa, NO por substring: así un término corto ("lote")
    NO contamina otra familia aunque aparezca dentro de un término multipalabra.
    """
    return {w for w in _norm(s).split() if len(w) >= 4}


# Tokens significativos por grupo (precomputados): identifican la familia sin cruces de substring.
# Invariante deseado: ningún token se comparte entre grupos (familias disjuntas).
_GRUPO_TOKENS = [set().union(*(_sig_tokens(t) for t in grupo)) for grupo in _ALIAS_GRUPOS]


def _tipos_aceptados(tipo_pedido) -> set[str]:
    """Familia (normalizada) de tipos aceptable para el tipo pedido. Vacío si no se pidió tipo.

    El tipo pedido pertenece a un grupo si comparte un **token significativo** con él (no por
    substring): "casa campestre"→familia casa; "penthouse"→familia apartamento; "lote"→solo lote.
    """
    toks = _sig_tokens(tipo_pedido)
    if not toks:
        return set()
    aceptados: set[str] = set()
    for grupo, gtoks in zip(_ALIAS_GRUPOS, _GRUPO_TOKENS):
        if toks & gtoks:  # comparten un token significativo → misma familia
            aceptados |= {_norm(t) for t in grupo}
    return aceptados or {_norm(tipo_pedido)}  # tipo desconocido: usa el literal


def _cumple_tipo(meta: dict, tipo_pedido) -> bool:
    """True si el `tipo` del inmueble cae en la familia del tipo pedido (match por token, no substring)."""
    aceptados = _tipos_aceptados(tipo_pedido)
    if not aceptados:
        return True  # no se pidió tipo → no restringe
    cand = _norm(meta.get("tipo"))
    if not cand:
        return False
    if cand in aceptados:
        return True
    # Match por token significativo: evita falsos positivos por substring corto (lote↔casa).
    acc_toks: set[str] = set()
    for a in aceptados:
        acc_toks |= _sig_tokens(a)
    return bool(_sig_tokens(cand) & acc_toks)


def _cumple_ubicacion(meta: dict, lugar_pedido) -> bool:
    """True si el lugar pedido aparece (substring o token ≥4) en zona/ciudad/depto/dirección/título.

    Tolerante a acentos/casing y a variantes ("Las Palmas" ⊂ "Alto de las Palmas").
    """
    p = _norm(lugar_pedido)
    if not p:
        return True
    campos = [meta.get("zona"), meta.get("ciudad"), meta.get("departamento"),
              meta.get("direccion"), meta.get("titulo")]
    blob = " ".join(_norm(c) for c in campos if c)
    if not blob:
        return False
    if p in blob:
        return True
    # Token a token: solo palabras significativas (≥4 chars) para no matchear "las", "del", "san".
    tokens = [w for w in p.split() if len(w) >= 4]
    return any(w in blob for w in tokens)


def _where_duro(filtros: dict, tenant_id: str) -> dict:
    """`where` de Chroma SOLO con filtros numéricos/confiables (sin tipo/zona/ciudad como $eq)."""
    cond = [{"tenant_id": {"$eq": tenant_id}}]
    f = filtros or {}
    if f.get("tipo_negocio"):
        cond.append({"tipo_negocio": {"$eq": _norm(f["tipo_negocio"])}})
    if f.get("precio_max") is not None:
        cond.append({"precio": {"$lte": int(f["precio_max"])}})
    if f.get("precio_min") is not None:
        cond.append({"precio": {"$gte": int(f["precio_min"])}})
    if f.get("habitaciones") is not None:
        cond.append({"habitaciones": {"$gte": int(f["habitaciones"])}})
    if f.get("banos") is not None:
        cond.append({"banos": {"$gte": int(f["banos"])}})
    if f.get("es_lujo") is not None:
        cond.append({"es_lujo": {"$eq": bool(f["es_lujo"])}})
    return cond[0] if len(cond) == 1 else {"$and": cond}


def _query_texto(query: str, filtros: dict) -> str:
    """Refuerza el embedding: añade tipo/zona/ciudad al texto si no están ya en la consulta."""
    base = (query or "").strip()
    qn = _norm(base)
    extra = [str(filtros.get(k)) for k in ("tipo", "zona", "ciudad") if filtros.get(k)]
    faltan = [e for e in extra if _norm(e) and _norm(e) not in qn]
    combinado = (base + " " + " ".join(faltan)).strip()
    # query_texts no puede ir vacío: si no hay nada, deja un término genérico.
    return combinado or base or " ".join(extra) or "inmueble"


def _formatear_meta(meta: dict, relevancia: float | None = None) -> dict:
    """Copia la metadata de Chroma, añade relevancia y deserializa `imagenes` (JSON string)."""
    meta = dict(meta or {})
    if relevancia is not None:
        meta["relevancia"] = relevancia
    imagenes_raw = meta.get("imagenes")
    if isinstance(imagenes_raw, str):
        try:
            meta["imagenes"] = json.loads(imagenes_raw)
        except (ValueError, TypeError):
            meta["imagenes"] = []
    return meta


def _consultar(query_texto: str, where: dict, n: int) -> list[dict]:
    """Una consulta a Chroma → lista de metadatas con `relevancia` calculada (orden de Chroma)."""
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
    res = col.query(query_texts=[query_texto], n_results=n, where=where)
    ids   = (res.get("ids")        or [[]])[0]
    metas = (res.get("metadatas")  or [[]])[0]
    dists = (res.get("distances")  or [[]])[0]
    salida = []
    for i, _id in enumerate(ids):
        dist = dists[i] if i < len(dists) else None
        relevancia = round(1.0 / (1.0 + dist), 4) if dist is not None else None
        salida.append(_formatear_meta(metas[i], relevancia))
    return salida


def _ordenar(items: list[dict]) -> list[dict]:
    """Ordena por relevancia semántica descendente (None al final)."""
    return sorted(items, key=lambda c: c.get("relevancia") if c.get("relevancia") is not None else -1.0,
                  reverse=True)


def buscar_inmuebles(query: str, filtros: dict | None = None, k: int = 5) -> list[dict]:
    """Top-k inmuebles tolerante con relax-and-retry.

    Filtros numéricos duros (precio/habitaciones/baños/tipo_negocio/es_lujo) + `tipo`/`zona`
    como señal semántica y post-filtro tolerante. Si quedan < k, relaja en orden
    (zona → tipo → precio ±15%). Cada resultado trae `coincidencia: "exacta"|"cercana"` y
    `motivo`. Devuelve hasta `k`, nunca vacío si hay inmuebles dentro de precio/habitaciones.
    """
    filtros = filtros or {}
    tipo_pedido  = filtros.get("tipo")
    lugar_pedido = filtros.get("zona") or filtros.get("ciudad")
    qtext = _query_texto(query, filtros)

    candidatos = _consultar(qtext, _where_duro(filtros, settings.DEFAULT_TENANT_ID), _OVERFETCH)

    resultados: list[dict] = []
    vistos: set[str] = set()

    def _agregar(items: list[dict], coincidencia: str, motivo: str) -> None:
        for c in items:
            cid = c.get("inmueble_id")
            # Sin id (caso patológico): clave única por identidad para no colisionar str(None).
            clave = str(cid) if cid else f"__anon_{id(c)}"
            if clave in vistos:
                continue
            vistos.add(clave)
            c["coincidencia"] = coincidencia
            c["motivo"] = motivo
            resultados.append(c)

    # Nivel 0 — match exacto: familia de tipo + ubicación pedidos.
    exactos = [c for c in candidatos
               if _cumple_tipo(c, tipo_pedido) and _cumple_ubicacion(c, lugar_pedido)]
    _agregar(_ordenar(exactos), "exacta", "coincide con lo que pediste")
    if len(resultados) >= k:
        return resultados[:k]

    # Nivel 1 — relaja ZONA (mantiene el tipo si se pidió): misma categoría en otra zona.
    if lugar_pedido:
        solo_tipo = [c for c in candidatos if _cumple_tipo(c, tipo_pedido)]
        motivo_zona = (
            f"mismo tipo, en otra zona (pediste “{lugar_pedido}”)" if tipo_pedido
            else f"en otra zona (pediste “{lugar_pedido}”)"
        )
        _agregar(_ordenar(solo_tipo), "cercana", motivo_zona)
        if len(resultados) >= k:
            return resultados[:k]

    # Nivel 2 — relaja TIPO: cualquier candidato dentro de los filtros numéricos.
    if tipo_pedido:
        _agregar(_ordenar(candidatos), "cercana", "dentro de tu presupuesto, en otra categoría")
        if len(resultados) >= k:
            return resultados[:k]

    # Nivel 3 — ensancha PRECIO ±15% y reconsulta (último recurso antes de devolver poco).
    if filtros.get("precio_min") is not None or filtros.get("precio_max") is not None:
        amplio = dict(filtros)
        if filtros.get("precio_min") is not None:
            amplio["precio_min"] = int(int(filtros["precio_min"]) * (1 - _PRICE_RELAX))
        if filtros.get("precio_max") is not None:
            amplio["precio_max"] = int(int(filtros["precio_max"]) * (1 + _PRICE_RELAX))
        extra = _consultar(qtext, _where_duro(amplio, settings.DEFAULT_TENANT_ID), _OVERFETCH)
        _agregar(_ordenar(extra), "cercana", "precio un poco fuera de tu rango")

    return resultados[:k]


def obtener_inmueble_por_codigo(codigo: str) -> dict | None:
    """Lookup exacto por código (document id en Chroma). Respeta tenant_id. Sin embedding."""
    codigo = str(codigo).strip()
    if not codigo:
        return None
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
    res = col.get(
        ids=[codigo],
        where={"tenant_id": {"$eq": settings.DEFAULT_TENANT_ID}},
    )
    ids = res.get("ids") or []
    metas = res.get("metadatas") or []
    if not ids or not metas:
        return None
    return _formatear_meta(metas[0], relevancia=1.0)
