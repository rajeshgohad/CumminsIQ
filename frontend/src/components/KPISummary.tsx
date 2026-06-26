import { AlertTriangle, Activity, Clock, Building2 } from 'lucide-react'
import type { Summary } from '../types'

interface KPISummaryProps {
  summary: Summary
}

interface KPITileProps {
  icon: React.ReactNode
  label: string
  value: string | number
  sub: string
  accent: string
}

function KPITile({ icon, label, value, sub, accent }: KPITileProps) {
  return (
    <div className="card px-5 py-4 flex items-center gap-4">
      <div className={`w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 ${accent}`}>
        {icon}
      </div>
      <div>
        <p className="text-gray-400 text-xs uppercase tracking-widest font-medium">{label}</p>
        <p className="text-white text-2xl font-bold leading-tight mt-0.5">{value}</p>
        <p className="text-gray-500 text-xs mt-0.5">{sub}</p>
      </div>
    </div>
  )
}

export default function KPISummary({ summary }: KPISummaryProps) {
  const alertColor =
    summary.total_alerts > 12 ? 'bg-red-500/15 text-red-400' :
    summary.total_alerts > 6  ? 'bg-amber-500/15 text-amber-400' :
    'bg-emerald-500/15 text-emerald-400'

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KPITile
        icon={<AlertTriangle size={20} />}
        label="Active Alerts"
        value={summary.total_alerts}
        sub="Across all 4 BUs"
        accent={alertColor}
      />
      <KPITile
        icon={<Activity size={20} />}
        label="Platform Score"
        value={`${summary.overall_score}%`}
        sub="Weighted avg OEE / health"
        accent={
          summary.overall_score >= 85 ? 'bg-emerald-500/15 text-emerald-400' :
          summary.overall_score >= 75 ? 'bg-amber-500/15 text-amber-400' :
          'bg-red-500/15 text-red-400'
        }
      />
      <KPITile
        icon={<Clock size={20} />}
        label="Downtime Today"
        value={`${summary.total_downtime}h`}
        sub="Engine BU — Columbus IN"
        accent={
          summary.total_downtime < 1 ? 'bg-emerald-500/15 text-emerald-400' :
          summary.total_downtime < 3 ? 'bg-amber-500/15 text-amber-400' :
          'bg-red-500/15 text-red-400'
        }
      />
      <KPITile
        icon={<Building2 size={20} />}
        label="Plants Online"
        value={`${summary.plants_online} / 12`}
        sub="Monitored globally"
        accent="bg-cummins-blue/15 text-cummins-blue"
      />
    </div>
  )
}
