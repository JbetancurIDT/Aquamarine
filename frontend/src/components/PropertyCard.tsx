export type Inmueble = {
  inmueble_id?: string
  titulo?: string
  tipo?: string
  zona?: string
  ciudad?: string
  precio?: number
  habitaciones?: number
  banos?: number
  area_m2?: number
  url_fuente?: string
  descripcion?: string
}

function formatCOP(pesos: number): string {
  const millones = pesos / 1_000_000
  return `$${millones.toLocaleString('es-CO', { maximumFractionDigits: 0 })} M`
}

export function PropertyCard({ inmueble }: { inmueble: Inmueble }) {
  const specs = [
    inmueble.habitaciones != null ? `${inmueble.habitaciones} hab` : null,
    inmueble.banos != null ? `${inmueble.banos} baños` : null,
    inmueble.area_m2 != null ? `${inmueble.area_m2} m²` : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <div
      className="flex flex-col flex-shrink-0 w-52 rounded-xl overflow-hidden"
      style={{
        background: 'var(--card)',
        border: '1px solid var(--line)',
        boxShadow: '0 1px 4px rgba(26,26,26,.07)',
      }}
    >
      {/* Foto placeholder */}
      <div
        className="flex items-center justify-center h-20 text-xs font-mono"
        style={{ background: 'var(--line-soft)', color: 'var(--gray-soft)' }}
      >
        {inmueble.tipo ?? 'inmueble'}
      </div>

      {/* Contenido */}
      <div className="p-3 flex flex-col gap-1">
        {inmueble.titulo && (
          <p
            className="text-sm font-semibold leading-snug line-clamp-2"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
          >
            {inmueble.titulo}
          </p>
        )}

        {(inmueble.zona || inmueble.ciudad) && (
          <p className="text-xs" style={{ color: 'var(--gray-soft)' }}>
            {[inmueble.zona, inmueble.ciudad].filter(Boolean).join(', ')}
          </p>
        )}

        {inmueble.precio != null && (
          <p
            className="text-sm font-semibold mt-0.5"
            style={{ fontFamily: 'Newsreader, Georgia, serif', color: 'var(--ink)' }}
          >
            {formatCOP(inmueble.precio)}
          </p>
        )}

        {specs && (
          <p className="text-xs" style={{ color: 'var(--gray)' }}>
            {specs}
          </p>
        )}

        {inmueble.url_fuente && (
          <a
            href={inmueble.url_fuente}
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs mt-1 font-medium"
            style={{ color: 'var(--champ)' }}
          >
            Ver detalle →
          </a>
        )}
      </div>
    </div>
  )
}

export function PropertyCardList({ inmuebles }: { inmuebles: Inmueble[] }) {
  const visibles = inmuebles.slice(0, 3)
  return (
    <div className="flex flex-row gap-2 overflow-x-auto pb-1 max-w-full">
      {visibles.map((inm, i) => (
        <PropertyCard key={inm.inmueble_id ?? i} inmueble={inm} />
      ))}
    </div>
  )
}
