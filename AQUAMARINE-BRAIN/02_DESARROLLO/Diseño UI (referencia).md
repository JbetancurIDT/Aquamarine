---
tipo: nota-tecnica
audiencia: ambos
estado: completado
actualizado: 2026-06-10
tags: [area/desarrollo, comp/frontend, diseño, ui]
---

# Diseño de referencia — Frontend Aquamarine

> [!info] Estado y alcance
> Síntesis del mock **"Landing Page Design"** (Claude Design). Es **referencia visual**, no diseño absoluto. El único requisito **duro** es **conservar la paleta** (ver abajo). Fuentes, radios, sombras y posiciones son **ajustables**. Archivos fuente en `Aquamarine/Contexto/Landing Page Design/` (no se versiona; este doc es la fuente de verdad de diseño en la vault). Decisión: [[Decisiones (Decision Log)]] D14.

## 1. Paleta — DEBE PREVALECER

> [!important] Estos hex son obligatorios. Ya están implementados como variables CSS (`:root` de `styles.css`) y son la base semántica de todos los componentes. No usar champagne como color masivo: es solo detalle de lujo.

**Neutros (estructura monocromática base)**
| Token | Hex | Uso |
|---|---|---|
| `--ink` | `#1A1A1A` | texto principal |
| `--charcoal` | `#3D3D3D` | avatares, botón dark, burbuja del lead, bar-fill por defecto |
| `--gray` | `#7A7A7A` | texto secundario (`--gray-soft #9a9a9a`) |
| `--line` | `#E5E5E5` | bordes (`--line-soft #efefef`) |
| `--bg` | `#FAFAFA` | fondo de página |
| `--card` | `#FFFFFF` | tarjetas |

**Acento LUJO — champagne / dorado** (solo detalles finos)
| Token | Hex | Uso |
|---|---|---|
| `--champ` | `#A8884E` | "marine" itálico de marca, rail KPI estrella, marca ◆ del promedio de equipo, borde-izq de stat-card |
| `--champ-soft` | `#c9b489` | borde en hover de cards, icono ✦ del Analyst, dot de chip origen |
| `--champ-bg` | `#f6f1e7` | fondo de KPI estrella, selección de texto, hover de chips |

**Canal mensajería**
| Token | Hex | Uso |
|---|---|---|
| `--wa` | `#25D366` | SOLO botón "Continuar por WhatsApp" y chip de canal (Meta/WhatsApp). Marca el paso a humano. |

**Temperatura del lead** (calidad del lead, clasificada por la IA)
| Estado | Color | Fondo (-bg) |
|---|---|---|
| Caliente (`hot`) | `#B4543A` | `#F6E9E4` |
| Tibio (`warm`) | `#B08428` | `#F7F0DE` |
| Frío (`cold`) | `#4A6275` | `#E8EDF1` |
| Desconocido (`unknown`, sin calificar) | `#7A7A7A` (gris) | `#EFEFEF` |

**Semáforo SLA / desempeño** (cumplimiento del asesor)
| Estado | Color | Fondo (-bg) |
|---|---|---|
| En objetivo (`ok`) | `#4F6F52` | `#e9efe8` |
| En riesgo (`risk`) | `#B08428` | `#F7F0DE` |
| Por debajo (`under`) | `#B4543A` | `#F6E9E4` |

> [!warning] Color compartido ≠ concepto compartido
> `temp.hot` y `semaforo.under` comparten `#B4543A`; `temp.warm` y `semaforo.risk` comparten `#B08428`. Son **enums distintos**: temperatura = calidad del lead; semáforo = cumplimiento del asesor. El backend (E02) los entrega por separado aunque visualmente se solapen. `ok` (`#4F6F52` verde) es color propio del semáforo, no de temperatura.

## 2. Tipografía y forma (ajustable)

- **Sans** `Hanken Grotesk` — UI, body (15px / line-height 1.5, antialiased).
- **Serif** `Newsreader` — titulares, valores de KPI, nombres en cards, cifras grandes. Aporta el tono "lujo"; conviene conservarla pero es negociable. La marca usa "Aqua**marine**" con *marine* en itálica color `--champ`.
- **Mono** `JetBrains Mono` — ids, scores, valores numéricos en tablas, captions de imagen, auditorías num/den.
- **Eyebrow/labels**: uppercase + letter-spacing alto.
- **Radios**: `--r-sm 8px` · `--r 12px` · `--r-lg 16px` · pills 999px. Burbujas de chat 18px con una esquina recortada a 5px (cola).
- **Sombras**: suaves (`--shadow-xs/sm/lg`), base `rgba(26,26,26,.04–.12)`.

## 3. Inventario de componentes

