import { Lightbulb, TrendingUp, AlertTriangle, Clock } from 'lucide-react'
import type { Station } from '../../types/assembly'

interface Props { stations: Station[] }

interface Rec {
  priority: 'high' | 'medium' | 'low'
  action: string
  rationale: string
  gain: string
}

function generateRecs(stations: Station[]): Rec[] {
  const recs: Rec[] = []

  // Bottleneck rebalancing
  const bottleneck = [...stations].sort((a, b) => (b.actual_ct / b.target_ct) - (a.actual_ct / a.target_ct))[0]
  const lightest = [...stations].sort((a, b) => (a.actual_ct / a.target_ct) - (b.actual_ct / b.target_ct))[0]
  if (bottleneck && bottleneck.actual_ct > bottleneck.target_ct * 1.10) {
    recs.push({
      priority: 'high',
      action: `Reallocate 1 operator from ${lightest.code} → ${bottleneck.code}`,
      rationale: `${bottleneck.code} is ${((bottleneck.actual_ct / bottleneck.target_ct - 1) * 100).toFixed(0)}% over takt. ${lightest.code} has capacity headroom.`,
      gain: `+3–5 engines/shift`,
    })
  }

  // Tool change
  const wornTools = stations.filter(s => s.tool_life_pct < 28)
  wornTools.slice(0, 2).forEach(s => {
    recs.push({
      priority: s.tool_life_pct < 15 ? 'high' : 'medium',
      action: `Schedule tool change at ${s.code} — next available break`,
      rationale: `Tool life ${s.tool_life_pct.toFixed(0)}% remaining. Below 15% risks unplanned stoppage.`,
      gain: `Prevents ~45 min unplanned downtime`,
    })
  })

  // Temp warning
  const hotMachines = stations.filter(s => s.machine_temp > 85)
  hotMachines.slice(0, 1).forEach(s => {
    recs.push({
      priority: 'high',
      action: `Reduce feed rate 15% at ${s.code} to lower bearing temp`,
      rationale: `Bearing temp ${s.machine_temp.toFixed(1)}°C. Threshold 87°C. Risk of thermal seizure.`,
      gain: `Prevents bearing failure (~4h downtime)`,
    })
  })

  // Batch resequencing
  const ctViolations = stations.filter(s => s.actual_ct > s.target_ct * 1.12)
  if (ctViolations.length >= 2) {
    recs.push({
      priority: 'medium',
      action: 'Resequence batch: move variant B ahead of C in production order',
      rationale: `${ctViolations.length} stations over takt. Smaller variant B relieves pressure on bottleneck stations.`,
      gain: `+4 engines/shift (est.)`,
    })
  }

  // Preventive suggestion
  if (recs.length < 3) {
    recs.push({
      priority: 'low',
      action: 'Pre-stage turbocharger components 20 min before STN-07 demand',
      rationale: 'Eliminates 8s average wait time for component delivery at turbo mount station.',
      gain: '+1–2 engines/shift',
    })
  }

  return recs.slice(0, 4)
}

const PRI_STYLE: Record<string, string> = {
  high:   'text-red-400 bg-red-500/10 border-red-500/20',
  medium: 'text-amber-400 bg-amber-500/10 border-amber-500/20',
  low:    'text-green-400 bg-green-500/10 border-green-500/20',
}

const PRI_DOT: Record<string, string> = {
  high: 'bg-red-400', medium: 'bg-amber-400', low: 'bg-green-400',
}

export default function AIRecommendations({ stations }: Props) {
  const recs = generateRecs(stations)

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2">
        <Lightbulb size={14} className="text-yellow-400" />
        <span className="text-xs font-semibold text-white">AI Scheduling Recommendations</span>
        <span className="ml-auto text-[10px] text-gray-500">{recs.length} active</span>
      </div>

      <div className="flex flex-col gap-2 flex-1">
        {recs.map((rec, i) => (
          <div key={i} className="rounded-lg border border-white/6 bg-white/3 p-3">
            <div className="flex items-center gap-2 mb-1.5">
              <div className={`w-1.5 h-1.5 rounded-full ${PRI_DOT[rec.priority]}`} />
              <span className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded border ${PRI_STYLE[rec.priority]}`}>
                {rec.priority}
              </span>
              <span className="ml-auto text-[9px] text-green-400 font-semibold">{rec.gain}</span>
            </div>
            <p className="text-[11px] text-white font-medium leading-snug mb-1">{rec.action}</p>
            <p className="text-[10px] text-gray-500 leading-relaxed">{rec.rationale}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
