import { useCallback, useEffect, useMemo, useState } from 'react'
import apiClient from '../api/client'
import type { AsesorMetrics } from '../api/types'
import { ConsolaNav } from '../components/ConsolaNav'

// ---------------------------------------------------------------------------
// SLA traffic lights
// ---------------------------------------------------------------------------

const SLA = {
  ok:    '#4F6F52',
  risk:  '#B08428',
  under: '#B4543A',
  none:  'var(--gray-soft)',
} as const

type SlaLevel = keyof typeof SLA

/** Clasifica un tiempo (seg) contra umbrales {ok <, risk <}. null → neutral. */
function clasificar(seg: number | null, okLt: number, riskLt: number): SlaLevel {
  if (seg === null) return 'none'
  if (seg < okLt) return 'ok'
  if (seg < riskLt) return 'risk'
  return 'under'
}

function formatMMSS(seg: number | null): string {
  if (seg === null) return '—'
  const m = Math.floor(seg / 60)
  const s = Math.round(seg % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

function copM(cop: number): string {
  return `$${(cop / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`
}

function SlaCell({ seg, level }: { seg: number | null; level: SlaLevel }) {
  return (
    <span className="inline-flex items-center gap-1.5 justify-end w-full font-mono">
      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: SLA[level] }} />
      <span style={{ color: level === 'none' ? 'var(--gray-soft)' : 'var(--ink)' }}>
        {formatMMSS(seg)}
      </span>
    </span>
  )
}

// ---------------------------------------------------------------------------
// Tabla
// ---------------------------------------------------------------------------

type SortKey =
  | 'nombre' | 'leads_asignados' | 'en_cola' | 'tomados' | 'ganados'
  | 'valor_cerrado_cop' | 'primera_respuesta_seg' | 'tiempo_en_tomar_seg' | 'conversion'

type Col = {
  key: SortKey
  label: string
  align: 'left' | 'right'
  value: (m: AsesorMetrics) => number | string | null
}

const COLS: Col[] = [
  { key: 'nombre',                label: 'Asesor',        align: 'left',  value: m => m.nombre },
  { key: 'leads_asignados',       label: 'Asignados',     align: 'right', value: m => m.leads_asignados },
  { key: 'en_cola',               label: 'En cola',       align: 'right', value: m => m.en_cola },
  { key: 'tomados',               label: 'Tomados',       align: 'right', value: m => m.tomados },
  { key: 'ganados',               label: 'Ganados',       align: 'right', value: m => m.ganados },
  { key: 'valor_cerrado_cop',     label: 'Valor cerrado', align: 'right', value: m => m.valor_cerrado_cop },
  { key: 'primera_respuesta_seg', label: '1ª resp.',      align: 'right', value: m => m.primera_respuesta_seg },
  { key: 'tiempo_en_tomar_seg',   label: 'Tiempo en tomar', align: 'right', value: m => m.tiempo_en_tomar_seg },
  { key: 'conversion',            label: 'Conversión',    align: 'right', value: m => m.ratio_conversion.pct },
]

