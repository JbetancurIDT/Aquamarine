"""Búsqueda semántica de inmuebles en Chroma (E01 · T01.4.1).

`buscar_inmuebles(query, filtros, k)` combina similitud semántica (embedding de la
consulta con la función por defecto de Chroma) con filtros de metadata. **Siempre**
filtra por `tenant_id` (multitenant desde el día 1).
"""

from app.core.config import settings
from app.rag.chroma_client import COLLECTION_NAME, get_chroma_client


def _construir_where(filtros: dict | None, tenant_id: str) -> dict:
    """Traduce filtros amigables a la sintaxis `where` de Chroma (combina con $and)."""
    cond = [{"tenant_id": {"$eq": tenant_id}}]
    f = filtros or {}
    if f.get("ciudad"):        cond.append({"ciudad": {"$eq": f["ciudad"]}})
    if f.get("zona"):          cond.append({"zona": {"$eq": f["zona"]}})
    if f.get("tipo"):          cond.append({"tipo": {"$eq": str(f["tipo"]).lower()}})
    if f.get("tipo_negocio"):  cond.append({"tipo_negocio": {"$eq": str(f["tipo_negocio"]).lower()}})
    if f.get("precio_max") is not None:   cond.append({"precio": {"$lte": int(f["precio_max"])}})
    if f.get("precio_min") is not None:   cond.append({"precio": {"$gte": int(f["precio_min"])}})
    if f.get("habitaciones") is not None: cond.append({"habitaciones": {"$gte": int(f["habitaciones"])}})
    if f.get("banos") is not None:        cond.append({"banos": {"$gte": int(f["banos"])}})
    if f.get("es_lujo") is not None:      cond.append({"es_lujo": {"$eq": bool(f["es_lujo"])}})
    # TODO: zona/ciudad son $eq exacto (la web usa "Poblado Campestre", no "El Poblado").
    # Más adelante: matching flexible (normalizar/aliases o búsqueda por substring).
    return cond[0] if len(cond) == 1 else {"$and": cond}


def buscar_inmuebles(query: str, filtros: dict | None = None, k: int = 5) -> list[dict]:
    """Devuelve hasta `k` inmuebles por similitud semántica + filtros, ordenados por relevancia."""
    col = get_chroma_client().get_or_create_collection(COLLECTION_NAME)
    where = _construir_where(filtros, settings.DEFAULT_TENANT_ID)
    res = col.query(query_texts=[query], n_results=k, where=where)
    ids   = (res.get("ids")        or [[]])[0]
    metas = (res.get("metadatas")  or [[]])[0]
    dists = (res.get("distances")  or [[]])[0]
    salida = []
    for i, _id in enumerate(ids):
        meta = dict(metas[i] or {})
        dist = dists[i] if i < len(dists) else None
        meta["relevancia"] = round(1.0 / (1.0 + dist), 4) if dist is not None else None
        salida.append(meta)
    return salida
