import { Gauge, TrendingUp, Clock, AlertOctagon } from 'lucide-react'
import type { LineMetrics as LM, Station } from '../../types/assembly'

interface Props { line: LM; stations: Station[] }

export default function LineMetrics({ line, stations }: Props) {
  const critical = stations.filter(s => s.status === 'critical').length
  const warning  = stations.filter(s => s.status === 'warning').length

  const oeeColor = line.oee >= 85 ? 'text-green-400' : line.oee >= 70 ? 'text-amber-400' : 'text-red-400'
  const prodColor = line.production_per_hour >= line.target_per_hour ? 'text-green-400' : 'text-amber-400'

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      <div className="card-inner rounded-xl p-3">
        <div className="flex items-center gap-2 mb-1">
          <Gauge size={13} className="text-blue-400" />
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">OEE</span>
        </div>
        <div className={`text-2xl font-bold ${oeeColor}`}>{line.oee}%</div>
        <div className="text-[9px] text-gray-600 mt-0.5">Line A — Columbus IN</div>
      </div>

      <div className="card-inner rounded-xl p-3">
        <div className="flex items-center gap-2 mb-1">
          <TrendingUp size={13} className="text-green-400" />
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Production</span>
        </div>
        <div className={`text-2xl font-bold ${prodColor}`}>{line.production_per_hour}</div>
        <div className="text-[9px] text-gray-600 mt-0.5">engines/hr · target {line.target_per_hour}</div>
      </div>

      <div className="card-inner rounded-xl p-3">
        <div className="flex items-center gap-2 mb-1">
          <Clock size={13} className="text-purple-400" />
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Shift {line.shift}</span>
        </div>
        <div className="text-2xl font-bold text-white">{line.production_today}</div>
        <div className="text-[9px] text-gray-600 mt-0.5">{line.shift_start}–{line.shift_end} · pcs today</div>
      </div>

      <div className="card-inner rounded-xl p-3">
        <div className="flex items-center gap-2 mb-1">
          <AlertOctagon size={13} className={critical > 0 ? 'text-red-400' : 'text-amber-400'} />
          <span className="text-[10px] text-gray-500 uppercase tracking-wider">Stations</span>
        </div>
        <div className="flex items-baseline gap-1">
          {critical > 0 && <span className="text-2xl font-bold text-red-400">{critical}</span>}
          {critical > 0 && <span className="text-xs text-gray-600">critical</span>}
          {warning > 0 && <span className="text-2xl font-bold text-amber-400 ml-1">{warning}</span>}
          {warning > 0 && <span className="text-xs text-gray-600">warn</span>}
          {critical === 0 && warning === 0 && <span className="text-2xl font-bold text-green-400">OK</span>}
        </div>
        <div className="text-[9px] text-gray-600 mt-0.5">bottleneck: {line.bottleneck_station}</div>
      </div>
    </div>
  )
}
