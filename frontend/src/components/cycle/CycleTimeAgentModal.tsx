import { useEffect, useRef, useState } from 'react'
import { X, Database, CheckCircle2, AlertTriangle, Timer, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import type { Station } from '../../types/assembly'

interface Props {
  bottleneck: Station
  apiKey: string
  onClose: () => void
}

interface TimelineEvent {
  id: number
  type: 'thinking' | 'tool_call' | 'tool_result' | 'done'
  tool?: string
  input?: Record<string, unknown>
  result?: Record<string, unknown>
  text?: string
}

const WRITE_TOOLS = new Set([
  'trigger_maintenance_investigation', 'redirect_jobs_to_parallel_station',
  'rebalance_operator_assignments', 'trigger_tool_change',
  'request_feed_rate_optimization', 'authorize_overtime',
  'resequence_production_jobs', 'update_standard_cycle_time',
  'set_cycle_time_monitoring', 'update_cycle_time_knowledge_graph', 'notify_human',
])

const TOOL_CATEGORY: Record<string, string> = {
  get_realtime_cycle_times: 'Perception', get_cycle_time_trend: 'Perception',
  get_oee_breakdown: 'Perception', get_downtime_log: 'Perception',
  get_machine_parameters: 'Perception', get_program_execution_log: 'Perception',
  get_operator_activity_log: 'Perception', get_in_cycle_inspection_time: 'Perception',
  get_thermal_state: 'Perception',
  get_line_balance_status: 'Bottleneck', get_bottleneck_station: 'Bottleneck',
  get_buffer_inventory: 'Bottleneck', get_parallel_station_status: 'Bottleneck',
  get_shift_production_target: 'Production', get_daily_production_forecast: 'Production',
  get_customer_order_at_risk: 'Production', get_cumulative_time_loss: 'Production',
  get_tooling_condition: 'Root Cause', get_material_lot_hardness: 'Root Cause',
  get_maintenance_history: 'Root Cause', get_feed_override_log: 'Root Cause',
  get_program_version: 'Root Cause', get_fixture_setup_log: 'Root Cause',
  get_operator_skill_profile: 'Root Cause', query_cycle_time_knowledge_graph: 'Root Cause',
  get_sister_machine_cycle_times: 'Root Cause',
  trigger_maintenance_investigation: 'Action', redirect_jobs_to_parallel_station: 'Action',
  rebalance_operator_assignments: 'Action', trigger_tool_change: 'Action',
  request_feed_rate_optimization: 'Action', authorize_overtime: 'Action',
  resequence_production_jobs: 'Action', update_standard_cycle_time: 'Action',
  set_cycle_time_monitoring: 'Action', update_cycle_time_knowledge_graph: 'Action',
  notify_human: 'Action',
}

const CATEGORY_COLOR: Record<string, string> = {
  Perception:  'text-blue-400 border-blue-500/40 bg-blue-500/8',
  Bottleneck:  'text-purple-400 border-purple-500/40 bg-purple-500/8',
  Production:  'text-red-400 border-red-500/40 bg-red-500/8',
  'Root Cause':'text-amber-400 border-amber-500/40 bg-amber-500/8',
  Action:      'text-orange-400 border-orange-500/40 bg-orange-500/8',
}

function toolLabel(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

export default function CycleTimeAgentModal({ bottleneck, apiKey, onClose }: Props) {
  const [events, setEvents]   = useState<TimelineEvent[]>([])
  const [done, setDone]       = useState(false)
  const [error, setError]     = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const idRef    = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  const deviationPct = bottleneck
    ? ((bottleneck.actual_ct / bottleneck.target_ct - 1) * 100).toFixed(1)
    : '0.0'

  useEffect(() => {
    const ctrl = new AbortController()

    async function startAgent() {
      try {
        const res = await fetch(
          '/api/cycle-time-agent',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_key:   apiKey,
              machine:   'MILL-04',
              operation: 'Op60',
              station:   bottleneck?.code ?? 'STN-06',
              actual_ct: bottleneck?.actual_ct ?? 847,
              target_ct: bottleneck?.target_ct ?? 720,
            }),
            signal: ctrl.signal,
          }
        )

        const reader = res.body!.getReader()
        const dec    = new TextDecoder()
        let buf      = ''

        while (true) {
          const { value, done: streamDone } = await reader.read()
          if (streamDone) break
          buf += dec.decode(value, { stream: true })
          const lines = buf.split('\n')
          buf = lines.pop() ?? ''
          for (const line of lines) {
            if (!line.startsWith('data: ')) continue
            try {
              const obj = JSON.parse(line.slice(6))
              const id  = ++idRef.current
              if (obj.type === 'done') {
                setDone(true)
              } else {
                setEvents(prev => [...prev, { id, ...obj }])
              }
            } catch { /* incomplete */ }
          }
        }
      } catch (e: unknown) {
        if ((e as Error).name !== 'AbortError') setError(String(e))
      }
    }

    startAgent()
    return () => ctrl.abort()
  }, [bottleneck, apiKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const writeActions   = events.filter(e => e.type === 'tool_call' && WRITE_TOOLS.has(e.tool ?? ''))
  const hasDeliveryRisk = writeActions.some(e => e.tool === 'notify_human')

  function toggleExpand(id: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl border border-orange-500/25 bg-[#0c1117] shadow-2xl">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/8">
          <div className="w-7 h-7 rounded-lg bg-orange-500/15 border border-orange-500/30 flex items-center justify-center flex-shrink-0">
            <Timer size={14} className="text-orange-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-bold text-white">Cycle Time Intelligence Agent</p>
              {!done && <Loader2 size={11} className="text-orange-400 animate-spin" />}
              {done  && <span className="text-[9px] font-bold text-orange-400 border border-orange-500/30 rounded px-1.5 py-0.5">COMPLETE</span>}
            </div>
            <p className="text-[10px] text-gray-500 truncate">
              MILL-04 · Op60 Crankshaft Bore · {deviationPct}% over target · 8-step reasoning
            </p>
          </div>
          {hasDeliveryRisk && (
            <div className="flex items-center gap-1 text-[9px] font-bold text-red-400 border border-red-500/40 bg-red-500/10 rounded px-2 py-1">
              <AlertTriangle size={9} />
              CUSTOMER DELIVERY RISK — Supervisor Notified
            </div>
          )}
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors ml-1">
            <X size={16} />
          </button>
        </div>

        {/* Deviation context strip */}
        <div className="flex items-center gap-4 px-5 py-2.5 border-b border-white/5 bg-orange-500/5">
          <div className="flex items-center gap-1.5 text-[10px] text-orange-400">
            <AlertTriangle size={10} />
            <span className="font-bold">BOTTLENECK</span>
          </div>
          <span className="text-[10px] font-mono text-gray-400">MILL-04 · Op60</span>
          <span className="text-[10px] font-semibold text-white">Crankshaft Bore Machining</span>
          <span className="text-[10px] text-gray-500 flex-1">
            {bottleneck?.actual_ct ?? 847}s actual vs {bottleneck?.target_ct ?? 720}s standard
          </span>
          <span className="text-[10px] text-orange-400 font-bold">+{deviationPct}%</span>
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-[11px] text-red-300">{error}</div>
          )}

          {events.map(ev => {
            if (ev.type === 'thinking') {
              return (
                <div key={ev.id} className="text-[11px] text-gray-300 leading-relaxed border-l-2 border-orange-500/30 pl-3 py-1">
                  {ev.text}
                </div>
              )
            }

            if (ev.type === 'tool_call') {
              const isWrite = WRITE_TOOLS.has(ev.tool ?? '')
              const cat     = TOOL_CATEGORY[ev.tool ?? ''] ?? 'Other'
              const catCls  = CATEGORY_COLOR[cat] ?? 'text-gray-400 border-gray-500/30 bg-gray-500/8'

              return (
                <div key={ev.id} className={`rounded-lg border px-3 py-2 flex items-center gap-2.5 ${
                  isWrite ? 'border-orange-500/25 bg-orange-500/5' : 'border-orange-500/12 bg-orange-500/3'
                }`}>
                  {isWrite
                    ? <CheckCircle2 size={11} className="text-orange-400 flex-shrink-0" />
                    : <Database size={11} className="text-orange-400/60 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-[9px] font-bold uppercase tracking-wider border rounded px-1.5 py-0.5 ${catCls}`}>
                        {cat}
                      </span>
                      <span className={`text-[10px] font-semibold ${isWrite ? 'text-orange-300' : 'text-orange-200/70'}`}>
                        {toolLabel(ev.tool ?? '')}
                      </span>
                    </div>
                    {ev.input && Object.keys(ev.input).length > 0 && (
                      <p className="text-[9px] text-gray-600 mt-0.5 truncate">
                        {Object.entries(ev.input).map(([k, v]) => `${k}: ${JSON.stringify(v)}`).join(' · ')}
                      </p>
                    )}
                  </div>
                </div>
              )
            }

            if (ev.type === 'tool_result') {
              const isOpen  = expanded.has(ev.id)
              const result  = ev.result ?? {}
              const preview = result.summary ?? result.confirmation ?? result.note ??
                              result.current_bottleneck ?? result.shortfall_confirmed_by ?? ''

              return (
                <div key={ev.id} className="ml-4 rounded-lg border border-white/5 bg-white/2 px-3 py-1.5">
                  {preview && (
                    <p className="text-[10px] text-gray-400 leading-relaxed">{String(preview)}</p>
                  )}
                  <button
                    onClick={() => toggleExpand(ev.id)}
                    className="flex items-center gap-1 text-[9px] text-gray-600 hover:text-gray-400 mt-1 transition-colors"
                  >
                    {isOpen ? <ChevronUp size={9} /> : <ChevronDown size={9} />}
                    {isOpen ? 'hide' : 'show'} raw data
                  </button>
                  {isOpen && (
                    <pre className="mt-1.5 text-[9px] text-gray-500 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-40 overflow-y-auto">
                      {JSON.stringify(result, null, 2)}
                    </pre>
                  )}
                </div>
              )
            }

            return null
          })}

          {/* Done summary */}
          {done && (
            <div className="rounded-xl border border-orange-500/25 bg-orange-500/5 p-4 mt-2">
              <p className="text-xs font-bold text-orange-400 mb-2">
                Investigation Complete — {writeActions.length} action{writeActions.length !== 1 ? 's' : ''} taken
              </p>
              <div className="flex flex-col gap-1">
                {writeActions.map(a => (
                  <div key={a.id} className="flex items-center gap-2 text-[10px] text-gray-300">
                    <CheckCircle2 size={10} className={a.tool === 'notify_human' ? 'text-red-400' : 'text-orange-400'} />
                    <span>{toolLabel(a.tool ?? '')}</span>
                    {a.tool === 'notify_human' && (
                      <span className="text-[9px] text-red-400 font-bold">— SUPERVISOR NOTIFIED</span>
                    )}
                    {a.tool === 'redirect_jobs_to_parallel_station' && (
                      <span className="text-[9px] text-green-400 font-bold">— CUSTOMER ORDERS PROTECTED</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!done && !error && events.length === 0 && (
            <div className="flex items-center gap-2 text-[11px] text-gray-500">
              <Loader2 size={12} className="animate-spin" />
              Starting cycle time investigation…
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
