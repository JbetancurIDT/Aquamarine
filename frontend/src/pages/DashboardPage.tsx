import { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import apiClient from '../api/client'
import type { Asesor, AsesorMetrics, MetricsOverview, PropiedadesMetrics, Rate } from '../api/types'
import { AquaChat } from '../components/AquaChat'
import { ConsolaNav } from '../components/ConsolaNav'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function pctStr(r: Rate): string {
  return `${(r.pct * 100).toFixed(1)}%`
}

function copM(cop: number): string {
  const m = cop / 1_000_000
  return `$${m.toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`
}

function formatMMSS(seg: number | null): string {
  if (seg === null) return '—'
  const m = Math.floor(seg / 60)
  const s = Math.round(seg % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

const ETAPA_LABEL: Record<string, string> = {
  nuevo: 'Nuevo',
  contactado: 'Contactado',
  calificado: 'Calificado',
  negociando: 'Negociando',
  cerrado_ganado: 'Ganado',
}

const TEMP_COLOR: Record<string, string> = {
  caliente: 'var(--hot)',
  tibio: 'var(--warm)',
  frio: 'var(--cold)',
  desconocido: 'var(--gray-soft)',
  otros: 'var(--line)',
}

const TEMP_LABEL: Record<string, string> = {
  caliente: 'Caliente',
  tibio: 'Tibio',
  frio: 'Frío',
  desconocido: 'N/A',
  otros: 'Otros',
}

// ---------------------------------------------------------------------------
// Donut SVG (por temperatura)
// ---------------------------------------------------------------------------

type DonutSegment = { label: string; count: number; color: string }

function DonutChart({ segments }: { segments: DonutSegment[] }) {
  const total = segments.reduce((s, d) => s + d.count, 0)
  if (total === 0) return (
    <p className="text-xs text-center" style={{ color: 'var(--gray-soft)' }}>Sin datos</p>
  )

  const cx = 56, cy = 56, r = 38, inner = 24
  let start = -Math.PI / 2

  const paths = segments.filter(s => s.count > 0).map(({ label, count, color }) => {
    const angle = (count / total) * 2 * Math.PI
    const end = start + angle
    const x1 = cx + r * Math.cos(start), y1 = cy + r * Math.sin(start)
    const x2 = cx + r * Math.cos(end),   y2 = cy + r * Math.sin(end)
    const ix1 = cx + inner * Math.cos(end),   iy1 = cy + inner * Math.sin(end)
    const ix2 = cx + inner * Math.cos(start), iy2 = cy + inner * Math.sin(start)
    const large = angle > Math.PI ? 1 : 0
    const d = `M${x1},${y1} A${r},${r} 0 ${large},1 ${x2},${y2} L${ix1},${iy1} A${inner},${inner} 0 ${large},0 ${ix2},${iy2}Z`
    start = end
    return { d, color, label, count }
  })

  return (
    <div className="flex items-center gap-4">
      <svg width="112" height="112" viewBox="0 0 112 112" className="flex-shrink-0">
        {paths.length === 1 ? (
          // Un solo segmento (100%): el arco SVG degenera a vacío → anillo completo.
          <circle
            cx={cx} cy={cy} r={(r + inner) / 2}
            fill="none" stroke={paths[0].color} strokeWidth={r - inner}
          />
        ) : (
          paths.map(p => <path key={p.label} d={p.d} fill={p.color} />)
        )}
      </svg>
      <div className="flex flex-col gap-1.5">
        {paths.map(p => (
          <div key={p.label} className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: p.color }} />
            <span className="text-xs" style={{ color: 'var(--ink)' }}>
              {TEMP_LABEL[p.label] ?? p.label}
            </span>
            <span className="text-xs font-mono ml-auto pl-2" style={{ color: 'var(--gray-soft)' }}>
              {p.count} ({((p.count / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// KPI tile
// ---------------------------------------------------------------------------

function Kpi({
  label, value, sublabel, accent, highlight,
}: {
  label: string
  value: string
  sublabel?: string
  accent?: string
  highlight?: boolean
}) {
  return (
    <div
      className="p-4 rounded-2xl border flex flex-col gap-1"
      style={{
        background: highlight ? 'var(--champ-bg)' : 'var(--card)',
        borderColor: highlight ? 'var(--champ-soft)' : 'var(--line)',
      }}
    >
      <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>{label}</p>
      <p
        className="text-2xl font-semibold leading-tight"
        style={{ fontFamily: 'Newsreader, Georgia, serif', color: accent ?? 'var(--ink)' }}
      >
        {value}
      </p>
      {sublabel && (
        <p className="text-xs" style={{ color: accent ?? 'var(--gray-soft)' }}>{sublabel}</p>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// MiniStat (bloques inventario)
// ---------------------------------------------------------------------------

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="p-3 rounded-xl border flex flex-col gap-0.5"
      style={{ background: 'var(--bg)', borderColor: 'var(--line)' }}>
      <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>{label}</p>
      <p className="text-lg font-semibold leading-tight"
        style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
        {value}
      </p>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Funnel horizontal bar
// ---------------------------------------------------------------------------

function FunnelBar({
  etapa, count, maxCount, pct_paso_previo,
}: {
  etapa: string
  count: number
  maxCount: number
  pct_paso_previo: Rate | null
}) {
  const w = maxCount > 0 ? (count / maxCount) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs w-24 text-right flex-shrink-0" style={{ color: 'var(--ink)' }}>
        {ETAPA_LABEL[etapa] ?? etapa}
      </span>
      <div className="flex-1 rounded-full overflow-hidden" style={{ height: '8px', background: 'var(--line-soft)' }}>
        <div
          style={{ width: `${w}%`, height: '100%', background: 'var(--champ)', borderRadius: 'inherit', transition: 'width 0.4s' }}
        />
      </div>
      <span className="text-xs w-8 text-right font-mono" style={{ color: 'var(--ink)' }}>
        {count}
      </span>
      <span className="text-xs w-16 text-right" style={{ color: pct_paso_previo ? 'var(--gray-soft)' : 'transparent' }}>
        {pct_paso_previo ? `${(pct_paso_previo.pct * 100).toFixed(1)}%` : '—'}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Barra por origen
// ---------------------------------------------------------------------------

function BarraOrigen({ origen, count, maxCount }: { origen: string; count: number; maxCount: number }) {
  const w = maxCount > 0 ? (count / maxCount) * 100 : 0
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs w-28 capitalize flex-shrink-0" style={{ color: 'var(--ink)' }}>
        {origen}
      </span>
      <div className="flex-1 rounded-full overflow-hidden" style={{ height: '6px', background: 'var(--line-soft)' }}>
        <div
          style={{ width: `${w}%`, height: '100%', background: 'var(--charcoal)', borderRadius: 'inherit', transition: 'width 0.4s' }}
        />
      </div>
      <span className="text-xs w-6 text-right font-mono" style={{ color: 'var(--gray-soft)' }}>
        {count}
      </span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// DashboardPage — panel de gerencia / métricas
// ---------------------------------------------------------------------------

const ORIG_PARAM: Record<string, string> = {
  web: 'web',
  meta: 'meta',
  metrocuadrado: 'metrocuadrado',
  fincaraiz: 'fincaraiz',
}

export default function DashboardPage() {
  const [metrics, setMetrics] = useState<MetricsOverview | null>(null)
  const [asesores, setAsesores] = useState<Asesor[]>([])
  const [propiedades, setPropiedades] = useState<PropiedadesMetrics | null>(null)
  const [asesorMetrics, setAsesorMetrics] = useState<AsesorMetrics[]>([])
  const [cargando, setCargando] = useState(true)

  // Filtros
  const [filtroAsesor, setFiltroAsesor] = useState('')
  const [filtroOrigen, setFiltroOrigen] = useState('')
  const [filtroTemp, setFiltroTemp] = useState('')

  const fetchRef = useRef<AbortController | null>(null)

  const cargarMetricas = useCallback(async () => {
    fetchRef.current?.abort()
    fetchRef.current = new AbortController()
    const params: Record<string, string> = {}
    if (filtroAsesor) params.asesor_id = filtroAsesor
    if (filtroOrigen) params.origen = filtroOrigen
    if (filtroTemp)   params.temperatura = filtroTemp
    try {
      const { data } = await apiClient.get<MetricsOverview>('/metrics/overview', { params })
      setMetrics(data)
    } catch {
      // abort silencioso
    }
  }, [filtroAsesor, filtroOrigen, filtroTemp])

  // Carga inicial + asesores
  useEffect(() => {
    apiClient.get<Asesor[]>('/asesores').then(({ data }) => setAsesores(data))
    cargarMetricas().finally(() => setCargando(false))
  }, [])

  // Re-fetch cuando cambian filtros
  useEffect(() => {
    cargarMetricas()
  }, [cargarMetricas])

  // Polling ~6 s
  useEffect(() => {
    const id = setInterval(cargarMetricas, 6000)
    return () => clearInterval(id)
  }, [cargarMetricas])

  // Extras (inventario mock + métricas por asesor) — globales, sin filtros
  useEffect(() => {
    const cargarExtras = () => {
      apiClient.get<PropiedadesMetrics>('/metrics/propiedades')
        .then(({ data }) => setPropiedades(data)).catch(() => {})
      apiClient.get<AsesorMetrics[]>('/metrics/asesores')
        .then(({ data }) => setAsesorMetrics(data)).catch(() => {})
    }
    cargarExtras()
    const id = setInterval(cargarExtras, 6000)
    return () => clearInterval(id)
  }, [])

  const m = metrics

  const origeNEntries = m
    ? Object.entries(m.por_origen).filter(([k]) => k !== 'otros' && m.por_origen[k] > 0)
    : []
  const maxOrigen = origeNEntries.length > 0 ? Math.max(...origeNEntries.map(([, v]) => v)) : 1

  const tempSegments: { label: string; count: number; color: string }[] = m
    ? ['caliente', 'tibio', 'frio', 'desconocido'].map(k => ({
        label: k,
        count: m.por_temperatura[k] ?? 0,
        color: TEMP_COLOR[k],
      }))
    : []

  const totalFiltrado = m?.total_leads ?? 0

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
        <ConsolaNav active="/dashboard" />
      </header>

      <main className="flex-1 px-6 py-6 max-w-5xl mx-auto w-full">
        {/* Page head */}
        <div className="mb-5">
          <h2
            className="text-xl font-semibold"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
          >
            Buenos días, Claudia.
          </h2>
          <p className="text-sm mt-0.5" style={{ color: 'var(--gray-soft)' }}>
            Resumen del pipeline · Junio 2026
          </p>
        </div>

        {/* Filter bar */}
        <div
          className="mb-5 px-4 py-3 rounded-xl border flex flex-wrap items-center gap-3"
          style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
        >
          <span className="text-xs" style={{ color: 'var(--gray-soft)' }}>Filtrar:</span>

          <select
            className="text-xs px-2 py-1 rounded-lg border"
            style={{ background: 'var(--bg)', borderColor: 'var(--line)', color: 'var(--ink)' }}
            value={filtroAsesor}
            onChange={e => setFiltroAsesor(e.target.value)}
          >
            <option value="">Todos los asesores</option>
            {asesores.map(a => (
              <option key={a.id} value={a.id}>{a.nombre}</option>
            ))}
          </select>

          <select
            className="text-xs px-2 py-1 rounded-lg border"
            style={{ background: 'var(--bg)', borderColor: 'var(--line)', color: 'var(--ink)' }}
            value={filtroOrigen}
            onChange={e => setFiltroOrigen(e.target.value)}
          >
            <option value="">Todos los orígenes</option>
            {Object.keys(ORIG_PARAM).map(o => (
              <option key={o} value={o}>{o}</option>
            ))}
          </select>

          <select
            className="text-xs px-2 py-1 rounded-lg border"
            style={{ background: 'var(--bg)', borderColor: 'var(--line)', color: 'var(--ink)' }}
            value={filtroTemp}
            onChange={e => setFiltroTemp(e.target.value)}
          >
            <option value="">Todas las temperaturas</option>
            <option value="caliente">Caliente</option>
            <option value="tibio">Tibio</option>
            <option value="frio">Frío</option>
            <option value="desconocido">Sin clasificar</option>
          </select>

          {(filtroAsesor || filtroOrigen || filtroTemp) && (
            <button
              className="text-xs px-2 py-1 rounded-lg"
              style={{ color: 'var(--gray)', background: 'var(--line-soft)' }}
              onClick={() => { setFiltroAsesor(''); setFiltroOrigen(''); setFiltroTemp('') }}
            >
              Limpiar
            </button>
          )}

          <span className="ml-auto text-xs" style={{ color: 'var(--gray-soft)' }}>
            Mostrando {totalFiltrado} leads
          </span>
        </div>

        {cargando && (
          <p className="text-sm text-center mt-12" style={{ color: 'var(--gray-soft)' }}>Cargando métricas…</p>
        )}

        {!cargando && m && (
          <>
            {/* 8 KPIs */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-6">
              <Kpi label="Total leads" value={String(m.total_leads)} />
              <Kpi
                label="Leads calientes"
                value={String(m.leads_calientes.count)}
                sublabel={pctStr(m.leads_calientes.rate)}
                accent="var(--hot)"
              />
              <Kpi
                label="% calificados"
                value={pctStr(m.pct_calificados)}
                sublabel={`${m.pct_calificados.num}/${m.pct_calificados.den}`}
              />
              <Kpi
                label="1ª respuesta"
                value={formatMMSS(m.primera_respuesta_seg)}
                sublabel="meta < 1:00"
                highlight
                accent={
                  m.primera_respuesta_seg !== null && m.primera_respuesta_seg < 60
                    ? '#2D7A4F'
                    : m.primera_respuesta_seg !== null
                    ? 'var(--hot)'
                    : 'var(--gray-soft)'
                }
              />
              <Kpi
                label="Lead → cita"
                value={pctStr(m.conversion.lead_a_cita)}
                sublabel={`${m.conversion.lead_a_cita.num}/${m.conversion.lead_a_cita.den}`}
              />
              <Kpi
                label="Cita → negociación"
                value={pctStr(m.conversion.cita_a_negociacion)}
                sublabel={`${m.conversion.cita_a_negociacion.num}/${m.conversion.cita_a_negociacion.den}`}
              />
              <Kpi
                label="Pipeline ponderado"
                value={copM(m.pipeline_ponderado_cop)}
              />
              <Kpi
                label="Negocios ganados"
                value={String(m.negocios_ganados.count)}
                sublabel={`${copM(m.negocios_ganados.valor_cerrado_cop)} cerrados`}
                accent="var(--champ)"
              />
            </div>

            {/* Funnel + distribuciones */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Funnel */}
              <div
                className="p-4 rounded-2xl border"
                style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
              >
                <p
                  className="text-xs font-semibold mb-3"
                  style={{ color: 'var(--gray-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
                >
                  Embudo del pipeline
                </p>
                <div className="flex flex-col gap-2.5">
                  {m.funnel.map(step => (
                    <FunnelBar
                      key={step.etapa}
                      etapa={step.etapa}
                      count={step.count}
                      maxCount={m.funnel[0]?.count ?? 1}
                      pct_paso_previo={step.pct_paso_previo}
                    />
                  ))}
                </div>
                <p className="text-xs mt-3" style={{ color: 'var(--gray-soft)' }}>
                  % del paso previo ↗
                </p>
              </div>

              {/* Donut temperatura */}
              <div
                className="p-4 rounded-2xl border"
                style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
              >
                <p
                  className="text-xs font-semibold mb-3"
                  style={{ color: 'var(--gray-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
                >
                  Por temperatura
                </p>
                <DonutChart segments={tempSegments} />
              </div>

              {/* Por origen */}
              <div
                className="p-4 rounded-2xl border sm:col-span-2"
                style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
              >
                <p
                  className="text-xs font-semibold mb-3"
                  style={{ color: 'var(--gray-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}
                >
                  Por origen
                </p>
                <div className="flex flex-col gap-2">
                  {origeNEntries.length === 0 ? (
                    <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>Sin datos</p>
                  ) : (
                    origeNEntries
                      .sort(([, a], [, b]) => b - a)
                      .map(([origen, count]) => (
                        <BarraOrigen key={origen} origen={origen} count={count} maxCount={maxOrigen} />
                      ))
                  )}
                </div>
              </div>
            </div>

            {/* Inventario de propiedades (datos de muestra) */}
            <div
              className="mt-4 p-4 rounded-2xl border"
              style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold"
                  style={{ color: 'var(--gray-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Inventario de propiedades
                </p>
                <span className="text-[10px] px-2 py-0.5 rounded-full"
                  style={{ background: 'var(--warm-bg)', color: 'var(--warm)' }}>
                  datos de muestra
                </span>
              </div>
              {propiedades ? (
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                  <MiniStat label="Activas" value={propiedades.activas} />
                  <MiniStat label="En negociación" value={propiedades.en_negociacion} />
                  <MiniStat label="Cerradas" value={propiedades.cerradas} />
                  <MiniStat label="Valor cerrado" value={copM(propiedades.valor_cerrado_cop)} />
                </div>
              ) : (
                <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>Sin datos</p>
              )}
            </div>

            {/* Equipo de asesores */}
            <div
              className="mt-4 p-4 rounded-2xl border"
              style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-xs font-semibold"
                  style={{ color: 'var(--gray-soft)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Equipo de asesores
                </p>
                <div className="flex items-center gap-3">
                  <Link to="/asesores" className="text-xs font-medium" style={{ color: 'var(--champ)' }}>
                    Asesores →
                  </Link>
                  <Link to="/performance" className="text-xs font-medium" style={{ color: 'var(--champ)' }}>
                    Ver performance →
                  </Link>
                </div>
              </div>
              {asesorMetrics.length === 0 ? (
                <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>Sin asesores registrados.</p>
              ) : (
                <div className="overflow-x-auto scrollbar-brand">
                  <table className="w-full text-sm border-collapse">
                    <thead>
                      <tr style={{ borderBottom: '1px solid var(--line)' }}>
                        <th className="px-3 py-2 text-left font-semibold" style={{ color: 'var(--gray-soft)' }}>Asesor</th>
                        <th className="px-3 py-2 text-right font-semibold" style={{ color: 'var(--gray-soft)' }}>En cola</th>
                        <th className="px-3 py-2 text-right font-semibold" style={{ color: 'var(--gray-soft)' }}>Tomados</th>
                        <th className="px-3 py-2 text-right font-semibold" style={{ color: 'var(--gray-soft)' }}>Ganados</th>
                        <th className="px-3 py-2 text-right font-semibold" style={{ color: 'var(--gray-soft)' }}>Conv.</th>
                      </tr>
                    </thead>
                    <tbody>
                      {asesorMetrics.map(a => (
                        <tr key={a.id} style={{ borderBottom: '1px solid var(--line-soft)' }}>
                          <td className="px-3 py-2">
                            <Link to={`/asesor/${a.id}`} className="flex items-center gap-2 hover:underline">
                              <span className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                                style={{ background: a.disponible ? '#2D7A4F' : 'var(--gray-soft)' }} />
                              <span style={{ color: 'var(--ink)' }}>{a.nombre}</span>
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--ink)' }}>{a.en_cola}</td>
                          <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--ink)' }}>{a.tomados}</td>
                          <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--champ)' }}>{a.ganados}</td>
                          <td className="px-3 py-2 text-right font-mono" style={{ color: 'var(--ink)' }}>
                            {(a.ratio_conversion.pct * 100).toFixed(0)}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </>
        )}
      </main>

      {/* Burbuja de asistente Aqua — FAB + panel flotante */}
      <AquaChat />
    </div>
  )
}
