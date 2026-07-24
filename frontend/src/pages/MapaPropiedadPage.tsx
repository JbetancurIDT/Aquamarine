import { useEffect, useMemo, useState, type ReactNode } from 'react'
import { useParams } from 'react-router-dom'
import { MapContainer, Marker, TileLayer, Tooltip } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import apiClient from '../api/client'
import { RutaAnimada } from '../components/RutaAnimada'

// --- Tipos ---
type Poi = { nombre: string; dist_m: number; lat: number; lon: number }
type Ficha = {
  codigo: string; titulo?: string; tipo?: string; precio?: number
  zona?: string; ciudad?: string; imagen_principal?: string; url_fuente?: string
  latitud: number; longitud: number
}
type CercaResp = { inmueble: Ficha; lugares: Record<string, Poi[]> }
type Ruta = { geometry: [number, number][]; duration_min: number; distance_m: number; modo: string; aprox: boolean }

// --- Metadata visual por categoría (emoji + color de marca) ---
const CAT: Record<string, { emoji: string; label: string; color: string }> = {
  metro:            { emoji: '🚇', label: 'Metro',              color: '#4A6275' },
  supermercado:     { emoji: '🛒', label: 'Supermercados',      color: '#B08428' },
  centro_comercial: { emoji: '🛍️', label: 'Centros comerciales', color: '#A8884E' },
  colegio:          { emoji: '🏫', label: 'Colegios',           color: '#B4543A' },
  universidad:      { emoji: '🎓', label: 'Universidades',      color: '#3D3D3D' },
  parque:           { emoji: '🌳', label: 'Parques',            color: '#4A7A4A' },
  clinica:          { emoji: '🏥', label: 'Clínicas',           color: '#9A5B7A' },
}
const CAT_ORDER = ['metro', 'supermercado', 'centro_comercial', 'colegio', 'universidad', 'parque', 'clinica']

