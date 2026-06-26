import { useEffect, useState } from 'react'
import { ScanEye, CheckCircle2, XCircle, Activity, Layers } from 'lucide-react'
import CameraFeed from '../components/vision/CameraFeed'
import DefectLog from '../components/vision/DefectLog'
import { INSPECTIONS } from '../components/vision/InspectionScenes'
import type { ActivityLogEntry, Agent } from '../types/assembly'
import { useAssemblySocket } from '../hooks/useAssemblySocket'

function KpiTile({ label, value, sub, color }: { label: string; value: string | number; sub: string; color: string }) {
  return (
    <div className="card rounded-xl p-4">
      <p className={`text-[10px] font-semibold uppercase tracking-wider mb-1 ${color}`}>{label}</p>
      <p className="text-2xl font-bold text-white">{value}</p>
      <p className="text-[10px] text-gray-500 mt-0.5">{sub}</p>
    </div>
  )
}

function AgentStatus({ log }: { log: ActivityLogEntry[] }) {
  const qualityEvents = log.filter(e => e.from_agent === 'quality').slice(0, 3)
  return (
    <div className="card rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <ScanEye size={14} className="text-teal-400" />
        <span className="text-xs font-semibold text-white">Quality AI Agent</span>
        <span className="ml-auto text-[9px] font-bold text-teal-400 animate-pulse">● ACTIVE</span>
      </div>
      <div className="flex flex-col gap-1.5">
        {qualityEvents.length === 0 && (
          <p className="text-[10px] text-gray-600">AI vision scanning all stations…</p>
        )}
        {qualityEvents.map(e => (
          <div key={e.id} className="text-[10px] text-gray-400 border-l-2 border-teal-500/30 pl-2 leading-relaxed">
            {e.message}
          </div>
        ))}
      </div>
    </div>
  )
}

export default function VisionInspectionPage() {
  const { data } = useAssemblySocket()
  const [inspectedToday, setInspectedToday] = useState(1847)
  const [defectsFound, setDefectsFound]     = useState(23)
  const [passRate, setPassRate]             = useState(98.8)

  // Slowly update KPIs to look live
  useEffect(() => {
    const t = setInterval(() => {
      setInspectedToday(p => p + Math.floor(Math.random() * 3))
      if (Math.random() < 0.15) {
        setDefectsFound(p => p + 1)
        setPassRate(p => Math.max(97, p - 0.01))
      }
    }, 6000)
    return () => clearInterval(t)
  }, [])

  const log: ActivityLogEntry[] = data?.activity_log ?? []

  return (
    <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden">
      {/* KPI row */}
      <div className="grid grid-cols-4 gap-4">
        <KpiTile label="Inspections Today"  value={inspectedToday.toLocaleString()} sub="units across 6 check points"         color="text-teal-400" />
        <KpiTile label="Pass Rate"          value={`${passRate.toFixed(1)}%`}       sub="AI vision confidence ≥ 90%"           color="text-green-400" />
        <KpiTile label="Defects Caught"     value={defectsFound}                   sub="prevented from reaching next station"  color="text-red-400" />
        <KpiTile label="Cameras Active"     value="6 / 6"                          sub="60fps · 12MP · structured light"        color="text-blue-400" />
      </div>

      {/* Main content */}
      <div className="flex gap-4 flex-1 min-h-0">
        {/* Camera feed grid — 2/3 width */}
        <div className="flex-1 min-w-0 flex flex-col gap-3 overflow-y-auto">
          <div className="flex items-center gap-2">
            <Layers size={13} className="text-teal-400" />
            <span className="text-xs font-semibold text-white">Live Inspection Cameras</span>
            <span className="ml-auto text-[10px] text-gray-500">All feeds · real-time AI inference · 60fps</span>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {INSPECTIONS.map(insp => (
              <CameraFeed key={insp.id} inspection={insp} frameRate={insp.id === 'ring-gap' ? 7 : 6} />
            ))}
          </div>
        </div>

        {/* Right panel — agent status + defect log */}
        <div className="w-80 flex-shrink-0 flex flex-col gap-3">
          <AgentStatus log={log} />
          <div className="card rounded-xl p-4 flex-1 overflow-hidden flex flex-col min-h-0">
            <DefectLog />
          </div>
        </div>
      </div>
    </div>
  )
}
