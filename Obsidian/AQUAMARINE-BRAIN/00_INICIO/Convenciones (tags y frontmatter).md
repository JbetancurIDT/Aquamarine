---
tipo: nota-proyecto
audiencia: ambos
estado: completado
actualizado: 2026-06-09
tags: [inicio, convenciones, meta]
---

# Convenciones (tags y frontmatter)

Para que tanto humanos como agentes de IA naveguen el vault de forma predecible.

## Frontmatter (YAML al inicio de cada nota)

```yaml
---
tipo:        # ver tabla abajo
audiencia:   # dev | comercial | ambos
estado:      # pendiente | en-progreso | completado | bloqueado
epica:       # solo en épicas: E00, E01, ...
actualizado: # YYYY-MM-DD
tags:        # lista de tags
---
```

### Valores de `tipo`
| Valor | Significado |
|---|---|
| `moc` | Mapa de contenido / índice |
| `nota-proyecto` | Contexto compartido del proyecto |
| `nota-tecnica` | Documento técnico (arquitectura, datos…) |
| `epica` | Épica con tareas para Claude Code |
| `nota-comercial` | Material comercial / pitch |
| `log` | Bitácora / seguimiento |
| `fuente` | Material original sin editar |

## Taxonomía de tags

**Por área:**
`#area/proyecto` · `#area/desarrollo` · `#area/comercial`

**Por componente del MVP:**
`#comp/rag` · `#comp/backend` · `#comp/agente` · `#comp/frontend` · `#comp/crm` · `#comp/handoff` · `#comp/dashboard` · `#comp/demo`

**Por stack:**
`#stack/fastapi` · `#stack/react` · `#stack/postgres` · `#stack/chroma` · `#stack/firecrawl` · `#stack/claude`

**Por estado (atajo de búsqueda):**
`#estado/pendiente` · `#estado/en-progreso` · `#estado/completado` · `#estado/bloqueado`

## Convención de IDs de tareas
`T{epica}.{etapa}.{numero}` → ejemplo: `T01.2.3` = Épica 01, Etapa 2, Tarea 3.
Permite referenciarlas en commits, en el [[Daily Log]] y en prompts a Claude Code.

## Enlaces
- Siempre usar enlaces internos `[[Nombre de la nota]]` en vez de repetir contenido.
- Cada nota técnica enlaza a su contraparte comercial cuando exista, y viceversa.
