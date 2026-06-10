"""Modelos SQLAlchemy (E00 · T00.2.2).

Por ahora no hay modelos de datos reales: se agregan desde E02 (Backend Core).
Este módulo reexporta `Base` para que Alembic descubra el metadata al hacer
`--autogenerate`. A medida que se creen modelos, impórtalos aquí para que queden
registrados en `Base.metadata`.

Convención del proyecto: todo modelo futuro debe incluir una columna `tenant_id`
desde su creación (multitenant-ready). Ver [[Arquitectura]] en la vault.
"""

from app.core.db import Base  # noqa: F401  (registra el metadata para Alembic)

# from app.models.lead import Lead          # noqa: F401  (ejemplo, desde E02)
# from app.models.conversation import ...    # noqa: F401

__all__ = ["Base"]
