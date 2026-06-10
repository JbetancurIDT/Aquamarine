"""Capa de base de datos: SQLAlchemy síncrono (E00 · T00.2.2).

Se mantiene síncrono a propósito por simplicidad para el MVP. Expone:
- `engine`        — motor conectado a `settings.DATABASE_URL`.
- `SessionLocal`  — fábrica de sesiones.
- `Base`          — clase base declarativa que heredan los modelos.
- `get_db()`      — dependencia de FastAPI que entrega una sesión y la cierra.
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)

# Todos los modelos ORM heredan de esta Base. Alembic usa `Base.metadata`.
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Dependencia FastAPI: abre una sesión por request y la cierra al terminar."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
