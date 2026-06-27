import { useEffect, useState } from 'react'
import { AlertOctagon, TrendingUp, Database, ScanSearch } from 'lucide-react'
import { API_BASE } from '../../lib/api'
import { LineChart, Line, ResponsiveContainer, ReferenceLine, Tooltip, YAxis } from 'recharts'
import type { Station } from '../../types/assembly'

interface Props {
  bottleneck: Station | null
  stations: Station[]
  apiKey?: string
  onInvestigate?: () => void
}

interface HistoryPoint { ts: number; actual_ct: number; status: string }

function getImpact(bottleneck: Station | null, stations: Station[]) {
  if (!bottleneck) return { blocked: [], starved: [] }
  const idx = stations.findIndex(s => s.id === bottleneck.id)
  const blocked = stations.slice(0, idx).filter(s => s.status !== 'running').map(s => s.code)
  const starved  = stations.slice(idx + 1).filter(s => s.status !== 'running').map(s => s.code)
  return { blocked: blocked.slice(-2), starved: starved.slice(0, 2) }
}

function getRootCause(station: Station): string {
  if (station.machine_temp > 86) return `Bearing temp ${station.machine_temp.toFixed(1)}°C → thermal expansion slowing cycle`
  if (station.vibration > 0.70)  return `Vibration ${station.vibration.toFixed(2)}g RMS → operator compensating, extra time`
  if (station.tool_life_pct < 25) return `Tool life ${station.tool_life_pct.toFixed(0)}% → worn tooling increases cycle time`
  return 'Operator-paced — possible component fit issue or missing parts'
}

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

export default function BottleneckDetail({ bottleneck, stations, apiKey, onInvestigate }: Props) {
  const [history, setHistory] = useState<HistoryPoint[]>([])

  useEffect(() => {
    if (!bottleneck) return
    setHistory([])   // clear on station change

    const load = () =>
      fetch(`${API_BASE}/api/station-history/${bottleneck.code}?hours=1`)
        .then(r => r.json())
        .then((rows: HistoryPoint[]) => setHistory(rows))
        .catch(() => {})

    load()
    const t = setInterval(load, 10_000)
    return () => clearInterval(t)
  }, [bottleneck?.code])

  if (!bottleneck) return null

  const { blocked, starved } = getImpact(bottleneck, stations)
  const variance  = ((bottleneck.actual_ct / bottleneck.target_ct - 1) * 100)
  const rootCause = getRootCause(bottleneck)
  const chartData = history.map(h => ({ t: fmtTime(h.ts), ct: h.actual_ct }))

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <AlertOctagon size={14} className="text-red-400" />
        <span className="text-xs font-semibold text-white">Bottleneck Analysis</span>
        <span className="ml-auto text-[10px] font-mono text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded-full animate-pulse">
          ACTIVE BOTTLENECK
        </span>
        {apiKey && onInvestigate && (
          <button
            onClick={onInvestigate}
            className="flex items-center gap-1 text-[9px] font-semibold text-orange-400 hover:text-white border border-orange-500/30 bg-orange-500/8 hover:bg-orange-500/20 rounded px-2 py-0.5 transition-all"
          >
            <ScanSearch size={9} />
            Investigate with AI Agent
          </button>
        )}
      </div>

      {/* Main bottleneck highlight */}
      <div className="rounded-xl border border-red-500/40 bg-red-500/8 p-3">
        <div className="flex items-baseline gap-2 mb-1">
          <span className="text-2xl font-bold text-red-400">{bottleneck.code}</span>
          <span className="text-sm text-gray-400">{bottleneck.name}</span>
        </div>

        <div className="grid grid-cols-2 gap-3 mt-3">
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Actual CT</p>
            <p className="text-xl font-bold text-red-400">{bottleneck.actual_ct}s</p>
          </div>
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Target CT</p>
            <p className="text-xl font-bold text-gray-300">{bottleneck.target_ct}s</p>
          </div>
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Over Target</p>
            <p className="text-xl font-bold text-amber-400">+{variance.toFixed(1)}%</p>
          </div>
          <div>
            <p className="text-[9px] text-gray-600 uppercase tracking-wider mb-0.5">Operator</p>
            <p className="text-sm font-medium text-white">{bottleneck.operator}</p>
          </div>
        </div>
      </div>

      {/* Historical CT sparkline */}
      <div className="rounded-lg border border-gray-700/50 bg-white/3 p-2.5">
        <div className="flex items-center gap-2 mb-2">
          <TrendingUp size={11} className="text-blue-400" />
          <span className="text-[10px] font-semibold text-gray-400">Cycle Time History (last hour)</span>
          {history.length > 0 && (
            <span className="ml-auto flex items-center gap-1 text-[9px] text-teal-400">
              <Database size={8} />
              {history.length} readings
            </span>
          )}
        </div>
        {chartData.length === 0 ? (
          <p className="text-[10px] text-gray-600 py-2">Accumulating data…</p>
        ) : (
          <ResponsiveContainer width="100%" height={70}>
            <LineChart data={chartData} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
              <YAxis domain={['auto', 'auto']} hide />
              <ReferenceLine
                y={bottleneck.target_ct}
                stroke="#6b7280"
                strokeDasharray="3 3"
                strokeWidth={1}
              />
              <Tooltip
                contentStyle={{ background: '#0D1220', border: '1px solid #374151', borderRadius: 6, fontSize: 10 }}
                labelStyle={{ color: '#9ca3af' }}
                formatter={(v: number) => [`${v}s`, 'Cycle Time']}
                labelFormatter={l => `${l}`}
              />
              <Line
                dataKey="ct"
                stroke="#f87171"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>

      {/* Root cause */}
      <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-2.5">
        <p className="text-[10px] text-amber-400 font-semibold uppercase tracking-wider mb-1">Root Cause (AI Analysis)</p>
        <p className="text-[11px] text-gray-300 leading-relaxed">{rootCause}</p>
      </div>

      {/* Cascade impact */}
      {(blocked.length > 0 || starved.length > 0) && (
        <div className="rounded-lg border border-gray-700/50 bg-white/3 p-2.5">
          <p className="text-[10px] text-gray-500 font-semibold uppercase tracking-wider mb-2">Cascade Impact</p>
          <div className="flex flex-col gap-1.5">
            {blocked.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded px-1.5 py-0.5">BLOCKED</span>
                <span className="text-[10px] text-gray-400">{blocked.join(', ')} — waiting for downstream clearance</span>
              </div>
            )}
            {starved.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-[9px] text-blue-400 bg-blue-500/10 border border-blue-500/20 rounded px-1.5 py-0.5">STARVED</span>
                <span className="text-[10px] text-gray-400">{starved.join(', ')} — waiting for input from bottleneck</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
