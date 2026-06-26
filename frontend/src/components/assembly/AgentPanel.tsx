import { Network } from 'lucide-react'
import AgentCard from './AgentCard'
import type { Agent } from '../../types/assembly'
import type { Page } from '../Header'

interface Props {
  agents: Record<string, Agent>
  onPageChange: (p: Page) => void
}

const ORDER = ['supervisor', 'cycle_time', 'equipment', 'quality', 'scheduling', 'maintenance']

export default function AgentPanel({ agents, onPageChange }: Props) {
  const activeCount = Object.values(agents).filter(a => a.status !== 'idle').length

  return (
    <div className="flex flex-col gap-3 h-full">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Network size={14} className="text-blue-400" />
          <span className="text-xs font-semibold text-white">Agent Orchestration</span>
        </div>
        <span className="text-[10px] text-gray-500">
          <span className="text-blue-400 font-bold">{activeCount}</span> / {ORDER.length} active
        </span>
      </div>

      {/* Supervisor is visually prominent */}
      {agents.supervisor && (
        <div className="border border-blue-500/30 rounded-xl p-1 bg-blue-500/5">
          <div className="text-[9px] text-blue-400/60 font-mono uppercase tracking-widest px-1 mb-1">
            Orchestrator
          </div>
          <AgentCard agent={agents.supervisor} onPageChange={onPageChange} />
        </div>
      )}

      {/* Specialist agents */}
      <div className="text-[9px] text-gray-600 font-mono uppercase tracking-widest">Specialist Agents</div>
      <div className="flex flex-col gap-2 flex-1 overflow-y-auto">
        {ORDER.filter(k => k !== 'supervisor').map(k =>
          agents[k] ? <AgentCard key={k} agent={agents[k]} onPageChange={onPageChange} /> : null
        )}
      </div>
    </div>
  )
}
