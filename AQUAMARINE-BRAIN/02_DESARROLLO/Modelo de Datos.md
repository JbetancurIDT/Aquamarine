---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-10
tags: [area/desarrollo, datos, stack/postgres, stack/chroma]
---

# Modelo de Datos

## En términos de negocio
Aquí definimos qué guardamos: los clientes (leads), sus conversaciones, en qué paso del embudo van, su "temperatura", y por separado el inventario de inmuebles que el asistente usa para recomendar.

## PostgreSQL — esquema transaccional
> Todo lleva `tenant_id` para ser multitenant-ready desde el día 1.

### `tenants`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| nombre | text | ej. "Aquamarine Group" |
| creado_en | timestamptz | |

### `leads`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK | |
| nombre | text | puede llegar vacío y completarse |
| contacto | text | email/teléfono si lo da |
| origen | text | `web` \| `meta` \| `metrocuadrado` \| `fincaraiz` (mock) |
| idioma | text | es/en (detectado); el agente solo conversa en es/en — fr fuera del target del MVP |
| score | int | 0–100 |
| temperatura | text | `caliente` \| `tibio` \| `frio` |
| estado | text | ver `pipeline` abajo |
| perfil | jsonb | {tipo, zona, presupuesto_min/max, habitaciones, plazo, notas} |
| asesor_id | UUID FK null | asignado en el handoff |
| creado_en / actualizado_en | timestamptz | |

### `conversaciones` / `mensajes`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| lead_id | UUID FK | |
| rol | text | `lead` \| `agente` \| `asesor` |
| contenido | text | |
| metadata | jsonb | tokens, inmuebles sugeridos, etc. |
| creado_en | timestamptz | |

### `pipeline` (estados del lead)
Valores de `leads.estado`:
`nuevo → contactado → calificado → negociando → cerrado_ganado → cerrado_perdido → descartado`
> El nurturing (tibio/frío) y la reactivación se modelan con estado + tareas programadas.

### `asesores`
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| tenant_id | UUID FK | |
| nombre | text | |
| disponible | bool | para la asignación |

### `eventos` (para métricas / handoff / auditoría)
| Campo | Tipo | Notas |
|---|---|---|
| id | UUID PK | |
| lead_id | UUID FK | |
| tipo | text | `lead_creado`, `score_actualizado`, `handoff`, `cita_agendada`, etc. |
| payload | jsonb | |
| creado_en | timestamptz | base para tiempos y conversión |

## Chroma — esquema del inventario (inmuebles)
Cada inmueble = 1 documento con su texto + metadata filtrable. Chroma corre como **servidor en Docker**
(`chromadb/chroma`, `localhost:8002`, `HttpClient`); colección `inmuebles`; embeddings con la **función por
defecto** de Chroma (all-MiniLM). El esquema lo define `InmuebleIn` (Pydantic) en `backend/app/schemas/inmueble.py`
y se llena por **extracción estructurada de Firecrawl** (no Claude, ver [[Decisiones (Decision Log)]] D12).
Implementado y verificado en E01 — detalle del feature en `Aquamarine Project/scraper.md`.

**Documento (texto a embedear):** título + tipo + zona/ciudad + descripción + características (texto rico para la búsqueda semántica).

**Metadata (plana — Chroma solo admite `str | int | float | bool`; los `None` se omiten; las listas se serializan):**

| Campo | Tipo | Notas |
|---|---|---|
| `inmueble_id` | str | "Código" = id final de la URL; **id en Chroma** (idempotencia) |
| `tenant_id` | str | siempre presente (multitenant); default `"aquamarine"` |
| `titulo` | str | del `<h1>` / `og:title` |
| `tipo` | str? | `apartamento \| casa \| lote \| ...` (minúsculas) |
| `tipo_negocio` | str? | `venta \| arriendo` |
| `precio` | int? | sin puntos (`$4.500.000.000` → `4500000000`); puede faltar ("Precio a consultar") |
| `moneda` | str | `COP` |
| `pais` / `departamento` / `ciudad` | str | `ciudad` es obligatoria |
| `zona` | str? | barrio/sector |
| `direccion` | str? | |
| `habitaciones` / `banos` / `parqueaderos` | int? | |
| `area_m2` | int? | redondeo de `area_construida` |
| `area_construida` / `area_privada` | float? | m² |
| `estrato` / `pisos` / `anio_construccion` | int? | |
| `administracion` | int? | valor de administración, sin puntos |
| `condicion` | str? | `usado \| nuevo` (del HTML; **NO es la disponibilidad**) |
| `estado` | str | disponibilidad del listado → `disponible` (ficha activa) |
| `es_lujo` | bool | `True` si "Inmueble de Lujo" aparece en las características |
| `caracteristicas` | str | lista unida por `, ` (Chroma no admite listas) |
| `imagen_principal` | str? | `og:image` |
| `imagenes` | str? | lista de URLs serializada como **JSON string** |
| `latitud` / `longitud` | float? | geo (`0,0` se descarta como ausente) |
| `url_fuente` | str | URL de la ficha (obligatoria) |
| `fuente` | str | `web` (web de Claudia) — extensible a portales |

> **Obligatorios mínimos:** `inmueble_id`, `titulo`, `ciudad`, `url_fuente`. El resto es opcional para no
> descartar fichas reales cuando la extracción omite un campo. `descripcion` va en el **document**, no en la metadata.
>
> **Búsqueda:** `buscar_inmuebles(query, filtros, k)` combina similitud semántica con filtros `where`
> (`ciudad`, `zona`, `tipo`, `precio_max`/`min`, `habitaciones`, `banos`, `es_lujo`), siempre acotada por `tenant_id`.
> Este es el esquema **extendido** que implementa E01; supera el mínimo original (tipo/zona/precio/área/…) con todos los
> campos relevantes de la ficha (estrato, año, administración, parqueaderos, características, geo, imágenes, lujo).

## Métricas derivadas (para el dashboard)
- Volumen de leads por **origen** y por **temperatura**.
- **Tiempo de primera respuesta** (objetivo < 1 min) y tiempo de calificación.
- Conversión **lead → cita** y **cita → negociación**.
- Leads en cada estado del **pipeline**.
- Inmuebles más consultados (mapa de calor de demanda).

> Casi todas salen de `eventos` + `leads`. Diseñar `eventos` bien = dashboard fácil.
