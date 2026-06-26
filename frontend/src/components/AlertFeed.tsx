import { AlertTriangle, AlertCircle, Info, Clock } from 'lucide-react'
import type { Alert, Severity } from '../types'

function timeAgo(ts: number): string {
  const s = Math.floor(Date.now() / 1000 - ts)
  if (s < 60) return `${s}s ago`
  if (s < 3600) return `${Math.floor(s / 60)}m ago`
  return `${Math.floor(s / 3600)}h ago`
}

function SeverityIcon({ severity }: { severity: Severity }) {
  if (severity === 'critical') return <AlertTriangle size={14} className="text-red-400 flex-shrink-0" />
  if (severity === 'warning')  return <AlertCircle  size={14} className="text-amber-400 flex-shrink-0" />
  return <Info size={14} className="text-blue-400 flex-shrink-0" />
}

const BU_LABELS: Record<string, string> = {
  engine:     'Engine',
  powgen:     'Power Gen',
  filtration: 'Filtration',
  component:  'Component',
}

const BU_COLORS: Record<string, string> = {
  engine:     'bg-blue-500/20 text-blue-300',
  powgen:     'bg-purple-500/20 text-purple-300',
  filtration: 'bg-teal-500/20 text-teal-300',
  component:  'bg-orange-500/20 text-orange-300',
}

function AlertRow({ alert }: { alert: Alert }) {
  const rowBg =
    alert.severity === 'critical' ? 'border-l-2 border-red-500 bg-red-500/5' :
    alert.severity === 'warning'  ? 'border-l-2 border-amber-500 bg-amber-500/5' :
    'border-l-2 border-blue-500/40 bg-blue-500/5'

  return (
    <div className={`flex items-start gap-3 px-4 py-2.5 rounded-lg ${rowBg}`}>
      <div className="mt-0.5">
        <SeverityIcon severity={alert.severity} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-gray-200 text-xs leading-snug">{alert.message}</p>
        <div className="flex items-center gap-2 mt-1">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${BU_COLORS[alert.bu] || 'bg-gray-700 text-gray-300'}`}>
            {BU_LABELS[alert.bu] || alert.bu}
          </span>
          <span className="text-[10px] text-gray-600 font-mono">{alert.asset}</span>
          <span className="text-[10px] text-gray-600 flex items-center gap-0.5 ml-auto">
            <Clock size={9} /> {timeAgo(alert.timestamp)}
          </span>
        </div>
      </div>
    </div>
  )
}

interface AlertFeedProps {
  alerts: Alert[]
}

export default function AlertFeed({ alerts }: AlertFeedProps) {
  const critical = alerts.filter(a => a.severity === 'critical').length
  const warning  = alerts.filter(a => a.severity === 'warning').length

  return (
    <div className="card overflow-hidden">
      <div className="flex items-center justify-between px-5 py-3 border-b border-gray-800">
        <div className="flex items-center gap-2">
          <AlertTriangle size={15} className="text-amber-400" />
          <span className="text-white font-semibold text-sm">Live Alert Feed</span>
          <span className="text-gray-500 text-xs">— real-time across all BUs</span>
        </div>
        <div className="flex items-center gap-3 text-xs">
          {critical > 0 && (
            <span className="flex items-center gap-1 text-red-400">
              <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              {critical} critical
            </span>
          )}
          {warning > 0 && (
            <span className="flex items-center gap-1 text-amber-400">
              <span className="w-2 h-2 rounded-full bg-amber-400" />
              {warning} warning
            </span>
          )}
          <span className="text-gray-600">{alerts.length} total</span>
        </div>
      </div>
      <div className="p-4 flex flex-col gap-1.5 max-h-64 overflow-y-auto">
        {alerts.length === 0 ? (
          <p className="text-gray-600 text-sm text-center py-6">No active alerts</p>
        ) : (
          alerts.map(a => <AlertRow key={a.id} alert={a} />)
        )}
      </div>
    </div>
  )
}
