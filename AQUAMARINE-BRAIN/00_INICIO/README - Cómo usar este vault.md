---
tipo: nota-proyecto
audiencia: ambos
estado: completado
actualizado: 2026-06-09
tags: [inicio, guia, meta]
---

# README — Cómo usar este vault

Este vault es el **cerebro único** del MVP de Aquamarine. Está diseñado para que dos mundos convivan sin pisarse:

- **Desarrollo** (`02_DESARROLLO`) — el detalle técnico, las épicas y las tareas que se le pasan a Claude Code.
- **Comercial** (`03_COMERCIAL`) — la narrativa, el pitch y el negocio, en lenguaje humano sin tecnicismos.

Ambos mundos **convergen** en el espacio compartido (`01_PROYECTO`, `04_PROGRESO`), que es la fuente de verdad común. Así, cuando el dev avanza, la comercial puede ver el avance traducido a su idioma, y viceversa.

## Cómo lo usa cada quien

### El desarrollador (vía Claude Code)
- Trabaja sobre las **épicas** en `02_DESARROLLO/Epicas/`.
- Cada épica tiene tareas con un **prompt sugerido** listo para pegar en Claude Code.
- Al cerrar una tarea, marca el checkbox `[x]` y deja una línea en [[Daily Log]].

### La comercial (vía Claude Desktop)
- Vive en `03_COMERCIAL` y `01_PROYECTO`.
- Si necesita saber "¿qué se hizo en el backend?", le pide a su agente que lea el vault: el agente cruza el [[Glosario (Tech ↔ Negocio)]] y le responde en lenguaje de negocio.
- Nunca necesita leer código: las notas técnicas siempre abren con un bloque **"En términos de negocio"**.

### Un agente de IA (cualquiera)
1. Empieza por [[🏠 MOC - Inicio]].
2. Respeta el `frontmatter`: `audiencia`, `tipo`, `estado`.
3. Si la pregunta es comercial, traduce con [[Glosario (Tech ↔ Negocio)]] y evita jerga.
4. Si la pregunta es técnica, ve directo a la épica correspondiente.

## Reglas de oro
1. **Una sola fuente de verdad por tema.** No dupliques; enlaza con `[[...]]`.
2. **Toda nota técnica abre con "En términos de negocio".** Es el puente entre mundos.
3. **Las decisiones se registran** en [[Decisiones (Decision Log)]], no se quedan en la cabeza de nadie.
4. **El progreso se actualiza a diario** en [[Daily Log]] y [[Estado del MVP (Checklist global)]].

Ver convenciones de formato en [[Convenciones (tags y frontmatter)]].
