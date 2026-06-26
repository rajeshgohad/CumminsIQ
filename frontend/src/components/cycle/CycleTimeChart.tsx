import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine,
  ResponsiveContainer, Cell, CartesianGrid,
} from 'recharts'
import type { Station } from '../../types/assembly'

interface Props { stations: Station[] }

const CustomTooltip = ({ active, payload, label }: any) => {
  if (!active || !payload?.length) return null
  const d = payload[0]?.payload
  return (
    <div className="bg-[#1a2235] border border-gray-700 rounded-lg p-2 text-xs">
      <p className="text-gray-400 font-mono mb-1">{d?.fullCode}</p>
      <p className="text-gray-300">{d?.name}</p>
      <div className="mt-1 space-y-0.5">
        <p className="text-gray-500">Target: <span className="text-gray-300">{d?.target}s</span></p>
        <p className="text-gray-500">Actual: <span className={
          d?.status === 'critical' ? 'text-red-400' :
          d?.status === 'warning'  ? 'text-amber-400' : 'text-green-400'
        }>{d?.actual}s</span></p>
        {d?.variance > 0 && (
          <p className="text-amber-400">+{d?.variance}% over target</p>
        )}
      </div>
    </div>
  )
}

export default function CycleTimeChart({ stations }: Props) {
  const data = stations.map(s => ({
    code:     s.code.replace('STN-', ''),
    fullCode: s.code,
    name:     s.name,
    target:   s.target_ct,
    actual:   s.actual_ct,
    status:   s.status,
    variance: Math.max(0, ((s.actual_ct / s.target_ct - 1) * 100)),
  }))

  const maxY = Math.max(...data.map(d => Math.max(d.actual, d.target))) + 40

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs font-semibold text-white">Station Cycle Time vs Target</p>
        <div className="flex items-center gap-4 text-[10px] text-gray-500">
          <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2 bg-gray-600 rounded-sm"/> Target</span>
          <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2 bg-green-500 rounded-sm"/> On-Time</span>
          <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2 bg-amber-500 rounded-sm"/> Warning</span>
          <span className="flex items-center gap-1.5"><span className="inline-block w-3 h-2 bg-red-500 rounded-sm"/> Critical</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={230}>
        <BarChart data={data} barCategoryGap="25%" barGap={2}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" vertical={false} />
          <XAxis dataKey="code" tick={{ fontSize: 10, fill: '#6b7280', fontFamily: 'monospace' }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 10, fill: '#4b5563' }} axisLine={false} tickLine={false} domain={[0, maxY]} unit="s" />
          <Tooltip content={<CustomTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Bar dataKey="target" fill="#374151" radius={[2, 2, 0, 0]} maxBarSize={18} />
          <Bar dataKey="actual" radius={[2, 2, 0, 0]} maxBarSize={18}>
            {data.map((d, i) => (
              <Cell key={i} fill={
                d.status === 'critical' ? '#ef4444' :
                d.status === 'warning'  ? '#f59e0b' : '#22c55e'
              } />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
