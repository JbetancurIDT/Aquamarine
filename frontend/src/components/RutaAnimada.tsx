import { useEffect } from 'react'
import { useMap } from 'react-leaflet'
import L from 'leaflet'
import { antPath } from 'leaflet-ant-path'

/**
 * Ruta con animación de FLUJO (dashes que corren de la propiedad hacia el POI, tipo corriente),
 * en bucle infinito, elegante y no invasiva. Una sola ruta activa a la vez (el padre re-monta este
 * componente al cambiar `positions`). Limpia la capa al desmontar/cambiar.
 */
export function RutaAnimada({ positions, color = '#1d4ed8' }: {
  positions: [number, number][]
  color?: string
}) {
  const map = useMap()

  useEffect(() => {
    if (!positions || positions.length < 2) return
    const path = antPath(positions, {
      color,               // azul oscuro (estilo Google Maps/Waze; contrasta con las vías beige de OSM)
      weight: 4,
      opacity: 0.85,
      dashArray: [10, 20],
      delay: 800,          // velocidad de flujo suave
      pulseColor: '#93c5fd',  // azul claro: los dashes que fluyen hacia el POI
      paused: false,
      reverse: false,      // dirección propiedad → POI
    })
    path.addTo(map)
    try {
      map.fitBounds(L.latLngBounds(positions), { padding: [60, 60], maxZoom: 16 })
    } catch { /* noop */ }
    return () => {
      map.removeLayer(path)
    }
  }, [map, positions, color])

  return null
}
