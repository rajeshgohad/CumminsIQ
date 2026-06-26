import { useRef, useEffect } from 'react'
import { ArrowRight, AlertTriangle, CheckCircle, Eye, Zap, ArrowUpRight, Radio } from 'lucide-react'
import type { ActivityLogEntry, LogType, LogSeverity } from '../../types/assembly'

interface Props { entries: ActivityLogEntry[]; onEntryClick: (e: ActivityLogEntry) => void }

const AGENT_LABELS: Record<string, string> = {
  supervisor: 'Supervisor',
  cycle_time: 'Cycle Time',
  equipment:  'Equipment',
  quality:    'Quality AI',
  scheduling: 'Scheduling',
  maintenance:'Maintenance',
}

const AGENT_COLORS: Record<string, string> = {
  supervisor: 'text-blue-400 bg-blue-500/15 border-blue-500/30',
  cycle_time: 'text-purple-400 bg-purple-500/15 border-purple-500/30',
  equipment:  'text-amber-400 bg-amber-500/15 border-amber-500/30',
  quality:    'text-teal-400 bg-teal-500/15 border-teal-500/30',
  scheduling: 'text-indigo-400 bg-indigo-500/15 border-indigo-500/30',
  maintenance:'text-orange-400 bg-orange-500/15 border-orange-500/30',
}

const TYPE_ICON: Record<LogType, React.ElementType> = {
  observe:  Eye,
  detect:   AlertTriangle,
  dispatch: ArrowRight,
  analyze:  Zap,
  act:      CheckCircle,
  escalate: ArrowUpRight,
  alert:    Radio,
}

const SEV_DOT: Record<LogSeverity, string> = {
  info:     'bg-blue-400',
  warning:  'bg-amber-400',
  critical: 'bg-red-400 animate-pulse',
  success:  'bg-green-400',
}

const TYPE_COLOR: Record<LogType, string> = {
  observe:  'text-blue-400',
  detect:   'text-amber-400',
  dispatch: 'text-blue-300',
  analyze:  'text-purple-400',
  act:      'text-green-400',
  escalate: 'text-orange-400',
  alert:    'text-red-400',
}

function timeAgo(ts: number): string {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${diff}s ago`
  return `${Math.floor(diff / 60)}m ago`
}

function AgentTag({ id }: { id: string }) {
  return (
    <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-semibold border ${AGENT_COLORS[id] ?? 'text-gray-400 bg-gray-500/10 border-gray-500/20'}`}>
      {AGENT_LABELS[id] ?? id}
    </span>
  )
}

export default function AgentActivityLog({ entries, onEntryClick }: Props) {
  const scrollRef = useRef<HTMLDivElement>(null)

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Radio size={13} className="text-green-400 animate-pulse" />
          <span className="text-xs font-semibold text-white">Agent Communication Log</span>
        </div>
        <span className="text-[10px] text-gray-500">{entries.length} events</span>
      </div>

      <div ref={scrollRef} className="flex flex-col gap-1 max-h-52 overflow-y-auto pr-1 scrollbar-thin">
        {entries.map(e => {
          const Icon = TYPE_ICON[e.type] ?? Eye
          const iconColor = TYPE_COLOR[e.type] ?? 'text-gray-400'

          return (
            <div key={e.id} onClick={() => onEntryClick(e)} className="flex items-start gap-2 px-2 py-1.5 rounded-lg bg-white/3 hover:bg-white/6 transition-colors cursor-pointer group">
              {/* Severity dot */}
              <div className="flex-shrink-0 mt-1.5">
                <div className={`w-1.5 h-1.5 rounded-full ${SEV_DOT[e.severity]}`} />
              </div>

              {/* Icon */}
              <Icon size={11} className={`flex-shrink-0 mt-1 ${iconColor}`} />

              {/* Content */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1.5 flex-wrap mb-0.5">
                  <AgentTag id={e.from_agent} />
                  {e.to_agent && (
                    <>
                      <ArrowRight size={8} className="text-gray-600" />
                      <AgentTag id={e.to_agent} />
                    </>
                  )}
                  {e.station && (
                    <span className="text-[9px] font-mono text-gray-600 bg-white/5 px-1 rounded">
                      {e.station}
                    </span>
                  )}
                </div>
                <p className="text-[10px] text-gray-300 leading-relaxed">{e.message}</p>
              </div>

              {/* Time + click hint */}
              <div className="flex flex-col items-end gap-1 flex-shrink-0">
                <span className="text-[9px] text-gray-600 mt-1">{timeAgo(e.timestamp)}</span>
                <span className="text-[8px] text-gray-700 group-hover:text-gray-500 transition-colors">details →</span>
              </div>
            </div>
          )
        })}

        {entries.length === 0 && (
          <div className="text-[10px] text-gray-600 text-center py-4">
            No agent activity yet — waiting for anomalies…
          </div>
        )}
      </div>
    </div>
  )
}
