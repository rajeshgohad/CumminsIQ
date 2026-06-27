import { AlertTriangle, TrendingDown, Brain } from 'lucide-react'
import type { Station } from '../../types/assembly'

interface Props { stations: Station[]; onRunPMAgent: (s: Station) => void }

function healthScore(s: Station): number {
  const tempPenalty = Math.max(0, (s.machine_temp - 68) * 1.8)
  const vibPenalty  = Math.max(0, (s.vibration - 0.28) * 55)
  const toolPenalty = Math.max(0, (100 - s.tool_life_pct) * 0.25)
  return Math.max(0, Math.min(100, 100 - tempPenalty - vibPenalty - toolPenalty))
}

function failureProbability(score: number): number {
  return Math.max(0, Math.min(99, Math.round((100 - score) * 1.1)))
}

function primaryRisk(s: Station): string {
  if (s.machine_temp > 86) return `Bearing overtemp — ${s.machine_temp.toFixed(1)}°C`
  if (s.vibration > 0.70)  return `Vibration anomaly — ${s.vibration.toFixed(2)}g RMS`
  if (s.tool_life_pct < 25) return `Tool near end-of-life — ${s.tool_life_pct.toFixed(0)}%`
  return 'General wear — multiple parameters elevated'
}

export default function CriticalEquipment({ stations, onRunPMAgent }: Props) {
  const critical = [...stations]
    .map(s => ({ ...s, score: healthScore(s) }))
    .sort((a, b) => a.score - b.score)
    .slice(0, 4)

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <AlertTriangle size={14} className="text-red-400" />
        <span className="text-xs font-semibold text-white">Critical Equipment — Failure Risk Ranking</span>
      </div>

      <div className="grid grid-cols-4 gap-2">
        {critical.map((s, rank) => {
          const prob = failureProbability(s.score)
          const probColor = prob > 60 ? 'text-red-400' : prob > 35 ? 'text-amber-400' : 'text-yellow-400'
          const barColor  = prob > 60 ? 'bg-red-500'  : prob > 35 ? 'bg-amber-500'  : 'bg-yellow-500'

          return (
            <div key={s.id} className="rounded-xl border border-white/8 bg-white/3 p-3">
              <div className="flex items-center gap-2 mb-2">
                <span className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold flex-shrink-0 ${
                  rank === 0 ? 'bg-red-500/30 text-red-300' :
                  rank === 1 ? 'bg-orange-500/30 text-orange-300' : 'bg-amber-500/20 text-amber-300'
                }`}>#{rank + 1}</span>
                <span className="text-[10px] font-mono text-gray-400">{s.code}</span>
                <TrendingDown size={10} className="ml-auto text-red-400" />
              </div>

              <p className="text-[10px] text-gray-300 font-medium mb-1">{s.name}</p>
              <p className="text-[9px] text-gray-500 mb-2">{s.machine}</p>

              {/* Failure probability */}
              <div className="mb-2">
                <div className="flex justify-between items-baseline mb-1">
                  <span className="text-[9px] text-gray-600">Failure Prob.</span>
                  <span className={`text-sm font-bold ${probColor}`}>{prob}%</span>
                </div>
                <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
                  <div className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                       style={{ width: `${prob}%` }} />
                </div>
              </div>

              {/* Health score */}
              <div className="flex justify-between text-[9px] mb-2">
                <span className="text-gray-600">Health Score</span>
                <span className={s.score < 40 ? 'text-red-400' : s.score < 60 ? 'text-amber-400' : 'text-yellow-400'}>
                  {s.score.toFixed(0)} / 100
                </span>
              </div>

              {/* Primary risk */}
              <div className="bg-white/4 rounded-lg p-1.5 mb-2">
                <p className="text-[9px] text-gray-500 mb-0.5">Primary Risk</p>
                <p className="text-[10px] text-gray-300 leading-snug">{primaryRisk(s)}</p>
              </div>

              {/* PM Agent button */}
              <button
                onClick={() => onRunPMAgent(s)}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 rounded-lg border border-orange-500/30 bg-orange-500/8 text-orange-400 hover:bg-orange-500/15 hover:text-white transition-all text-[10px] font-semibold"
              >
                <Brain size={10} />
                Run PM Agent
              </button>
            </div>
          )
        })}
      </div>
    </div>
  )
}
