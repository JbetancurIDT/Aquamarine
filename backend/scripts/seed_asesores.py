#!/usr/bin/env python
"""Seed mínimo de asesores para que el handoff funcione en demo.

Crea 2 asesores disponibles si no existen (idempotente por nombre).
Uso desde la carpeta backend/:
    python scripts/seed_asesores.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.db import SessionLocal
from app.models.asesor import Asesor
from app.services.lead_service import get_or_create_default_tenant

ASESORES = [
    "Mateo Ángel",
    "Valentina Ruiz",
]


def seed() -> None:
    db = SessionLocal()
    try:
        tenant = get_or_create_default_tenant(db)
        for nombre in ASESORES:
            existe = (
                db.query(Asesor)
                .filter(Asesor.tenant_id == tenant.id, Asesor.nombre == nombre)
                .first()
            )
            if existe is None:
                asesor = Asesor(tenant_id=tenant.id, nombre=nombre, disponible=True)
                db.add(asesor)
                db.flush()
                print(f"[creado]  {nombre} → {asesor.id}")
            else:
                print(f"[existe]  {nombre} (id={existe.id})")
        db.commit()
        print("Seed completado.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
