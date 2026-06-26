import { useEffect, useState } from 'react'
import { ClipboardList, CheckCircle2, Clock, AlertCircle, Database, RefreshCw } from 'lucide-react'
import type { ActivityLogEntry, Agent } from '../../types/assembly'
import { API_BASE } from '../../lib/api'

interface Props { log: ActivityLogEntry[]; agent: Agent | undefined }

interface WO {
  wo_number: string
  station_code: string | null
  description: string
  priority: string
  wo_status: string
  created_at: number
  source: 'db' | 'session'
}

const PRI_STYLE: Record<string, string> = {
  HIGH:   'text-red-400 bg-red-500/10 border-red-500/20',
  MEDIUM: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  LOW:    'text-blue-400 bg-blue-500/10 border-blue-500/20',
}

const STATUS_ICON: Record<string, React.ElementType> = {
  open:          AlertCircle,
  'in-progress': Clock,
  complete:      CheckCircle2,
}
const STATUS_COLOR: Record<string, string> = {
  open:          'text-amber-400',
  'in-progress': 'text-blue-400',
  complete:      'text-green-400',
}

function timeAgo(ts: number) {
  const d = Math.floor(Date.now() / 1000) - ts
  if (d < 60)   return `${d}s ago`
  if (d < 3600) return `${Math.floor(d / 60)}m ago`
  return `${Math.floor(d / 3600)}h ago`
}

function extractSessionWOs(log: ActivityLogEntry[]): WO[] {
  return log
    .filter(e => e.from_agent === 'maintenance' && e.type === 'act' && e.message.includes('WO-'))
    .map(e => {
      const wo = e.message.match(/WO-\d+/)?.[0] ?? 'WO-???'
      const pri = e.message.match(/Priority:\s*(\w+)/)?.[1] ?? 'MEDIUM'
      return {
        wo_number:    wo,
        station_code: e.station,
        description:  e.message.split('—')[0].trim().slice(0, 120),
        priority:     pri,
        wo_status:    'open',
        created_at:   e.timestamp,
        source:       'session' as const,
      }
    })
}

export default function WorkOrders({ log, agent }: Props) {
  const [dbWOs, setDbWOs]   = useState<WO[]>([])
  const [loading, setLoading] = useState(true)
  const [lastFetch, setLastFetch] = useState(0)

  const fetchWOs = () => {
    fetch(`${API_BASE}/api/work-orders?limit=50`)
      .then(r => r.json())
      .then((rows: any[]) => {
        setDbWOs(rows.map(r => ({ ...r, source: 'db' as const })))
        setLastFetch(Date.now())
      })
      .catch(() => {})
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    fetchWOs()
    const t = setInterval(fetchWOs, 15_000)   // refresh from DB every 15s
    return () => clearInterval(t)
  }, [])

  // Merge DB + session, dedupe by WO number (DB wins)
  const sessionWOs = extractSessionWOs(log)
  const dbNums = new Set(dbWOs.map(w => w.wo_number))
  const merged = [
    ...dbWOs,
    ...sessionWOs.filter(w => !dbNums.has(w.wo_number)),
  ].sort((a, b) => b.created_at - a.created_at).slice(0, 20)

  return (
    <div className="flex flex-col gap-3 h-full">
      {/* Header */}
      <div className="flex items-center gap-2">
        <ClipboardList size={14} className="text-orange-400" />
        <span className="text-xs font-semibold text-white">Work Order Pipeline</span>
        <span className="ml-auto flex items-center gap-1.5 text-[10px] text-gray-500">
          <Database size={9} className="text-teal-400" />
          <span className="text-teal-400">{dbWOs.length} persisted</span>
          <span>· {merged.length} total</span>
        </span>
      </div>

      {/* Maintenance agent status */}
      {agent && (
        <div className="rounded-lg border border-orange-500/20 bg-orange-500/5 p-2.5">
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-semibold text-orange-400">{agent.name}</span>
            <span className={`ml-auto text-[9px] font-bold uppercase ${
              agent.status === 'acting' ? 'text-green-400 animate-pulse' : 'text-gray-500'
            }`}>{agent.status}</span>
          </div>
          <p className="text-[10px] text-gray-400 leading-relaxed line-clamp-2">{agent.current_action}</p>
        </div>
      )}

      {/* Refresh indicator */}
      {lastFetch > 0 && (
        <div className="flex items-center gap-1.5 text-[9px] text-gray-600">
          <RefreshCw size={8} />
          DB synced {timeAgo(Math.floor(lastFetch / 1000))}
        </div>
      )}

      {/* WO list */}
      <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto">
        {loading && (
          <p className="text-[10px] text-gray-600 py-2">Loading work orders from database…</p>
        )}
        {!loading && merged.length === 0 && (
          <p className="text-[10px] text-gray-600 py-2">No work orders yet — agents monitoring</p>
        )}
        {merged.map((wo, i) => {
          const StatusIcon = STATUS_ICON[wo.wo_status] ?? AlertCircle
          return (
            <div key={`${wo.wo_number}-${i}`} className="rounded-lg border border-white/6 bg-white/3 p-2.5">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-[10px] font-mono font-bold text-white">{wo.wo_number}</span>
                <span className={`text-[9px] font-bold border rounded px-1.5 py-0.5 ${PRI_STYLE[wo.priority] ?? PRI_STYLE.MEDIUM}`}>
                  {wo.priority}
                </span>
                {wo.source === 'db' && (
                  <Database size={8} className="text-teal-400 flex-shrink-0" title="Persisted to DB" />
                )}
                <StatusIcon size={10} className={`ml-auto ${STATUS_COLOR[wo.wo_status]}`} />
              </div>
              {wo.station_code && (
                <span className="inline-block text-[9px] font-mono text-gray-500 bg-white/5 px-1.5 py-0.5 rounded mb-1">
                  {wo.station_code}
                </span>
              )}
              <p className="text-[10px] text-gray-400 leading-snug line-clamp-2">{wo.description}</p>
              <p className="text-[9px] text-gray-600 mt-1">{timeAgo(wo.created_at)}</p>
            </div>
          )
        })}
      </div>
    </div>
  )
}
