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

    # Almacén vectorial (Chroma) en modo servidor (contenedor Docker `aquamarine-chroma`).
    # La app se conecta vía HttpClient a host:puerto; ya no hay persistencia embebida en disco.
    CHROMA_HOST: str = "localhost"
    CHROMA_PORT: int = 8002

    # Tenant por defecto: todo registro lleva tenant_id desde el día 1 (multitenant-ready).
    DEFAULT_TENANT_ID: str = "aquamarine"

    # Claves de servicios externos (se completan en épicas posteriores).
    ANTHROPIC_API_KEY: str = ""
    FIRECRAWL_API_KEY: str = ""

    # Entorno de ejecución: development | staging | production.
    ENVIRONMENT: str = "development"


settings = Settings()
