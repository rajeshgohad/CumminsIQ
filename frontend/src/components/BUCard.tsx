import { AlertTriangle, TrendingUp, TrendingDown, Minus, MapPin, Bell } from 'lucide-react'
import { LineChart, Line, ResponsiveContainer, Tooltip } from 'recharts'
import GaugeChart from './GaugeChart'
import type { Status } from '../types'

interface MetricRowProps {
  label: string
  value: string | number
  highlight?: 'good' | 'warn' | 'bad' | 'neutral'
}

function MetricRow({ label, value, highlight = 'neutral' }: MetricRowProps) {
  const colors: Record<string, string> = {
    good: 'text-emerald-400',
    warn: 'text-amber-400',
    bad: 'text-red-400',
    neutral: 'text-white',
  }
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-gray-800/60 last:border-0">
      <span className="text-gray-400 text-xs">{label}</span>
      <span className={`text-xs font-semibold ${colors[highlight]}`}>{value}</span>
    </div>
  )
}

function StatusBadge({ status }: { status: Status }) {
  const cfg = {
    critical: { cls: 'bg-red-500/15 text-red-400 border-red-500/30', dot: 'bg-red-500', label: 'Critical' },
    warning:  { cls: 'bg-amber-500/15 text-amber-400 border-amber-500/30', dot: 'bg-amber-400', label: 'Warning' },
    normal:   { cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30', dot: 'bg-emerald-400', label: 'Normal' },
  }[status]

  return (
    <span className={`flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-[10px] font-semibold uppercase tracking-widest ${cfg.cls}`}>
      <span className={`w-1.5 h-1.5 rounded-full animate-pulse ${cfg.dot}`} />
      {cfg.label}
    </span>
  )
}

function TrendIcon({ history }: { history: number[] }) {
  if (history.length < 3) return <Minus size={14} className="text-gray-500" />
  const recent = history.slice(-3)
  const delta = recent[recent.length - 1] - recent[0]
  if (delta > 0.5) return <TrendingUp size={14} className="text-emerald-400" />
  if (delta < -0.5) return <TrendingDown size={14} className="text-red-400" />
  return <Minus size={14} className="text-gray-500" />
}

interface BUCardProps {
  title: string
  icon: React.ReactNode
  location: string
  status: Status
  primaryMetricLabel: string
  primaryMetric: number
  alertCount: number
  history: number[]
  metrics: MetricRowProps[]
  borderColor: string
}

export default function BUCard({
  title, icon, location, status, primaryMetricLabel,
  primaryMetric, alertCount, history, metrics, borderColor,
}: BUCardProps) {
  const sparkData = history.map((v, i) => ({ i, v }))

  const sparkColor =
    status === 'critical' ? '#EF4444' :
    status === 'warning'  ? '#F59E0B' :
    '#10B981'

  return (
    <div className={`card overflow-hidden border-t-2 ${borderColor}`}>
      {/* Card header */}
      <div className="flex items-start justify-between px-5 pt-4 pb-3 border-b border-gray-800">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-gray-800 flex items-center justify-center text-cummins-blue">
            {icon}
          </div>
          <div>
            <p className="text-white font-semibold text-sm leading-none">{title}</p>
            <p className="text-gray-500 text-[11px] flex items-center gap-1 mt-0.5">
              <MapPin size={9} /> {location}
            </p>
          </div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <StatusBadge status={status} />
          <span className={`flex items-center gap-1 text-[11px] font-medium ${
            alertCount > 4 ? 'text-red-400' : alertCount > 2 ? 'text-amber-400' : 'text-gray-400'
          }`}>
            <Bell size={10} /> {alertCount} alert{alertCount !== 1 ? 's' : ''}
          </span>
        </div>
      </div>

      {/* Gauge + sparkline */}
      <div className="flex items-center justify-between px-5 py-4">
        <div className="flex flex-col items-center">
          <GaugeChart value={primaryMetric} label={primaryMetricLabel} />
          <p className="text-gray-500 text-[10px] mt-1 uppercase tracking-widest">{primaryMetricLabel}</p>
        </div>

        <div className="flex-1 ml-4">
          <div className="flex items-center gap-1 mb-1">
            <TrendIcon history={history} />
            <span className="text-gray-500 text-[10px]">Last {history.length} updates</span>
          </div>
          <ResponsiveContainer width="100%" height={56}>
            <LineChart data={sparkData}>
              <Line
                type="monotone"
                dataKey="v"
                stroke={sparkColor}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
              <Tooltip
                contentStyle={{ background: '#1F2937', border: 'none', borderRadius: '6px', fontSize: '11px' }}
                formatter={(v: number) => [`${v.toFixed(1)}%`, primaryMetricLabel]}
                labelFormatter={() => ''}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Metrics list */}
      <div className="px-5 pb-4">
        <div className="card-inner px-3 py-1">
          {metrics.map((m) => (
            <MetricRow key={m.label} {...m} />
          ))}
        </div>
      </div>
    </div>
  )
}
