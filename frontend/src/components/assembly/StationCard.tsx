import { Bot, Thermometer, Activity, Wrench } from 'lucide-react'
import type { Station } from '../../types/assembly'

interface Props { station: Station }

const STATUS_STYLES: Record<string, string> = {
  running:  'border-green-500/40 bg-green-500/5',
  warning:  'border-amber-500/40 bg-amber-500/5',
  critical: 'border-red-500/60 bg-red-500/10',
  idle:     'border-gray-600/40 bg-gray-800/30',
  blocked:  'border-orange-500/40 bg-orange-500/5',
}

const STATUS_DOT: Record<string, string> = {
  running:  'bg-green-400',
  warning:  'bg-amber-400 animate-pulse',
  critical: 'bg-red-400 animate-ping',
  idle:     'bg-gray-500',
  blocked:  'bg-orange-400 animate-pulse',
}

const STATUS_LABEL: Record<string, string> = {
  running:  'RUNNING',
  warning:  'WARNING',
  critical: 'CRITICAL',
  idle:     'IDLE',
  blocked:  'BLOCKED',
}

export default function StationCard({ station }: Props) {
  const variance = ((station.actual_ct / station.target_ct) - 1) * 100
  const barPct = Math.min(100, (station.actual_ct / (station.target_ct * 1.4)) * 100)
  const barColor = station.status === 'critical' ? 'bg-red-500' :
                   station.status === 'warning'  ? 'bg-amber-500' : 'bg-green-500'

  const tempColor = station.machine_temp > 88 ? 'text-red-400' :
                    station.machine_temp > 83 ? 'text-amber-400' : 'text-gray-400'
  const vibColor  = station.vibration > 0.78 ? 'text-red-400' :
                    station.vibration > 0.65 ? 'text-amber-400' : 'text-gray-400'
  const toolColor = station.tool_life_pct < 15 ? 'text-red-400' :
                    station.tool_life_pct < 30 ? 'text-amber-400' : 'text-gray-400'

  return (
    <div className={`rounded-xl border p-3 relative transition-all duration-500 ${STATUS_STYLES[station.status]}`}>
      {/* Agent watching indicator */}
      {station.agent_active && (
        <div className="absolute top-2 right-2 flex items-center gap-1 bg-blue-500/20 border border-blue-500/40 rounded-full px-2 py-0.5">
          <Bot size={10} className="text-blue-400 animate-pulse" />
          <span className="text-[9px] text-blue-400 font-mono">AGENT</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`relative w-2 h-2 rounded-full ${STATUS_DOT[station.status]}`} />
        <span className="text-[10px] font-mono text-gray-500">{station.code}</span>
        <span className={`ml-auto text-[9px] font-bold tracking-widest ${
          station.status === 'critical' ? 'text-red-400' :
          station.status === 'warning'  ? 'text-amber-400' : 'text-green-400'
        }`}>{STATUS_LABEL[station.status]}</span>
      </div>

      <p className="text-xs text-white font-medium leading-tight mb-2 pr-12">{station.name}</p>

      {/* Cycle time bar */}
      <div className="mb-2">
        <div className="flex justify-between text-[9px] text-gray-500 mb-1">
          <span>Cycle Time</span>
          <span className={variance > 10 ? 'text-amber-400' : variance > 20 ? 'text-red-400' : 'text-gray-400'}>
            {station.actual_ct}s / {station.target_ct}s
            {variance > 0 && <span className="ml-1 text-amber-400">+{variance.toFixed(0)}%</span>}
          </span>
        </div>
        <div className="h-1.5 bg-gray-700 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-700 ${barColor}`}
            style={{ width: `${barPct}%` }}
          />
        </div>
      </div>

      {/* Machine params */}
      <div className="grid grid-cols-3 gap-1 text-[9px]">
        <div className="flex items-center gap-1">
          <Thermometer size={9} className={tempColor} />
          <span className={tempColor}>{station.machine_temp.toFixed(1)}°C</span>
        </div>
        <div className="flex items-center gap-1">
          <Activity size={9} className={vibColor} />
          <span className={vibColor}>{station.vibration.toFixed(2)}g</span>
        </div>
        <div className="flex items-center gap-1">
          <Wrench size={9} className={toolColor} />
          <span className={toolColor}>{station.tool_life_pct.toFixed(0)}%</span>
        </div>
      </div>

      {/* Operator */}
      <div className="mt-2 pt-2 border-t border-white/5 flex justify-between items-center">
        <span className="text-[9px] text-gray-600">{station.operator}</span>
        <span className="text-[9px] text-gray-600">{station.parts_count} pcs</span>
      </div>
    </div>
  )
}
