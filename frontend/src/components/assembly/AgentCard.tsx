import { Cpu, Timer, Wrench, Eye, CalendarDays, ClipboardList, ExternalLink } from 'lucide-react'
import type { Agent } from '../../types/assembly'
import type { Page } from '../Header'

interface Props {
  agent: Agent
  onPageChange: (p: Page) => void
}

const ICONS: Record<string, React.ElementType> = {
  cpu: Cpu, timer: Timer, wrench: Wrench, eye: Eye, calendar: CalendarDays, clipboard: ClipboardList,
}

const STATUS_CONFIG: Record<string, { label: string; color: string; pulse: string }> = {
  idle:         { label: 'IDLE',          color: 'text-gray-500',   pulse: '' },
  observing:    { label: 'OBSERVING',     color: 'text-blue-400',   pulse: 'animate-pulse' },
  orchestrating:{ label: 'ORCHESTRATING', color: 'text-blue-300',   pulse: 'animate-pulse' },
  detecting:    { label: 'DETECTING',     color: 'text-amber-400',  pulse: 'animate-ping' },
  analyzing:    { label: 'ANALYZING',     color: 'text-purple-400', pulse: 'animate-pulse' },
  acting:       { label: 'ACTING',        color: 'text-green-400',  pulse: 'animate-pulse' },
}

const BORDER_COLOR: Record<string, string> = {
  blue:   'border-blue-500/30',
  purple: 'border-purple-500/30',
  amber:  'border-amber-500/30',
  teal:   'border-teal-500/30',
  indigo: 'border-indigo-500/30',
  orange: 'border-orange-500/30',
}

const BG_ACTIVE: Record<string, string> = {
  blue:   'bg-blue-500/10',
  purple: 'bg-purple-500/10',
  amber:  'bg-amber-500/10',
  teal:   'bg-teal-500/10',
  indigo: 'bg-indigo-500/10',
  orange: 'bg-orange-500/10',
}

const ICON_COLOR: Record<string, string> = {
  blue:   'text-blue-400',
  purple: 'text-purple-400',
  amber:  'text-amber-400',
  teal:   'text-teal-400',
  indigo: 'text-indigo-400',
  orange: 'text-orange-400',
}

// Which agent id navigates to which page
const AGENT_NAV: Record<string, Page> = {
  cycle_time: 'cycle_time',
  equipment:  'maintenance',
  quality:    'vision',
}

export default function AgentCard({ agent, onPageChange }: Props) {
  const Icon = ICONS[agent.icon] ?? Cpu
  const sc = STATUS_CONFIG[agent.status] ?? STATUS_CONFIG.idle
  const borderClass = BORDER_COLOR[agent.color] ?? 'border-gray-600/30'
  const bgClass = agent.active ? (BG_ACTIVE[agent.color] ?? '') : ''
  const iconClass = ICON_COLOR[agent.color] ?? 'text-gray-400'
  const isActive = agent.status !== 'idle'
  const targetPage = AGENT_NAV[agent.id]

  return (
    <div
      onClick={targetPage ? () => onPageChange(targetPage) : undefined}
      className={`rounded-lg border p-3 transition-all duration-500 ${borderClass} ${bgClass}
        ${isActive ? 'shadow-sm' : 'opacity-70'}
        ${targetPage ? 'cursor-pointer hover:border-white/20 hover:bg-white/5 group' : ''}`}
    >
      <div className="flex items-center gap-2 mb-1.5">
        <Icon size={14} className={iconClass} />
        <span className="text-xs font-semibold text-white flex-1 truncate">{agent.name}</span>
        <div className="flex items-center gap-1.5">
          {targetPage && (
            <ExternalLink size={9} className="text-gray-600 group-hover:text-gray-400 transition-colors" />
          )}
          <div className={`w-1.5 h-1.5 rounded-full ${sc.color.replace('text-', 'bg-')} ${sc.pulse}`} />
          <span className={`text-[9px] font-bold tracking-wider ${sc.color}`}>{sc.label}</span>
        </div>
      </div>

      {agent.station && (
        <span className="inline-block text-[9px] font-mono bg-white/5 border border-white/10 rounded px-1.5 py-0.5 text-gray-400 mb-1.5">
          {agent.station}
        </span>
      )}

      <p className="text-[10px] text-gray-400 leading-relaxed line-clamp-2">{agent.current_action}</p>

      {targetPage && (
        <p className="text-[9px] text-gray-600 group-hover:text-gray-400 mt-1.5 transition-colors">
          Click to open {targetPage === 'cycle_time' ? 'Cycle Time AI' : targetPage === 'maintenance' ? 'Predictive Maint.' : 'Vision Inspection'} →
        </p>
      )}
    </div>
  )
}
