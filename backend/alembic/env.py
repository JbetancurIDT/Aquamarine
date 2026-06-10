"""Entorno de Alembic (E00 · T00.2.2).

Lee `DATABASE_URL` desde `app.core.config.settings` (no se hardcodea) y usa
`Base.metadata` como `target_metadata`, importando `app.models` para que todos
los modelos queden registrados antes de autogenerar migraciones.
"""

import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Hace importable el paquete `app` cuando Alembic ejecuta este archivo
# (la raíz del backend es el directorio padre de `alembic/`).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings  # noqa: E402
from app.core.db import Base  # noqa: E402
import app.models  # noqa: E402,F401  (registra los modelos en Base.metadata)

# Objeto de configuración de Alembic (lee alembic.ini).
config = context.config

# Inyecta la URL real desde settings (sobrescribe el placeholder de alembic.ini).
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# Configura el logging definido en alembic.ini.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Metadata objetivo para `--autogenerate`.
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse a la base (modo --sql)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Ejecuta las migraciones con una conexión real a la base."""
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = settings.DATABASE_URL
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
