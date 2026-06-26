// In development: WS is proxied by Vite, API calls use relative URLs
// In production:  set VITE_WS_URL and VITE_API_URL to the Railway backend URL
const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
export const WS_BASE  = (import.meta.env.VITE_WS_URL  as string | undefined) ?? `${proto}://${window.location.host}`
export const API_BASE = (import.meta.env.VITE_API_URL as string | undefined) ?? ''
