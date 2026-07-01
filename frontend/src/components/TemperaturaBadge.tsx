import React from 'react'

type TemperaturaKey = 'desconocido' | 'frio' | 'tibio' | 'caliente'

export const TEMPERATURA_BADGE: Record<TemperaturaKey, { style: React.CSSProperties; etiqueta: string }> = {
  desconocido: { style: { color: 'var(--unknown)', background: 'var(--unknown-bg)' }, etiqueta: '—' },
  frio:        { style: { color: 'var(--cold)',    background: 'var(--cold-bg)'    }, etiqueta: 'Frío' },
  tibio:       { style: { color: 'var(--warm)',    background: 'var(--warm-bg)'    }, etiqueta: 'Tibio' },
  caliente:    { style: { color: 'var(--hot)',     background: 'var(--hot-bg)'     }, etiqueta: 'Caliente' },
}

export function TemperaturaBadge({ temperatura }: { temperatura: string }) {
  const badge = TEMPERATURA_BADGE[temperatura as TemperaturaKey] ?? TEMPERATURA_BADGE.desconocido
  return (
    <span className="text-xs font-medium px-2 py-0.5 rounded-full flex-shrink-0" style={badge.style}>
      {badge.etiqueta}
    </span>
  )
}
