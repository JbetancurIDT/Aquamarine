"""Esquema del inmueble para la ingesta RAG (E01 · T01.2.2).

`InmuebleIn` es el modelo común al que se normaliza cada ficha scrapeada antes de
indexarla en Chroma. Combina:
- campos de **contenido** que extrae Firecrawl de la página (titulo, precio, zona…),
- campos **fijos/derivados** que pone el mapper (`inmueble_id`, `tenant_id`, `moneda`,
  `es_lujo`, `area_m2`, …).

Expone dos helpers para Chroma:
- `document`: el texto que se embebe (búsqueda semántica).
- `metadata`: dict **plano** (solo `str|int|float|bool`, sin `None` ni listas anidadas),
  porque Chroma no admite otros tipos en metadata.
"""

import json

from pydantic import BaseModel, Field

from app.rag.geo_const import CERCANIA_KEYS


class InmuebleIn(BaseModel):
    # --- Identidad / fijos ---
    inmueble_id: str  # "Código" (= id numérico final de la URL). Id en Chroma → idempotencia.
    tenant_id: str  # settings.DEFAULT_TENANT_ID

    # --- Contenido principal ---
    # Obligatorios mínimos: inmueble_id, url_fuente, titulo, ciudad. El resto es
    # opcional para no descartar fichas válidas cuando Firecrawl omite un campo
    # (típico: "Precio a consultar" → precio None).
    titulo: str
    tipo: str | None = None  # apartamento | casa | lote | ... (en minúsculas)
    tipo_negocio: str | None = None  # venta | arriendo
    precio: int | None = None  # sin puntos: "$4.500.000.000" → 4500000000
    moneda: str = "COP"

    # --- Ubicación ---
    pais: str | None = None
    departamento: str | None = None
    ciudad: str
    zona: str | None = None
    direccion: str | None = None

    # --- Características numéricas ---
    habitaciones: int | None = None
    banos: int | None = None
    parqueaderos: int | None = None
    area_m2: int | None = None  # redondeo entero de area_construida
    area_construida: float | None = None
    area_privada: float | None = None
    estrato: int | None = None
    pisos: int | None = None
    anio_construccion: int | None = None
    administracion: int | None = None  # sin puntos

    # --- Estado ---
    condicion: str | None = None  # usado | nuevo (del HTML; NO es disponibilidad)
    estado: str = "disponible"  # disponibilidad del listado (ficha activa)
    es_lujo: bool = False  # True si "Inmueble de Lujo" está en las características

    # --- Texto / listas ---
    caracteristicas: list[str] = Field(default_factory=list)
    descripcion: str | None = None  # va en el `document`, NO en la metadata

    # --- Media ---
    imagen_principal: str | None = None
    imagenes: list[str] = Field(default_factory=list)

    # --- Geo ---
    latitud: float | None = None
    longitud: float | None = None
    # Distancias precalculadas (m) al POI más cercano por categoría (E09). Nombres = valores
    # de geo_const.CERCANIA_KEYS. Metadata plana: si es None, la property `metadata` la omite.
    dist_metro_m: int | None = None
    dist_super_m: int | None = None
    dist_mall_m: int | None = None
    dist_colegio_m: int | None = None
    dist_universidad_m: int | None = None
    dist_parque_m: int | None = None
    dist_clinica_m: int | None = None

    # --- Procedencia ---
    url_fuente: str
    fuente: str = "web"

    @property
    def document(self) -> str:
        """Texto a embedear: rico en zona/tipo/características, sin incrustar 'None'."""
        partes = [self.titulo]
        ubic = " en ".join(
            p
            for p in [self.tipo, ", ".join(x for x in [self.zona, self.ciudad] if x)]
            if p
        )
        if ubic:
            partes.append(ubic)
        if self.descripcion:
            partes.append(self.descripcion)
        if self.caracteristicas:
            partes.append("Características: " + ", ".join(self.caracteristicas))
        return ". ".join(partes)

    @property
    def metadata(self) -> dict:
        """Dict plano para Chroma (solo str|int|float|bool; sin None; listas serializadas)."""
        bruto = {
            "inmueble_id": self.inmueble_id,
            "tenant_id": self.tenant_id,
            "titulo": self.titulo,
            "tipo": self.tipo,
            "tipo_negocio": self.tipo_negocio,
            "precio": self.precio,
            "moneda": self.moneda,
            "pais": self.pais,
            "departamento": self.departamento,
            "ciudad": self.ciudad,
            "zona": self.zona,
            "direccion": self.direccion,
            "habitaciones": self.habitaciones,
            "banos": self.banos,
            "parqueaderos": self.parqueaderos,
            "area_m2": self.area_m2,
            "area_construida": self.area_construida,
            "area_privada": self.area_privada,
            "estrato": self.estrato,
            "pisos": self.pisos,
            "anio_construccion": self.anio_construccion,
            "administracion": self.administracion,
            "condicion": self.condicion,
            "estado": self.estado,
            "es_lujo": self.es_lujo,
            # caracteristicas → string; imagenes → JSON string; descripcion NO va aquí.
            "caracteristicas": ", ".join(self.caracteristicas) if self.caracteristicas else None,
            "imagen_principal": self.imagen_principal,
            "imagenes": json.dumps(self.imagenes, ensure_ascii=False) if self.imagenes else None,
            "latitud": self.latitud,
            "longitud": self.longitud,
            "url_fuente": self.url_fuente,
            "fuente": self.fuente,
        }
        # Distancias geo (E09): se añaden por su nombre canónico en CERCANIA_KEYS (fuente única
        # de verdad; cero strings de clave a mano). Las que sigan en None las descarta la
        # comprensión de abajo, igual que el resto → metadata plana sin nulos.
        for _clave in CERCANIA_KEYS.values():
            bruto[_clave] = getattr(self, _clave)
        # Chroma no acepta None en metadata → se omiten esas claves.
        return {clave: valor for clave, valor in bruto.items() if valor is not None}
