import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import { useAssemblySocket } from '../hooks/useAssemblySocket'
import LineMetrics from '../components/assembly/LineMetrics'
import AssemblyLine from '../components/assembly/AssemblyLine'
import AgentPanel from '../components/assembly/AgentPanel'
import AgentActivityLog from '../components/assembly/AgentActivityLog'
import AnomalyDetailModal from '../components/assembly/AnomalyDetailModal'
import ShiftImpactBar from '../components/assembly/ShiftImpactBar'
import type { Page } from '../components/Header'
import type { ActivityLogEntry } from '../types/assembly'

interface Props { onPageChange: (p: Page) => void; apiKey: string }

export default function AssemblyLineDashboard({ onPageChange, apiKey }: Props) {
  const { data, connectionState } = useAssemblySocket()
  const [selectedEntry, setSelectedEntry] = useState<ActivityLogEntry | null>(null)

  if (!data) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-500">
        <Loader2 size={32} className="animate-spin text-cummins-blue" />
        <p className="text-white font-medium">Loading Assembly Line feed…</p>
        {connectionState === 'disconnected' && (
          <p className="text-sm text-red-400">Connection lost — retrying…</p>
        )}
      </div>
    )
  }

  return (
    <>
      <div className="flex-1 flex flex-col gap-4 p-4 overflow-hidden">
        {/* Shift impact */}
        <ShiftImpactBar />

        {/* KPI row */}
        <LineMetrics line={data.line} stations={data.stations} />

        {/* Main content: assembly line (left) + agent panel (right) */}
        <div className="flex gap-4 flex-1 min-h-0">
          <div className="flex-1 min-w-0 card rounded-xl p-4 overflow-y-auto">
            <AssemblyLine stations={data.stations} />
          </div>
          <div className="w-80 flex-shrink-0 card rounded-xl p-4 overflow-y-auto">
            <AgentPanel agents={data.agents} onPageChange={onPageChange} />
          </div>
        </div>

        {/* Agent activity log — full width at bottom */}
        <div className="card rounded-xl p-4">
          <AgentActivityLog
            entries={data.activity_log}
            onEntryClick={setSelectedEntry}
          />
        </div>
      </div>

      {/* Anomaly detail modal */}
      {selectedEntry && (
        <AnomalyDetailModal
          entry={selectedEntry}
          stations={data.stations}
          apiKey={apiKey}
          onClose={() => setSelectedEntry(null)}
        />
      )}
    </>
  )
}