export default function PerformancePage() {
  const [metrics, setMetrics] = useState<AsesorMetrics[]>([])
  const [cargando, setCargando] = useState(true)
  const [sortKey, setSortKey] = useState<SortKey>('leads_asignados')
  const [asc, setAsc] = useState(false)

  const cargar = useCallback(async () => {
    try {
      const { data } = await apiClient.get<AsesorMetrics[]>('/metrics/asesores')
      setMetrics(data)
    } catch {
      // silencioso
    }
  }, [])

  useEffect(() => {
    cargar().finally(() => setCargando(false))
    const id = setInterval(cargar, 6000)
    return () => clearInterval(id)
  }, [cargar])

  const valorOrden = useCallback((m: AsesorMetrics, key: SortKey): number | string | null => {
    if (key === 'conversion') return m.ratio_conversion.pct
    const col = COLS.find(c => c.key === key)
    return col ? col.value(m) : null
  }, [])

  const sorted = useMemo(() => {
    const dir = asc ? 1 : -1
    return [...metrics].sort((a, b) => {
      const av = valorOrden(a, sortKey)
      const bv = valorOrden(b, sortKey)
      if (av === null && bv === null) return 0
      if (av === null) return 1   // nulls siempre al final
      if (bv === null) return -1
      if (typeof av === 'string' && typeof bv === 'string') return dir * av.localeCompare(bv)
      return dir * ((av as number) - (bv as number))
    })
  }, [metrics, sortKey, asc, valorOrden])

  const handleSort = (key: SortKey) => {
    if (key === sortKey) {
      setAsc(a => !a)
    } else {
      setSortKey(key)
      // por defecto: texto asc, números desc
      setAsc(key === 'nombre')
    }
  }

  return (
    <div className="flex flex-col min-h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header */}
      <header
        className="flex-shrink-0 border-b px-6 py-3 flex items-center justify-between gap-4"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <h1 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
        </h1>
        <ConsolaNav active="/performance" />
      </header>

      <main className="flex-1 px-6 py-6 max-w-6xl mx-auto w-full">
        <div className="mb-5">
          <h2 className="text-xl font-semibold"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
            Performance del equipo
          </h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--gray-soft)' }}>
            Carga, conversión y SLA por asesor · ordena haciendo clic en una columna
          </p>
        </div>

        {/* Leyenda SLA */}
        <div className="flex items-center gap-4 mb-4 text-xs" style={{ color: 'var(--gray)' }}>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: SLA.ok }} /> En SLA
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: SLA.risk }} /> En riesgo
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: SLA.under }} /> Fuera de SLA
          </span>
        </div>

        {cargando ? (
          <p className="text-sm text-center mt-12" style={{ color: 'var(--gray-soft)' }}>Cargando…</p>
        ) : metrics.length === 0 ? (
          <p className="text-sm text-center mt-12" style={{ color: 'var(--gray-soft)' }}>
            No hay asesores registrados todavía.
          </p>
        ) : (
          <div className="rounded-2xl border overflow-x-auto scrollbar-brand"
            style={{ background: 'var(--card)', borderColor: 'var(--line)' }}>
            <table className="w-full text-sm border-collapse">
              <thead>
                <tr style={{ borderBottom: '1px solid var(--line)' }}>
                  {COLS.map(c => (
                    <th
                      key={c.key}
                      onClick={() => handleSort(c.key)}
                      className={`px-4 py-3 font-semibold cursor-pointer select-none whitespace-nowrap ${c.align === 'right' ? 'text-right' : 'text-left'}`}
                      style={{ color: sortKey === c.key ? 'var(--champ)' : 'var(--gray-soft)' }}
                    >
                      {c.label}
                      {sortKey === c.key && <span className="ml-1">{asc ? '▲' : '▼'}</span>}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {sorted.map(m => {
                  const slaResp  = clasificar(m.primera_respuesta_seg, 60, 300)
                  const slaTomar = clasificar(m.tiempo_en_tomar_seg, 300, 1800)
                  return (
                    <tr key={m.id} style={{ borderBottom: '1px solid var(--line-soft)' }}>
                      <td className="px-4 py-3">
                        <span className="flex items-center gap-2">
                          <span className="w-2 h-2 rounded-full flex-shrink-0"
                            style={{ background: m.disponible ? '#2D7A4F' : 'var(--gray-soft)' }}
                            title={m.disponible ? 'Disponible' : 'No disponible'} />
                          <span className="font-medium" style={{ color: 'var(--ink)' }}>{m.nombre}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--ink)' }}>{m.leads_asignados}</td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--ink)' }}>{m.en_cola}</td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--ink)' }}>{m.tomados}</td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--champ)' }}>{m.ganados}</td>
                      <td className="px-4 py-3 text-right font-medium" style={{ color: 'var(--ink)' }}>{copM(m.valor_cerrado_cop)}</td>
                      <td className="px-4 py-3 text-right"><SlaCell seg={m.primera_respuesta_seg} level={slaResp} /></td>
                      <td className="px-4 py-3 text-right"><SlaCell seg={m.tiempo_en_tomar_seg} level={slaTomar} /></td>
                      <td className="px-4 py-3 text-right font-mono" style={{ color: 'var(--ink)' }}>
                        {(m.ratio_conversion.pct * 100).toFixed(1)}%
                        <span className="text-xs ml-1" style={{ color: 'var(--gray-soft)' }}>
                          ({m.ratio_conversion.num}/{m.ratio_conversion.den})
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </div>
  )
}
