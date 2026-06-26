import { Brain, ArrowRight, Zap } from 'lucide-react'
import type { Agent, ActivityLogEntry } from '../../types/assembly'

interface Props {
  agents: Record<string, Agent>
  log: ActivityLogEntry[]
}

const STATUS_STYLE: Record<string, string> = {
  idle:          'text-gray-500',
  observing:     'text-blue-400',
  orchestrating: 'text-blue-300',
  detecting:     'text-amber-400',
  analyzing:     'text-purple-400',
  acting:        'text-green-400',
}

const RELEVANT_AGENTS = ['cycle_time', 'scheduling', 'supervisor']

function timeAgo(ts: number) {
  const diff = Math.floor(Date.now() / 1000) - ts
  if (diff < 60) return `${diff}s`
  return `${Math.floor(diff / 60)}m`
}

export default function AgentReasoning({ agents, log }: Props) {
  const relevant = log.filter(e =>
    RELEVANT_AGENTS.includes(e.from_agent) || RELEVANT_AGENTS.includes(e.to_agent ?? '')
  ).slice(0, 12)

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center gap-2">
        <Brain size={14} className="text-purple-400" />
        <span className="text-xs font-semibold text-white">AI Agent Reasoning</span>
      </div>

      {/* Active agent status cards */}
      <div className="flex flex-col gap-2">
        {RELEVANT_AGENTS.map(id => {
          const agent = agents[id]
          if (!agent) return null
          const sc = STATUS_STYLE[agent.status] ?? 'text-gray-500'
          return (
            <div key={id} className="rounded-lg bg-white/3 border border-white/6 p-2.5">
              <div className="flex items-center gap-2 mb-1">
                <Zap size={10} className={sc} />
                <span className="text-[10px] font-semibold text-gray-300">{agent.name}</span>
                <span className={`ml-auto text-[9px] font-bold uppercase tracking-wider ${sc}`}>
                  {agent.status}
                </span>
              </div>
              {agent.station && (
                <span className="inline-block text-[9px] font-mono text-gray-500 bg-white/5 px-1.5 py-0.5 rounded mb-1">
                  {agent.station}
                </span>
              )}
              <p className="text-[10px] text-gray-400 leading-relaxed line-clamp-2">{agent.current_action}</p>
            </div>
          )
        })}
      </div>

      {/* Recent reasoning log */}
      <div className="text-[9px] text-gray-600 font-mono uppercase tracking-widest">Recent Events</div>
      <div className="flex flex-col gap-1 flex-1 overflow-y-auto">
        {relevant.map(e => (
          <div key={e.id} className="flex items-start gap-2 py-1 border-b border-white/4">
            <span className={`flex-shrink-0 text-[9px] font-mono mt-0.5 ${
              e.severity === 'critical' ? 'text-red-400' :
              e.severity === 'warning'  ? 'text-amber-400' :
              e.severity === 'success'  ? 'text-green-400' : 'text-blue-400'
            }`}>{timeAgo(e.timestamp)}</span>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-1 mb-0.5">
                <span className="text-[9px] font-semibold text-gray-400">{e.from_agent.replace('_', ' ')}</span>
                {e.to_agent && (
                  <>
                    <ArrowRight size={7} className="text-gray-600" />
                    <span className="text-[9px] text-gray-500">{e.to_agent.replace('_', ' ')}</span>
                  </>
                )}
              </div>
              <p className="text-[10px] text-gray-300 leading-snug line-clamp-2">{e.message}</p>
            </div>
          </div>
        ))}
        {relevant.length === 0 && (
          <p className="text-[10px] text-gray-600 py-2">Monitoring — no cycle time events yet</p>
        )}
      </div>
    </div>
  )
}
