#!/usr/bin/env python
"""Backfill de intención de compra idempotente (E11 · T11.2.2).

Rellena `perfil.intencion` en los leads que aún no la tienen, derivándola de forma
determinista con `derivar_intencion(perfil, temperatura)` (misma rúbrica de D26), y emite el
evento de auditoría `intencion_clasificada` por cada lead derivado. La escritura + el evento
los hace `lead_service.registrar_intencion` (único escritor de `perfil['intencion']`), que
mergea sin pisar otras claves.

Idempotente: una segunda corrida no deriva nada (los leads ya tienen `intencion`) → 0 eventos.
Sin red ni SDK: usa solo lo ya guardado en Postgres.

Uso (desde backend/):
    python scripts/backfill_intencion.py
    python scripts/backfill_intencion.py --dry-run
    python scripts/backfill_intencion.py --tenant "Aquamarine Group"
"""

import argparse
import os
import sys
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.agent.intencion import INTENCIONES, derivar_intencion
from app.core.db import SessionLocal
from app.models.lead import Lead
from app.models.tenant import Tenant
from app.services import lead_service


def _resolver_tenant(db, tenant_arg: str | None) -> Tenant:
    """Resuelve el tenant: por UUID, por nombre, o el default si no se pasa `--tenant`."""
    if not tenant_arg:
        return lead_service.get_or_create_default_tenant(db)
    try:
        t = db.query(Tenant).filter(Tenant.id == UUID(str(tenant_arg))).first()
        if t is not None:
            return t
    except (ValueError, TypeError):
        pass
    t = db.query(Tenant).filter(Tenant.nombre == tenant_arg).first()
    if t is None:
        raise SystemExit(f"[backfill_intencion] tenant no encontrado: {tenant_arg!r}")
    return t


def backfill(db, tenant: Tenant, dry_run: bool = False) -> dict:
    """Deriva y persiste `intencion` en los leads del tenant que no la tienen. Devuelve stats."""
    leads = db.query(Lead).filter(Lead.tenant_id == tenant.id).all()
    por_intencion = {k: 0 for k in INTENCIONES}
    stats = {
        "total": len(leads),
        "ya_tenian": 0,
        "derivados": 0,
        "por_intencion": por_intencion,
    }

    for lead in leads:
        perfil = lead.perfil or {}
        if perfil.get("intencion"):
            stats["ya_tenian"] += 1
            continue
        intencion = derivar_intencion(perfil, lead.temperatura)
        por_intencion[intencion] += 1
        stats["derivados"] += 1
        if not dry_run:
            # Persiste el merge + emite `intencion_clasificada` (siempre cambia: antes era None).
            lead_service.registrar_intencion(db, lead, intencion)

    return stats


def main() -> None:
    ap = argparse.ArgumentParser(description="Backfill de intención de compra idempotente (E11).")
    ap.add_argument(
        "--tenant", default=None,
        help="Nombre o UUID del tenant (default: el tenant por defecto del MVP).",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="No escribe ni emite eventos; solo reporta lo que haría.",
    )
    args = ap.parse_args()

    db = SessionLocal()
    try:
        tenant = _resolver_tenant(db, args.tenant)
        nombre = tenant.nombre  # captura antes de cerrar la sesión (evita lazy-load detached)
        stats = backfill(db, tenant, dry_run=args.dry_run)
    finally:
        db.close()

    modo = "DRY-RUN (sin escribir)" if args.dry_run else "aplicado"
    print(f"[backfill_intencion] tenant={nombre} · {modo}")
    print(f"  total leads         : {stats['total']}")
    print(f"  ya tenían intención : {stats['ya_tenian']}")
    print(f"  derivados           : {stats['derivados']}")
    for k in INTENCIONES:
        print(f"    - {k:11s}: {stats['por_intencion'][k]}")


if __name__ == "__main__":
    main()
