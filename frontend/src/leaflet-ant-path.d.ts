declare module 'leaflet-ant-path' {
  import type * as L from 'leaflet'
  export function antPath(latlngs: L.LatLngExpression[], options?: Record<string, unknown>): L.Polyline
}
