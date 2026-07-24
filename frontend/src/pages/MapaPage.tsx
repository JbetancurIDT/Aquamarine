import { useEffect, useState } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer } from 'react-leaflet'
import 'leaflet/dist/leaflet.css'
import apiClient from '../api/client'
import { ConsolaNav } from '../components/ConsolaNav'
import { PropertyCard, type Inmueble } from '../components/PropertyCard'

// Inmueble del mapa = el de PropertyCard + coords, distancias por cercanía, y la DEMANDA de la zona.
type MapaInmueble = Inmueble & {
  latitud: number
  longitud: number
  leads_zona: number
  dist_metro_m?: number
  dist_super_m?: number
  dist_mall_m?: number
  dist_colegio_m?: number
  dist_universidad_m?: number
  dist_parque_m?: number
  dist_clinica_m?: number
}

const CENTRO_MEDELLIN: [number, number] = [6.24, -75.58]

// Rampa de calor SECUENCIAL por demanda de leads en la zona (rojo = más). Rangos REALES (0-5):
// máximo observado = 5 leads (El Poblado). Cambiar la escala = tocar solo esta función.
function colorPorDemanda(n: number): string {
  if (n >= 5) return '#dc2626' // rojo — alta demanda
  if (n >= 3) return '#f97316' // naranja — demanda media
  if (n >= 1) return '#fbbf24' // ámbar — demanda baja
  return '#cbd5e1'             // gris — sin demanda
}

// Leyenda del mapa de calor (imprescindible para entender los colores).
const LEYENDA: { color: string; label: string }[] = [
  { color: '#cbd5e1', label: '0 · sin demanda' },
  { color: '#fbbf24', label: '1–2' },
  { color: '#f97316', label: '3–4' },
  { color: '#dc2626', label: '5+ · alta demanda' },
]

// Categorías de cercanía → etiqueta corta para el popup (mismo vocabulario que geo_const).
const CERCANIA: [keyof MapaInmueble, string][] = [
  ['dist_metro_m', 'Metro'],
  ['dist_super_m', 'Súper'],
  ['dist_mall_m', 'C.C.'],
  ['dist_colegio_m', 'Colegio'],
  ['dist_universidad_m', 'Univ.'],
  ['dist_parque_m', 'Parque'],
  ['dist_clinica_m', 'Clínica'],
]

function aprox(m: number): string {
  return m < 1000 ? `~${Math.round(m / 100) * 100} m` : `~${(m / 1000).toFixed(1)} km`
}

function Cercania({ inm }: { inm: MapaInmueble }) {
  const items = CERCANIA
    .filter(([k]) => typeof inm[k] === 'number')
    .map(([k, label]) => `${label} ${aprox(inm[k] as number)}`)
  if (items.length === 0) return null
  return (
    <p className="text-xs mt-1.5" style={{ color: 'var(--gray)' }}>
      {items.join(' · ')}
    </p>
  )
}

function Demanda({ inm }: { inm: MapaInmueble }) {
  const n = inm.leads_zona
  return (
    <p className="text-xs mt-1.5 flex items-center gap-1.5">
      <span className="inline-block w-2.5 h-2.5 rounded-full flex-shrink-0"
            style={{ background: colorPorDemanda(n) }} />
      {n > 0 ? (
        <span style={{ color: 'var(--ink)' }}>
          <b>{n}</b> {n === 1 ? 'lead busca' : 'leads buscan'} en {inm.zona ?? 'esta zona'}
        </span>
      ) : (
        <span style={{ color: 'var(--gray-soft)' }}>Sin leads en esta zona</span>
      )}
    </p>
  )
}

export default function MapaPage() {
  const [inmuebles, setInmuebles] = useState<MapaInmueble[]>([])
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    apiClient
      .get<{ inmuebles: MapaInmueble[] }>('/rag/inmuebles/mapa')
      .then((r) => setInmuebles(r.data.inmuebles))
      .catch(() => setError(true))
      .finally(() => setCargando(false))
  }, [])

  return (
    <div className="flex flex-col h-screen" style={{ background: 'var(--bg)' }}>
      {/* Header (consistente con el resto de la consola) */}
      <header
        className="flex-shrink-0 border-b px-6 py-3 flex items-center justify-between gap-4"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <h1 className="text-sm font-semibold" style={{ color: 'var(--ink)' }}>
          Aqua<span className="italic" style={{ color: 'var(--champ)' }}>marine</span>
          <span className="font-normal" style={{ color: 'var(--gray-soft)' }}> · Mapa</span>
        </h1>
        <ConsolaNav active="/mapa" />
      </header>

      {/* Sub-head */}
      <div
        className="flex-shrink-0 px-6 py-3 border-b"
        style={{ background: 'var(--card)', borderColor: 'var(--line)' }}
      >
        <h2 className="text-xl font-semibold"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}>
          Inventario en el mapa
        </h2>
        <p className="text-sm mt-0.5" style={{ color: 'var(--gray-soft)' }}>
          {cargando ? 'Cargando…' : `${inmuebles.length} propiedades · color = leads buscando en la zona`}
        </p>
      </div>

      {/* Mapa (llena el resto de la pantalla) */}
      <main className="flex-1 relative" style={{ minHeight: 0 }}>
        {error ? (
          <div className="absolute inset-0 flex items-center justify-center">
            <p className="text-sm" style={{ color: 'var(--gray-soft)' }}>
              No se pudo cargar el inventario. ¿Está el backend arriba en :8000?
            </p>
          </div>
        ) : (
          <>
            <MapContainer
              center={CENTRO_MEDELLIN}
              zoom={12}
              scrollWheelZoom
              style={{ height: '100%', width: '100%' }}
            >
              <TileLayer
                url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
                attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              />
              {inmuebles.map((inm, i) => (
                <CircleMarker
                  key={inm.inmueble_id ?? i}
                  center={[inm.latitud, inm.longitud]}
                  radius={7 + inm.leads_zona}
                  pathOptions={{
                    fillColor: colorPorDemanda(inm.leads_zona),
                    color: '#ffffff',
                    weight: 1.5,
                    fillOpacity: 0.85,
                  }}
                >
                  <Popup minWidth={216} maxWidth={240} className="mapa-popup">
                    <PropertyCard inmueble={inm} />
                    <Demanda inm={inm} />
                    <Cercania inm={inm} />
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>

            {/* Leyenda del mapa de calor (esquina inferior-derecha) */}
            <div
              className="absolute bottom-4 right-4 rounded-xl border px-3 py-2.5"
              style={{ background: 'var(--card)', borderColor: 'var(--line)', zIndex: 1000,
                       boxShadow: '0 1px 6px rgba(26,26,26,.10)' }}
            >
              <p className="text-xs font-semibold mb-1.5" style={{ color: 'var(--ink)' }}>
                Demanda de leads
              </p>
              <div className="flex flex-col gap-1">
                {LEYENDA.map(({ color, label }) => (
                  <div key={label} className="flex items-center gap-2">
                    <span className="inline-block w-3 h-3 rounded-full flex-shrink-0"
                          style={{ background: color, border: '1.5px solid #ffffff',
                                   boxShadow: '0 0 0 1px var(--line)' }} />
                    <span className="text-xs" style={{ color: 'var(--gray)' }}>{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
