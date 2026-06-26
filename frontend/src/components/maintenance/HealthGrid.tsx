import { Thermometer, Activity, Wrench, ShieldAlert } from 'lucide-react'
import type { Station } from '../../types/assembly'

interface Props { stations: Station[] }

function healthScore(s: Station): number {
  const tempPenalty  = Math.max(0, (s.machine_temp - 68) * 1.8)
  const vibPenalty   = Math.max(0, (s.vibration - 0.28) * 55)
  const toolPenalty  = Math.max(0, (100 - s.tool_life_pct) * 0.25)
  return Math.max(0, Math.min(100, 100 - tempPenalty - vibPenalty - toolPenalty))
}

function rul(score: number): { label: string; color: string } {
  if (score >= 80) return { label: '30+ days',    color: 'text-green-400' }
  if (score >= 65) return { label: '7–30 days',   color: 'text-green-400' }
  if (score >= 50) return { label: '2–7 days',    color: 'text-amber-400' }
  if (score >= 35) return { label: '24–48 h',     color: 'text-orange-400' }
  return                 { label: '< 24 h',       color: 'text-red-400' }
}

const SCORE_STYLE = (score: number) =>
  score >= 75 ? 'border-green-500/30 bg-green-500/5' :
  score >= 50 ? 'border-amber-500/30 bg-amber-500/5' :
  score >= 30 ? 'border-orange-500/40 bg-orange-500/8' :
               'border-red-500/50 bg-red-500/10'

const SCORE_COLOR = (score: number) =>
  score >= 75 ? 'text-green-400' :
  score >= 50 ? 'text-amber-400' :
  score >= 30 ? 'text-orange-400' : 'text-red-400'

const BAR_COLOR = (score: number) =>
  score >= 75 ? 'bg-green-500' :
  score >= 50 ? 'bg-amber-500' :
  score >= 30 ? 'bg-orange-500' : 'bg-red-500'

export default function HealthGrid({ stations }: Props) {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <ShieldAlert size={14} className="text-teal-400" />
        <span className="text-xs font-semibold text-white">Equipment Health Map — All 12 Stations</span>
      </div>
      <div className="grid grid-cols-4 gap-2">
        {stations.map(s => {
          const score = healthScore(s)
          const { label, color } = rul(score)
          return (
            <div key={s.id} className={`rounded-xl border p-2.5 ${SCORE_STYLE(score)}`}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-[10px] font-mono text-gray-500">{s.code}</span>
                <span className={`text-sm font-bold ${SCORE_COLOR(score)}`}>{score.toFixed(0)}</span>
              </div>
              <p className="text-[9px] text-gray-500 truncate mb-2">{s.name}</p>

              {/* Health bar */}
              <div className="h-1 bg-gray-700 rounded-full mb-2">
                <div className={`h-full rounded-full transition-all duration-700 ${BAR_COLOR(score)}`}
                     style={{ width: `${score}%` }} />
              </div>

              {/* Params */}
              <div className="space-y-0.5">
                <div className="flex items-center justify-between text-[9px]">
                  <span className="flex items-center gap-1 text-gray-600"><Thermometer size={7}/></span>
                  <span className={s.machine_temp > 86 ? 'text-red-400' : s.machine_temp > 82 ? 'text-amber-400' : 'text-gray-500'}>
                    {s.machine_temp.toFixed(1)}°C
                  </span>
                </div>
                <div className="flex items-center justify-between text-[9px]">
                  <span className="flex items-center gap-1 text-gray-600"><Activity size={7}/></span>
                  <span className={s.vibration > 0.75 ? 'text-red-400' : s.vibration > 0.60 ? 'text-amber-400' : 'text-gray-500'}>
                    {s.vibration.toFixed(2)}g
                  </span>
                </div>
                <div className="flex items-center justify-between text-[9px]">
                  <span className="flex items-center gap-1 text-gray-600"><Wrench size={7}/></span>
                  <span className={s.tool_life_pct < 15 ? 'text-red-400' : s.tool_life_pct < 30 ? 'text-amber-400' : 'text-gray-500'}>
                    {s.tool_life_pct.toFixed(0)}%
                  </span>
                </div>
              </div>

              {/* RUL */}
              <div className="mt-2 pt-1.5 border-t border-white/5 flex justify-between items-center">
                <span className="text-[9px] text-gray-600">RUL</span>
                <span className={`text-[9px] font-semibold ${color}`}>{label}</span>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
