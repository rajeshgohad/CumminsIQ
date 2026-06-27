import { useEffect, useRef, useState } from 'react'
import { X, Database, CheckCircle2, AlertTriangle, ShieldAlert, Loader2, ChevronDown, ChevronUp } from 'lucide-react'
import type { LogEntry } from './DefectLog'

interface Props {
  defect: LogEntry
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
  'quarantine_serial_numbers', 'place_operation_hold', 'create_ncr', 'create_capa',
  'trigger_100pct_inspection', 'disposition_parts', 'release_hold',
  'notify_supplier', 'notify_customer', 'update_control_plan',
  'set_enhanced_monitoring', 'notify_human',
])

const TOOL_CATEGORY: Record<string, string> = {
  get_inspection_result: 'Perception', get_spc_chart: 'Perception',
  get_test_results: 'Perception', get_visual_inspection_log: 'Perception',
  get_gauge_calibration_status: 'Perception',
  get_serial_number_history: 'Traceability', get_material_lot_traceability: 'Traceability',
  get_affected_population: 'Traceability', get_engine_location: 'Traceability',
  get_shipment_records: 'Traceability',
  get_process_parameters: 'Root Cause', get_tooling_history: 'Root Cause',
  get_material_cert: 'Root Cause', get_operator_log: 'Root Cause',
  get_maintenance_history: 'Root Cause', get_engineering_drawing: 'Root Cause',
  query_failure_knowledge_graph: 'Root Cause', get_similar_components: 'Root Cause',
  quarantine_serial_numbers: 'Action', place_operation_hold: 'Action',
  create_ncr: 'Action', create_capa: 'Action', trigger_100pct_inspection: 'Action',
  disposition_parts: 'Action', release_hold: 'Action', notify_supplier: 'Action',
  notify_customer: 'Action', update_control_plan: 'Action',
  set_enhanced_monitoring: 'Action', notify_human: 'Action',
}

const CATEGORY_COLOR: Record<string, string> = {
  Perception: 'text-blue-400 border-blue-500/40 bg-blue-500/8',
  Traceability: 'text-purple-400 border-purple-500/40 bg-purple-500/8',
  'Root Cause': 'text-amber-400 border-amber-500/40 bg-amber-500/8',
  Action: 'text-red-400 border-red-500/40 bg-red-500/8',
}

function toolLabel(name: string) {
  return name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

function stationCode(station: string) {
  const m = station.match(/STN-\d+/)
  return m ? m[0] : station.split(' ')[0]
}

export default function QualityAgentModal({ defect, apiKey, onClose }: Props) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [done, setDone]     = useState(false)
  const [error, setError]   = useState('')
  const [expanded, setExpanded] = useState<Set<number>>(new Set())
  const idRef = useRef(0)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const ctrl = new AbortController()

    async function startAgent() {
      const code = stationCode(defect.station)
      try {
        const res = await fetch(
          '/api/quality-agent',
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              api_key: apiKey,
              station: code,
              defect_type: defect.check,
              detail: defect.detail,
              confidence: defect.confidence,
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
            } catch { /* incomplete frame */ }
          }
        }
      } catch (e: unknown) {
        if ((e as Error).name !== 'AbortError') setError(String(e))
      }
    }

    startAgent()
    return () => ctrl.abort()
  }, [defect, apiKey])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const writeActions = events.filter(e => e.type === 'tool_call' && WRITE_TOOLS.has(e.tool ?? ''))
  const hasFieldEscape = writeActions.some(e => e.tool === 'notify_customer')

  function toggleExpand(id: number) {
    setExpanded(prev => {
      const next = new Set(prev)
      next.has(id) ? next.delete(id) : next.add(id)
      return next
    })
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="relative w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl border border-teal-500/25 bg-[#0c1117] shadow-2xl">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/8">
          <div className="w-7 h-7 rounded-lg bg-teal-500/15 border border-teal-500/30 flex items-center justify-center flex-shrink-0">
            <ShieldAlert size={14} className="text-teal-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <p className="text-sm font-bold text-white">Quality Intelligence Agent</p>
              {!done && <Loader2 size={11} className="text-teal-400 animate-spin" />}
              {done  && <span className="text-[9px] font-bold text-teal-400 border border-teal-500/30 rounded px-1.5 py-0.5">COMPLETE</span>}
            </div>
            <p className="text-[10px] text-gray-500 truncate">{defect.station} · {defect.check} · {defect.confidence}% confidence</p>
          </div>
          {hasFieldEscape && (
            <div className="flex items-center gap-1 text-[9px] font-bold text-amber-400 border border-amber-500/40 bg-amber-500/10 rounded px-2 py-1">
              <AlertTriangle size={9} />
              FIELD ESCAPE — Pending Human Approval
            </div>
          )}
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors ml-1">
            <X size={16} />
          </button>
        </div>

        {/* Defect context strip */}
        <div className="flex items-center gap-4 px-5 py-2.5 border-b border-white/5 bg-red-500/5">
          <div className="flex items-center gap-1.5 text-[10px] text-red-400">
            <AlertTriangle size={10} />
            <span className="font-bold">FAIL</span>
          </div>
          <span className="text-[10px] font-mono text-gray-400">{defect.station}</span>
          <span className="text-[10px] font-semibold text-white">{defect.check}</span>
          <span className="text-[10px] text-gray-500 flex-1 truncate">{defect.detail}</span>
          <span className="text-[10px] text-red-400 font-bold">{defect.confidence}%</span>
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-2">
          {error && (
            <div className="rounded-lg border border-red-500/30 bg-red-500/10 p-3 text-[11px] text-red-300">{error}</div>
          )}

          {events.map(ev => {
            if (ev.type === 'thinking') {
              return (
                <div key={ev.id} className="text-[11px] text-gray-300 leading-relaxed border-l-2 border-teal-500/30 pl-3 py-1">
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
                  isWrite ? 'border-red-500/25 bg-red-500/5' : 'border-teal-500/15 bg-teal-500/4'
                }`}>
                  {isWrite
                    ? <CheckCircle2 size={11} className="text-red-400 flex-shrink-0" />
                    : <Database size={11} className="text-teal-400 flex-shrink-0" />}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className={`text-[9px] font-bold uppercase tracking-wider border rounded px-1.5 py-0.5 ${catCls}`}>
                        {cat}
                      </span>
                      <span className={`text-[10px] font-semibold ${isWrite ? 'text-red-300' : 'text-teal-300'}`}>
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
              const isOpen = expanded.has(ev.id)
              const result = ev.result ?? {}
              const preview = result.summary ?? result.confirmation ?? result.assessment ?? result.warning ?? ''

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
            <div className="rounded-xl border border-teal-500/25 bg-teal-500/5 p-4 mt-2">
              <p className="text-xs font-bold text-teal-400 mb-2">Investigation Complete — {writeActions.length} action{writeActions.length !== 1 ? 's' : ''} taken</p>
              <div className="flex flex-col gap-1">
                {writeActions.map(a => (
                  <div key={a.id} className="flex items-center gap-2 text-[10px] text-gray-300">
                    <CheckCircle2 size={10} className={a.tool === 'notify_customer' ? 'text-amber-400' : 'text-teal-400'} />
                    <span>{toolLabel(a.tool ?? '')}</span>
                    {a.tool === 'notify_customer' && (
                      <span className="text-[9px] text-amber-400 font-bold">— PENDING HUMAN APPROVAL</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {!done && !error && events.length === 0 && (
            <div className="flex items-center gap-2 text-[11px] text-gray-500">
              <Loader2 size={12} className="animate-spin" />
              Starting quality investigation…
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  )
}
