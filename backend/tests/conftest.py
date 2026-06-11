"""Infraestructura de tests aislada (E02 · §6).

Usa una BD separada `aquamarine_test` (NO la de desarrollo). Cada test parte de una
BD limpia. El `client` inyecta la sesión de test en la app vía dependency_overrides.
"""

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient
import app.models  # registra los modelos en Base.metadata (antes de ligar `app` a la instancia)
from app.core.db import Base, get_db
from app.core.config import settings
from app.main import app  # debe ir AL FINAL: `app` queda ligado a la instancia FastAPI, no al paquete

_BASE = settings.DATABASE_URL.rsplit("/", 1)[0]
TEST_DB_URL = _BASE + "/aquamarine_test"


@pytest.fixture(scope="session")
def engine():
    admin = create_engine(_BASE + "/postgres", isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        if not c.execute(text("SELECT 1 FROM pg_database WHERE datname='aquamarine_test'")).scalar():
            c.execute(text("CREATE DATABASE aquamarine_test"))
    admin.dispose()
    eng = create_engine(TEST_DB_URL)
    with eng.connect() as c:
        c.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto")); c.commit()
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def db(engine):
    s = sessionmaker(bind=engine)()
    for t in reversed(Base.metadata.sorted_tables):  # limpia respetando FKs
        s.execute(t.delete())
    s.commit()
    yield s
    s.close()


@pytest.fixture
def client(db):
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
