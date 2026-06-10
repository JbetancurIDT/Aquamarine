---
tipo: nota-tecnica
audiencia: dev
estado: completado
actualizado: 2026-06-09
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
| idioma | text | es/en/fr (detectado) |
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
Cada inmueble = 1 documento con su texto + metadata filtrable.

**Documento (texto a embedear):** descripción rica del inmueble (zona, características, entorno).

**Metadata:**
```json
{
  "inmueble_id": "string",
  "tenant_id": "string",
  "tipo": "apartamento | casa | lote | ...",
  "zona": "El Poblado | Laureles | ...",
  "ciudad": "Medellín | Cartagena | ...",
  "precio": 1500000000,
  "moneda": "COP",
  "habitaciones": 3,
  "banos": 2,
  "area_m2": 180,
  "estado": "disponible | reservado | vendido",
  "url_fuente": "https://...",
  "fuente": "web | metrocuadrado | fincaraiz"
}
```

## Métricas derivadas (para el dashboard)
- Volumen de leads por **origen** y por **temperatura**.
- **Tiempo de primera respuesta** (objetivo < 1 min) y tiempo de calificación.
- Conversión **lead → cita** y **cita → negociación**.
- Leads en cada estado del **pipeline**.
- Inmuebles más consultados (mapa de calor de demanda).

> Casi todas salen de `eventos` + `leads`. Diseñar `eventos` bien = dashboard fácil.
