import { useEffect, useState } from 'react'
import { Shield, TrendingUp, Eye, Zap, Clock } from 'lucide-react'
import { API_BASE } from '../../lib/api'

const MTTR_MIN        = 45   // assumed mins per maintenance intervention
const CT_RECOVERY_MIN = 10   // assumed mins recovered per cycle-time intervention
const SCHED_GAIN_MIN  = 15   // assumed mins recovered per scheduling optimization
const AVG_TAKT_S      = 60   // average takt time (seconds)
const SHIFT_H         = 8

interface AgentEvent {
  id: number
  timestamp: number
  from_agent: string
  type: string
  severity: string
  message: string
  station: string | null
}

function shiftHoursElapsed(events: AgentEvent[]): number {
  const cutoff = Math.floor(Date.now() / 1000) - SHIFT_H * 3600
  const oldest = events.find(e => e.timestamp >= cutoff)
  if (!oldest) return 0
  const elapsedSec = Math.floor(Date.now() / 1000) - oldest.timestamp
  return Math.min(Math.round(elapsedSec / 3600 * 10) / 10, SHIFT_H)
}

export default function ShiftImpactBar() {
  const [events, setEvents] = useState<AgentEvent[]>([])

  const load = () =>
    fetch(`${API_BASE}/api/agent-events?limit=500`)
      .then(r => r.json())
      .then(setEvents)
      .catch(() => {})

  useEffect(() => {
    load()
    const t = setInterval(load, 30_000)
    return () => clearInterval(t)
  }, [])

  const cutoff     = Math.floor(Date.now() / 1000) - SHIFT_H * 3600
  const shiftActs  = events.filter(e => e.timestamp >= cutoff && e.type === 'act')

  const maintCount   = shiftActs.filter(e => e.from_agent === 'maintenance').length
  const ctCount      = shiftActs.filter(e => e.from_agent === 'cycle_time').length
  const qualityCount = shiftActs.filter(e => e.from_agent === 'quality').length
  const schedCount   = shiftActs.filter(e => e.from_agent === 'scheduling').length

  const downtimeAvoided = maintCount * MTTR_MIN
  const minsRecovered   = ctCount * CT_RECOVERY_MIN + schedCount * SCHED_GAIN_MIN
  const enginesGained   = Math.round(minsRecovered * 60 / AVG_TAKT_S)
  const hoursElapsed    = shiftHoursElapsed(events)

  const tiles = [
    {
      icon:  Shield,
      color: 'text-orange-400',
      ring:  'border-orange-500/25 bg-orange-500/8',
      value: `${downtimeAvoided} min`,
      label: 'Downtime Avoided',
      detail: `${maintCount} proactive WO${maintCount !== 1 ? 's' : ''} · 45 min MTTR each`,
    },
    {
      icon:  TrendingUp,
      color: 'text-purple-400',
      ring:  'border-purple-500/25 bg-purple-500/8',
      value: `+${enginesGained} engines`,
      label: 'Throughput Recovered',
      detail: `${ctCount} CT + ${schedCount} scheduling interventions · ~${minsRecovered} min`,
    },
    {
      icon:  Eye,
      color: 'text-teal-400',
      ring:  'border-teal-500/25 bg-teal-500/8',
      value: `${qualityCount} unit${qualityCount !== 1 ? 's' : ''}`,
      label: 'Defects Caught',
      detail: 'Flagged before reaching downstream station',
    },
    {
      icon:  Zap,
      color: 'text-indigo-400',
      ring:  'border-indigo-500/25 bg-indigo-500/8',
      value: `${shiftActs.length} actions`,
      label: 'Total Agent Actions',
      detail: `Across ${SHIFT_H}h shift · ${hoursElapsed}h elapsed`,
    },
  ]

  return (
    <div className="rounded-xl border border-white/8 bg-[#0a0f1e] px-4 py-3">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={11} className="text-cummins-blue" />
        <span className="text-[10px] font-bold text-white tracking-wider uppercase">Shift Impact — Last 8 Hours</span>
        <span className="ml-2 text-[9px] text-gray-600">Agent-derived value · real-time</span>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {tiles.map(t => (
          <div key={t.label} className={`rounded-lg border p-3 ${t.ring}`}>
            <t.icon size={13} className={`${t.color} mb-2`} />
            <p className={`text-lg font-bold leading-none mb-1 ${t.color}`}>{t.value}</p>
            <p className="text-[11px] text-gray-200 font-medium">{t.label}</p>
            <p className="text-[9px] text-gray-500 mt-1 leading-snug">{t.detail}</p>
          </div>
        ))}
      </div>

      {/* How the numbers are derived — transparency note */}
      <p className="text-[9px] text-gray-700 mt-2 leading-relaxed">
        Downtime = maintenance acts × 45 min assumed MTTR · Throughput = (cycle-time + scheduling acts) × avg recovery ÷ 60s takt · Defects = quality act events
      </p>
    </div>
  )
}