function emojiIcon(emoji: string, size: number, ring: string): L.DivIcon {
  return L.divIcon({
    className: '',
    html: `<div style="font-size:${Math.round(size * 0.6)}px;line-height:${size}px;width:${size}px;height:${size}px;text-align:center;background:#fff;border:2px solid ${ring};border-radius:50%;box-shadow:0 1px 5px rgba(26,26,26,.3)">${emoji}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
  })
}

function aprox(m: number): string {
  return m < 1000 ? `~${Math.round(m / 100) * 100} m` : `~${(m / 1000).toFixed(1)} km`
}

export default function MapaPropiedadPage() {
  const { codigo } = useParams<{ codigo: string }>()
  const [data, setData] = useState<CercaResp | null>(null)
  const [error, setError] = useState(false)
  const [sel, setSel] = useState<{ cat: string; poi: Poi } | null>(null)
  const [ruta, setRuta] = useState<Ruta | null>(null)
  const [rutaError, setRutaError] = useState(false)

  const propIcon = useMemo(() => emojiIcon('🏡', 42, '#A8884E'), [])
  const poiIcons = useMemo(() => {
    const m: Record<string, L.DivIcon> = {}
    for (const c of CAT_ORDER) m[c] = emojiIcon(CAT[c].emoji, 30, CAT[c].color)
    return m
  }, [])

  useEffect(() => {
    if (!codigo) return
    apiClient.get<CercaResp>(`/rag/inmuebles/${codigo}/cerca`)
      .then((r) => setData(r.data))
      .catch(() => setError(true))
  }, [codigo])

  // Al elegir un POI → traer la ruta (propiedad → POI, modo auto).
  useEffect(() => {
    if (!data || !sel) { setRuta(null); setRutaError(false); return }
    let vivo = true
    setRuta(null); setRutaError(false)
    const { latitud, longitud } = data.inmueble
    apiClient.get<Ruta>('/geo/ruta', {
      params: { from_lat: latitud, from_lon: longitud, to_lat: sel.poi.lat, to_lon: sel.poi.lon, modo: 'auto' },
    })
      .then((r) => { if (vivo) setRuta(r.data) })
      .catch(() => { if (vivo) setRutaError(true) })
    return () => { vivo = false }
  }, [data, sel])

  if (error) return <Centro>No se pudo cargar la propiedad. ¿Está el backend en :8000?</Centro>
  if (!data) return <Centro>Cargando mapa…</Centro>

  const { inmueble, lugares } = data
  const centro: [number, number] = [inmueble.latitud, inmueble.longitud]
  const cats = CAT_ORDER.filter((c) => lugares[c]?.length)

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header mínimo con marca (público, sin ConsolaNav) */}
      <header className="flex-shrink-0 border-b px-5 py-3 flex items-center justify-between gap-3"
              style={{ background: 'var(--card)', borderColor: 'var(--line)' }}>
        <span className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
          <span className="font-normal" style={{ color: 'var(--gray-soft)' }}> · Mapa de la propiedad</span>
        </span>
        {inmueble.url_fuente && (
          <a href={inmueble.url_fuente} target="_blank" rel="noopener noreferrer"
             className="text-xs font-medium" style={{ color: 'var(--champ)' }}>Ver ficha →</a>
        )}
      </header>

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        {/* Mapa */}
        <div className="h-[55vh] md:h-auto md:flex-1 relative">
          <MapContainer center={centro} zoom={15} scrollWheelZoom style={{ height: '100%', width: '100%' }}>
            <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                       attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' />
            {/* Pin del inmueble (distinto) */}
            <Marker position={centro} icon={propIcon}>
              <Tooltip direction="top" offset={[0, -20]}>
                <b>{inmueble.titulo ?? 'Este inmueble'}</b>
              </Tooltip>
            </Marker>
            {/* Un pin por POI */}
            {cats.flatMap((c) => lugares[c].map((poi, i) => (
              <Marker key={`${c}-${i}`} position={[poi.lat, poi.lon]} icon={poiIcons[c]}
                      eventHandlers={{ click: () => setSel({ cat: c, poi }) }}>
                <Tooltip direction="top" offset={[0, -16]}>{poi.nombre} · {aprox(poi.dist_m)}</Tooltip>
              </Marker>
            )))}
            {/* Ruta animada (línea azul, sin rótulo de tiempo) */}
            {ruta && ruta.geometry.length >= 2 && (
              <RutaAnimada positions={ruta.geometry} color="#1d4ed8" />
            )}
          </MapContainer>
        </div>

        {/* Panel lateral (o inferior en móvil) con los lugares */}
        <aside className="flex-1 md:flex-none md:w-80 overflow-y-auto scrollbar-brand border-t md:border-t-0 md:border-l"
               style={{ background: 'var(--card)', borderColor: 'var(--line)' }}>
          <div className="p-4">
            <h1 className="text-lg font-semibold leading-snug"
                style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
              {inmueble.titulo ?? 'Propiedad'}
            </h1>
            <p className="text-sm mt-0.5" style={{ color: 'var(--gray-soft)' }}>
              {[inmueble.zona, inmueble.ciudad].filter(Boolean).join(', ')}
              {inmueble.precio != null && ` · $${(inmueble.precio / 1_000_000).toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`}
            </p>
            {sel && (
              <p className="text-xs mt-2 px-2 py-1.5 rounded-lg" style={{ background: 'var(--champ-bg)', color: 'var(--charcoal)' }}>
                Ruta a <b>{sel.poi.nombre}</b>{ruta ? '' : rutaError ? ' — no se pudo calcular la ruta' : ' — calculando…'}
              </p>
            )}
            <p className="text-xs mt-2" style={{ color: 'var(--gray-soft)' }}>
              Toca un lugar para trazar la ruta. Distancias aproximadas (la ubicación es el centroide del barrio).
            </p>
          </div>

          {cats.map((c) => (
            <div key={c} className="px-4 pb-3">
              <p className="text-xs font-semibold mb-1 flex items-center gap-1.5" style={{ color: 'var(--ink)' }}>
                <span>{CAT[c].emoji}</span> {CAT[c].label}
              </p>
              <ul className="space-y-1">
                {lugares[c].map((poi, i) => {
                  const activo = sel?.cat === c && sel?.poi.nombre === poi.nombre && sel?.poi.lat === poi.lat
                  return (
                    <li key={i}>
                      <button onClick={() => setSel({ cat: c, poi })}
                              className="w-full text-left text-xs px-2 py-1.5 rounded-lg transition-colors flex justify-between gap-2"
                              style={activo
                                ? { background: 'var(--champ-bg)', color: 'var(--ink)', border: '1px solid var(--champ-soft)' }
                                : { background: 'var(--line-soft)', color: 'var(--charcoal)' }}>
                        <span className="truncate">{poi.nombre}</span>
                        <span className="flex-shrink-0" style={{ color: 'var(--gray)' }}>{aprox(poi.dist_m)}</span>
                      </button>
                    </li>
                  )
                })}
              </ul>
            </div>
          ))}
        </aside>
      </div>
    </div>
  )
}

function Centro({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center justify-center h-screen" style={{ background: 'var(--bg)' }}>
      <p className="text-sm" style={{ color: 'var(--gray-soft)' }}>{children}</p>
    </div>
  )
}
