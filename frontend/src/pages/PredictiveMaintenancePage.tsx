import { useState } from 'react'
import { Loader2, ShieldCheck, AlertTriangle, ClipboardList, TrendingDown } from 'lucide-react'
import { useAssemblySocket } from '../hooks/useAssemblySocket'
import HealthGrid from '../components/maintenance/HealthGrid'
import CriticalEquipment from '../components/maintenance/CriticalEquipment'
import WorkOrders from '../components/maintenance/WorkOrders'
import PMAgentModal from '../components/maintenance/PMAgentModal'
import type { Station } from '../types/assembly'

interface Props { apiKey: string }

function healthScore(s: { machine_temp: number; vibration: number; tool_life_pct: number }): number {
  const t = Math.max(0, (s.machine_temp - 68) * 1.8)
  const v = Math.max(0, (s.vibration - 0.28) * 55)
  const l = Math.max(0, (100 - s.tool_life_pct) * 0.25)
  return Math.max(0, Math.min(100, 100 - t - v - l))
}

export default function PredictiveMaintenancePage({ apiKey }: Props) {
  const { data } = useAssemblySocket()
  const [pmStation, setPmStation] = useState<Station | null>(null)

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-cummins-blue" />
      </div>
    )
  }

  const scores = data.stations.map(s => healthScore(s))
  const avgHealth = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
  const critical = scores.filter(s => s < 40).length
  const warning  = scores.filter(s => s >= 40 && s < 65).length
  const woCount  = data.activity_log.filter(e => e.from_agent === 'maintenance' && e.type === 'act').length

  return (
    <>
    <div className="flex-1 flex flex-col gap-4 p-4 overflow-y-auto">
      {/* Header metrics */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <ShieldCheck size={13} className="text-teal-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Avg Health</span>
          </div>
          <div className={`text-xl font-bold ${parseFloat(avgHealth) >= 70 ? 'text-green-400' : parseFloat(avgHealth) >= 50 ? 'text-amber-400' : 'text-red-400'}`}>
            {avgHealth}
          </div>
          <div className="text-[9px] text-gray-600 mt-0.5">/ 100 across 12 stations</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <TrendingDown size={13} className="text-red-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Critical</span>
          </div>
          <div className={`text-xl font-bold ${critical > 0 ? 'text-red-400' : 'text-green-400'}`}>{critical}</div>
          <div className="text-[9px] text-gray-600 mt-0.5">equipment health &lt; 40</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertTriangle size={13} className="text-amber-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">At Risk</span>
          </div>
          <div className={`text-xl font-bold ${warning > 0 ? 'text-amber-400' : 'text-green-400'}`}>{warning}</div>
          <div className="text-[9px] text-gray-600 mt-0.5">equipment health 40–65</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <ClipboardList size={13} className="text-orange-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Work Orders</span>
          </div>
          <div className="text-xl font-bold text-orange-400">{woCount}</div>
          <div className="text-[9px] text-gray-600 mt-0.5">created this session</div>
        </div>
      </div>

      {/* Health grid + Work orders */}
      <div className="grid grid-cols-3 gap-4">
        <div className="col-span-2 card rounded-xl p-4">
          <HealthGrid stations={data.stations} />
        </div>
        <div className="card rounded-xl p-4">
          <WorkOrders log={data.activity_log} agent={data.agents?.maintenance} />
        </div>
      </div>

      {/* Critical equipment ranking */}
      <div className="card rounded-xl p-4">
        <CriticalEquipment stations={data.stations} onRunPMAgent={setPmStation} />
      </div>
    </div>

    {pmStation && (
      <PMAgentModal
        station={pmStation}
        apiKey={apiKey}
        onClose={() => setPmStation(null)}
      />
    )}
  </>
  )
}
