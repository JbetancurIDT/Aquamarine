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
    # Modelo de Claude para el agente Aqua (ID sin sufijo de fecha). Sonnet 4.6 soporta
    # tool use + prompt caching; subir a claude-opus-4-8 para la demo.
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"
    # Modelo barato para la extracción estructurada del perfil (tarea mecánica).
    ANTHROPIC_EXTRACTION_MODEL: str = "claude-haiku-4-5"
    FIRECRAWL_API_KEY: str = ""

    # ── Geo / búsqueda por proximidad (E09) ──────────────────────────────────
    # Fuentes en vivo (STRETCH). Nominatim se usa en caliente SOLO para el fallback por nombre
    # propio (cacheado); Overpass/GTFS son offline (scripts build_*). Radio default del fallback.
    NOMINATIM_URL: str = "https://nominatim.openstreetmap.org/search"
    NOMINATIM_USER_AGENT: str = "Aquamarine/1.0 (E09 geo; contacto: dev@aquamarine.example)"
    OVERPASS_URL: str = "https://overpass-api.de/api/interpreter"
    METRO_GTFS_URL: str = ("https://raw.githubusercontent.com/ColombiaInfo/ColombiaGTFS/master/"
                           "Medellin%20-%20Metro/stops.txt")
    GEO_DEFAULT_RADIO_KM: float = 3.0

    # Rutas del mapa interactivo (OpenRouteService, OSM — sin Google). Si ORS_API_KEY está vacía o
    # ORS falla, el endpoint /geo/ruta cae a una ruta en LÍNEA RECTA (aprox) para que la demo funcione.
    ORS_API_KEY: str = ""
    ORS_URL: str = "https://api.openrouteservice.org/v2/directions"
    # OSRM público: ruteo por CALLES sin key (paso intermedio ORS → OSRM → línea recta).
    # Swappable a un OSRM self-hosted. El demo público tiene límites de uso (no producción pesada).
    OSRM_URL: str = "https://router.project-osrm.org"
    GEO_MODO_UMBRAL_M: int = 1800  # modo=auto: caminando por debajo de este umbral, si no carro

    # Entorno de ejecución: development | staging | production.
    ENVIRONMENT: str = "development"

    # ── Handoff, auto-asignación y notificaciones escalonadas (E07) ──────────
    MAX_LEADS_ACTIVOS_POR_ASESOR: int = 5
    NOTIF_MAX_ANTES_REASIGNAR: int = 5
    SWEEP_INTERVALO_SEG: int = 60     # cada cuánto corre el barrido (segundos)
    # NOTIF_SCALE: divide los intervalos base → útil para demo con tiempos cortos.
    # Ejemplo: NOTIF_SCALE=60 convierte 300s→5s (caliente avisa en 5 s en vez de 5 min).
    NOTIF_SCALE: float = 1.0

    # Intervalos base de notificación por temperatura (segundos)
    NOTIF_SEG_CALIENTE: int = 300
    NOTIF_SEG_TIBIO: int = 1200
    NOTIF_SEG_FRIO: int = 3600
    NOTIF_SEG_DESCONOCIDO: int = 1200

    @property
    def notif_intervalos_seg(self) -> dict:
        """Intervalos efectivos tras aplicar NOTIF_SCALE."""
        scale = max(self.NOTIF_SCALE, 0.001)
        return {
            "caliente":    max(1, int(self.NOTIF_SEG_CALIENTE / scale)),
            "tibio":       max(1, int(self.NOTIF_SEG_TIBIO / scale)),
            "frio":        max(1, int(self.NOTIF_SEG_FRIO / scale)),
            "desconocido": max(1, int(self.NOTIF_SEG_DESCONOCIDO / scale)),
        }


settings = Settings()
