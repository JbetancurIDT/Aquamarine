"""Configuración por entorno (E00 · T00.2.1).

Usa pydantic-settings: las variables se leen del entorno o de un archivo `.env`
en la raíz de `backend/`. Se exporta una única instancia `settings`.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Base de datos relacional (Postgres). Se da un default de desarrollo para que
    # la app y Alembic arranquen sin configurar nada; en producción viene del entorno.
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/aquamarine"

    # Almacén vectorial (Chroma) persistente en disco.
    CHROMA_PERSIST_DIR: str = "./chroma_store"

    # Claves de servicios externos (se completan en épicas posteriores).
    ANTHROPIC_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""

    # Entorno de ejecución: development | staging | production.
    ENVIRONMENT: str = "development"


settings = Settings()
