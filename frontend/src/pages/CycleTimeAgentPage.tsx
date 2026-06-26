import { Loader2, Timer, TrendingUp, AlertOctagon, Target } from 'lucide-react'
import { useAssemblySocket } from '../hooks/useAssemblySocket'
import CycleTimeChart from '../components/cycle/CycleTimeChart'
import BottleneckDetail from '../components/cycle/BottleneckDetail'
import AgentReasoning from '../components/cycle/AgentReasoning'
import AIRecommendations from '../components/cycle/AIRecommendations'

export default function CycleTimeAgentPage() {
  const { data } = useAssemblySocket()

  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <Loader2 size={32} className="animate-spin text-cummins-blue" />
      </div>
    )
  }

  const sorted = [...data.stations].sort((a, b) => (b.actual_ct / b.target_ct) - (a.actual_ct / a.target_ct))
  const bottleneck = sorted[0]
  const overTarget = data.stations.filter(s => s.actual_ct > s.target_ct)
  const avgVariance = data.stations.reduce((sum, s) => sum + (s.actual_ct / s.target_ct - 1) * 100, 0) / data.stations.length
  const taktEff = Math.max(0, 100 - avgVariance).toFixed(1)

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 overflow-y-auto">
      {/* Header metrics */}
      <div className="grid grid-cols-4 gap-3">
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <AlertOctagon size={13} className="text-red-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Bottleneck</span>
          </div>
          <div className="text-xl font-bold text-red-400">{bottleneck?.code ?? '—'}</div>
          <div className="text-[9px] text-gray-600 mt-0.5 truncate">{bottleneck?.name}</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Target size={13} className="text-purple-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Takt Efficiency</span>
          </div>
          <div className={`text-xl font-bold ${parseFloat(taktEff) >= 90 ? 'text-green-400' : parseFloat(taktEff) >= 80 ? 'text-amber-400' : 'text-red-400'}`}>
            {taktEff}%
          </div>
          <div className="text-[9px] text-gray-600 mt-0.5">vs 100% ideal</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <Timer size={13} className="text-amber-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Over Takt</span>
          </div>
          <div className={`text-xl font-bold ${overTarget.length > 2 ? 'text-red-400' : overTarget.length > 0 ? 'text-amber-400' : 'text-green-400'}`}>
            {overTarget.length} / 12
          </div>
          <div className="text-[9px] text-gray-600 mt-0.5">stations exceeding target</div>
        </div>
        <div className="card-inner rounded-xl p-3">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp size={13} className="text-green-400" />
            <span className="text-[10px] text-gray-500 uppercase tracking-wider">Production</span>
          </div>
          <div className="text-xl font-bold text-white">{data.line.production_per_hour}</div>
          <div className="text-[9px] text-gray-600 mt-0.5">engines/hr · target {data.line.target_per_hour}</div>
        </div>
      </div>

      {/* Cycle time chart — full width */}
      <div className="card rounded-xl p-4">
        <CycleTimeChart stations={data.stations} />
      </div>

      {/* Bottom row: bottleneck + agent reasoning + recommendations */}
      <div className="grid grid-cols-3 gap-4 flex-1 min-h-0">
        <div className="card rounded-xl p-4">
          <BottleneckDetail bottleneck={bottleneck} stations={data.stations} />
        </div>
        <div className="card rounded-xl p-4">
          <AgentReasoning agents={data.agents} log={data.activity_log} />
        </div>
        <div className="card rounded-xl p-4">
          <AIRecommendations stations={data.stations} />
        </div>
      </div>
    </div>
  )
}
