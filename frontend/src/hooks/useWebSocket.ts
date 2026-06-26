import { useEffect, useRef, useState, useCallback } from 'react'
import type { DashboardSnapshot } from '../types'
import { WS_BASE } from '../lib/api'

type ConnectionState = 'connecting' | 'connected' | 'disconnected'

export function useWebSocket() {
  const [data, setData] = useState<DashboardSnapshot | null>(null)
  const [connectionState, setConnectionState] = useState<ConnectionState>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const ws = new WebSocket(`${WS_BASE}/ws`)
    wsRef.current = ws

    ws.onopen = () => setConnectionState('connected')

    ws.onmessage = (e) => {
      try {
        setData(JSON.parse(e.data) as DashboardSnapshot)
      } catch {
        // ignore malformed message
      }
    }

    ws.onclose = () => {
      setConnectionState('disconnected')
      retryRef.current = setTimeout(connect, 3000)
    }

    ws.onerror = () => {
      ws.close()
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      retryRef.current && clearTimeout(retryRef.current)
      wsRef.current?.close()
    }
  }, [connect])

  return { data, connectionState }
}