**Átomos reutilizables** (en `components.jsx`, expuestos globalmente):
- **Temp** — badge de temperatura del lead (pill + glyph). El átomo semántico más importante del CRM. Prop `size='lg'` para detalle. Labels desde `DATA.tempLabel`.
- **Origen / chip** — pill outline con dot champ-soft (canal de adquisición).
- **Ph** — placeholder elegante de foto de inmueble (gradiente charcoal + textura + caption mono). Variante `lit` más cálida.
- **Kpi** — tarjeta de métrica (valor serif 30px + sub + delta ▲/▼). Variantes `accent='hot'|'champ'` (rail 3px) y `highlight` (KPI estrella crema/champ).
- **Gauge** — anillo SVG de cumplimiento 0-100 coloreado por semáforo.
- **IndRow** — fila de indicador auditable (meta + valor + flag ✓/!).
- **PropertyCard** — tarjeta de inmueble (foto, título serif, estado pill, zona, precio COP "M", hab·baños·m²). Variante `compact` para incrustar en el chat.
- **LeadCard** — tarjeta de lead para Kanban (nombre + Temp + perfil + origen + score/100 + valor + mini-avatar asesor + días sin gestión).
- **Bar** — barra horizontal (funnel/origen/zonas) con tono semántico.

**Componentes mayores** (en `screen-*.jsx` + su CSS; conviene promoverlos a librería):
- App shell (topbar sticky + tabs pill + avatar de cuenta).
- Donut de temperatura (dashboard).
- Tabla comparativa de asesores `perf-table` + `sem-chip` (ordenable, marca ◆ = promedio).
- Phone frame + burbujas de chat + bloque de handoff.
- `PerfSel` / filtros dropdown, `StageStrip`, `TempStrip`, `PerfFunnel`, Gauge de detalle.
- `AnalystBot` (FAB + panel flotante).

## 4. Catálogo de pantallas

> [!note] Cara al cliente vs. consola interna
> El **Chat del lead** es **público** (cara al cliente, ruta `/chat`). **Dashboard, Pipeline, Performance y la burbuja Analyst** son la **consola interna** de Claudia y los asesores. El mock los junta en tabs (Chat/Dashboard/Pipeline) **solo por comodidad de demo**; en la app real el chat del lead va **separado** del CRM.

### 4.1 Chat del lead — "Aqua" (PÚBLICO · `/chat`) → [[E04 - Chatbot Frontend (React)]]
App de mensajería full-screen (estética WhatsApp/iMessage con paleta de lujo propia). Conversación en vivo lead ↔ agente IA "Aqua".
- **Header sticky translúcido**: avatar "A" (serif itálica), "Aqua" / "IDEAL Real Estate · Asesoría de lujo" + dot verde "en línea", chip "vía Meta" (canal), badge `LEAD · CALIENTE` (temperatura siempre visible, evoluciona Frío→Tibio→Caliente en vivo).
- **Hilo**: burbujas IA (blanca, izquierda) / lead (charcoal, derecha) con hora; **PropertyCard compact** incrustada cuando Aqua recomienda inventario (RAG); indicador "escribiendo" (~1.4s); auto-scroll.
- **Handoff**: bloque con dot verde WhatsApp + "Conectando con Daniela Restrepo · Asesora senior" y botón ancho **"Continuar por WhatsApp"** (verde `--wa`). Es el único uso del verde.
- **Input**: pill + botón circular charcoal de enviar (Enter o click).
- *Contenido perfilado en el guion*: tipo (casa de inversión campestre), zona (Las Palmas/Alto de las Palmas, Medellín), intención (inversión + temporadas), presupuesto (5.000–7.000 M).

### 4.2 Dashboard de gerencia (INTERNO) → [[E05 - CRM Pipeline y Dashboard]]
Vista de apertura de Claudia: "Buenos días, Claudia." / "Esto es lo que la IA movió mientras no estabas mirando". Lectura/análisis, no operación lead a lead.
- **page-head** + pill de periodo (Junio 2026) + botón Exportar.
- **filterbar**: Asesor / Zona / Origen / Temperatura + contador "Mostrando 248 de 248 leads".
- **8 KPIs**: Total leads 248 (+18%) · Calientes 41 (accent hot) · % calificados 63% · 1ª respuesta 0:38 (KPI estrella, meta <1:00) · Lead→cita 34% · Cita→negociación 58% · Pipeline ponderado $48.200 M · Negocios ganados 7 (accent champ, $31.400 M cerrados).
- **Funnel** (248→181→112→38→7), **Donut por temperatura** (41/73/134), **Por origen** (Meta 88, Metrocuadrado 64, Web 52, Fincaraíz 44).
- **Demanda por zona** (El Poblado 74…), **Inmuebles más consultados**, **tabla Seguimiento urgente** (días sin contacto, rojo si ≥4).

