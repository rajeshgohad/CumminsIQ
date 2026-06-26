import { useState, useEffect, useRef } from 'react'
import type { AssemblySnapshot } from '../types/assembly'
import { WS_BASE } from '../lib/api'

export function useAssemblySocket() {
  const [data, setData] = useState<AssemblySnapshot | null>(null)
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected'>('connecting')
  const wsRef = useRef<WebSocket | null>(null)
  const retryRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  function connect() {
    if (wsRef.current?.readyState === WebSocket.OPEN) return
    setConnectionState('connecting')
    const ws = new WebSocket(`${WS_BASE}/ws/assembly`)
    wsRef.current = ws

    ws.onopen = () => setConnectionState('connected')
    ws.onmessage = (e) => {
      try { setData(JSON.parse(e.data)) } catch {}
    }
    ws.onclose = () => {
      setConnectionState('disconnected')
      retryRef.current = setTimeout(connect, 3000)
    }
    ws.onerror = () => ws.close()
  }

  useEffect(() => {
    connect()
    return () => {
      wsRef.current?.close()
      if (retryRef.current) clearTimeout(retryRef.current)
    }
  }, [])

  return { data, connectionState }
}
