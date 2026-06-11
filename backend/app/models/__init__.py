"""Modelos SQLAlchemy (E00 · T00.2.2 → poblado en E02).

Reexporta `Base` y **importa todos los modelos** para que queden registrados en
`Base.metadata` (necesario para que Alembic los detecte al autogenerar y para que
`Base.metadata.create_all()` los cree en los tests).

Convención del proyecto: todo modelo de negocio lleva `tenant_id` (multitenant-ready).
"""

from app.core.db import Base  # noqa: F401  (registra el metadata para Alembic)
from app.models.tenant import Tenant  # noqa: F401
from app.models.asesor import Asesor  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.mensaje import Mensaje  # noqa: F401
from app.models.evento import Evento  # noqa: F401

__all__ = ["Base", "Tenant", "Asesor", "Lead", "Mensaje", "Evento"]