### 4.3 Pipeline — Kanban operativo (INTERNO) → [[E05 - CRM Pipeline y Dashboard]]
"Pipeline & desempeño" · "Cada lead caliente tiene dueño, reloj y meta. Nada se cae." Segmented control **Kanban / Desempeño por asesor**.
- 6 columnas por estado (Nuevo, Contactado, Calificado, Negociando, Cerrado·ganado, Cerrado·perdido), pin de color por **estado del embudo** (no por temperatura), conteo + valor total en M por columna.
- **LeadCard** clickeable → abre **panel lateral de detalle** (`LeadDetail`): identidad, score IA con barra, perfil de búsqueda, **timeline** de la conversación (IA / asesor / lead con dots de color) y acciones "Ver inventario sugerido" / "Asignar / reasignar".

### 4.4 Performance de asesores (INTERNO) → [[E05 - CRM Pipeline y Dashboard]] (vista) / [[E08 - Agente de Métricas (Gerencia)]] (métricas)
Sub-vista del Pipeline. Dos modos con un solo estado (`sel`):
- **Comparativa**: `team-strip` (3 asesores, 74 leads, 15 ganados, $62.400 M, 1ª resp. 1:04, conv. 20%) + **tabla ordenable** por cualquier columna; cada celda compara contra la **meta** (flag ✓/!) y el **promedio de equipo** (marca ◆ + ▲/▼). Semáforo ok/risk/under.
- **Detalle de asesor**: perfil + **Gauge** de score global + **4 categorías** (01 Conversión · 02 Velocidad/SLA · 03 Volumen y cartera · 04 Valor) con métricas auditables num/den, **embudo personal** y **leads recientes**.
- *Historia mock*: Daniela Restrepo (estrella, 94) · Sofía Gaviria (sólido, 85) · Mateo Ángel (en riesgo, 68; deja caer leads sin gestión).

### 4.5 Burbuja Analyst — "Asistente Aquamarine" (INTERNO, flotante) → [[E08 - Agente de Métricas (Gerencia)]]
Agente de métricas en lenguaje natural para la directora. **FAB** pill charcoal (✦ dorado, "Asistente") abajo-derecha + **panel flotante** sobre el Dashboard (no es pantalla aparte).
- Saludo personalizado ("Hola, Claudia…") + **6 preguntas sugeridas** (ventas, mejor asesor, calientes en riesgo, mejor canal, tiempo de respuesta, zona top).
- Patrón de respuesta = **prosa breve + tarjeta-stat con UN dato destacado**. Variante **warn** (roja `--under`) cuando el dato es accionable/urgente (ej. "2 calientes +4 días sin contacto, ambos de Mateo Ángel — reasignar hoy"): no solo informa, **sugiere acción**.
- Verbaliza exactamente las métricas que el panel muestra (0:38 respuesta, 41 calientes, 7 negocios, Meta 88).

## 5. Convenciones de datos (alinear con backend E02)

- **Dinero**: precios/valores en **millones de COP** (6200 = "$6.200 M"). Front formatea con `cop()+' M'`.
- **Tasas auditables**: cada % llega como `{val, num, den}` (ej. winRate 78% = 7/9). El backend expone numerador y denominador, no solo el %.
- **Tiempos**: `primeraResp` en segundos → mm:ss; `tCalif` en horas; `cicloVenta` en días. `metas.lowerBetter` marca dónde menos es mejor.
- **Dos contratos**: KPIs del dashboard llegan como **strings ya formateados** (presentacionales); `perf` llega como **números crudos calculables**. `bench` (promedios) se **deriva** de `perf`, no se persiste.
- **Enums**: temp (hot/warm/cold) · estado (nuevo/contactado/calificado/negociando/ganado/perdido/descartado) · semaforo (ok/risk/under) · idioma (ES/EN) · origen (Meta/Web/Metrocuadrado/Fincaraíz) · ciudad (Medellín/Cartagena).
- **Relaciones por id**: `lead.asesor → advisor.id` · `chatThread.cards[] → property.id` · `topProps.id → property.id`.

## 6. Caveats del mock (no son requisitos)
- Bug de formateo: doble `$$` y `20%` duplicado en perf-comparativa (`cop()` ya antepone `$`). Usar un único formateador.
- Nombre "Claudia Vélez / Directora" se solapa por ancho de fuente — ajustable.
- `descartado` es estado válido pero no tiene columna en el Kanban.
- `fmtCOP` en `data.jsx` (líneas 3-6) está rota/no usada — el formateador real es `cop()`.
