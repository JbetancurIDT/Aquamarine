"""Demanda de leads por zona sobre el inventario (mapa de calor · feat/mapa-inmuebles).

Cuenta, por cada propiedad, cuántos leads del tenant tienen interés en su zona. Reusa la
**tolerancia de ubicación** de la búsqueda (`_cumple_ubicacion`/`_norm`), así "El Poblado" del lead
matchea una propiedad en "Poblado" o "El Poblado - Milla de Oro". Un mismo lead puede contar para
varias propiedades de la misma zona (correcto: "5 leads buscan en esta zona").
"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.rag.search import _cumple_ubicacion, _norm


def leads_por_ubicacion(db: Session, tenant_id: UUID, propiedades: list[dict]) -> list[int]:
    """Para cada propiedad (metadata de Chroma), nº de leads del tenant interesados en su zona.

    - Si el lead tiene `perfil.zona`, cuenta si `_cumple_ubicacion(prop, zona)` (tolerante). Valores
      de zona que no son una ubicación real (p. ej. "cerca del metro") simplemente no matchean → 0.
    - Si el lead NO tiene zona pero sí `perfil.ciudad`, cuenta por ciudad (`_norm` exacto).
    Devuelve una lista de enteros en el MISMO orden que `propiedades`.
    """
    perfiles = db.query(Lead.perfil).filter(Lead.tenant_id == tenant_id).all()
    intereses = [((p or {}).get("zona"), (p or {}).get("ciudad")) for (p,) in perfiles]

    conteos: list[int] = []
    for prop in propiedades:
        prop_ciudad = _norm(prop.get("ciudad"))
        n = 0
        for zona, ciudad in intereses:
            if zona:
                if _cumple_ubicacion(prop, zona):
                    n += 1
            elif ciudad and _norm(ciudad) == prop_ciudad:
                n += 1
        conteos.append(n)
    return conteos
