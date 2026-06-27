import { useEffect, useRef, useState } from 'react'
import { X, Brain, Wrench, CheckCircle2, ChevronDown, ChevronRight, Loader2, Database } from 'lucide-react'
import { API_BASE } from '../../lib/api'
import type { Station } from '../../types/assembly'

interface Props {
  station: Station
  apiKey: string
  onClose: () => void
}

type EventType = 'thinking' | 'tool_call' | 'tool_result' | 'done' | 'error'

interface AgentEvent {
  type:   EventType
  text?:  string
  tool?:  string
  input?: Record<string, unknown>
  result?: Record<string, unknown>
}

const TOOL_LABELS: Record<string, string> = {
  get_sensor_data:              'Reading sensor historian',
  get_fault_prognosis:          'Running ML prognosis model',
  get_production_schedule:      'Checking MES production schedule',
  check_parts_inventory:        'Checking CMMS parts inventory',
  get_supplier_lead_time:       'Querying supplier lead times',
  get_technician_availability:  'Checking technician availability',
  create_work_order:            'Creating work order in CMMS',
  schedule_technician:          'Booking technician',
  create_purchase_order:        'Creating purchase order',
  set_monitoring_checkpoint:    'Setting monitoring checkpoint',
  notify_human:                 'Sending notification',
}

const TOOL_COLORS: Record<string, string> = {
  get_sensor_data:              'border-blue-500/30 bg-blue-500/6',
  get_fault_prognosis:          'border-purple-500/30 bg-purple-500/6',
  get_production_schedule:      'border-indigo-500/30 bg-indigo-500/6',
  check_parts_inventory:        'border-amber-500/30 bg-amber-500/6',
  get_supplier_lead_time:       'border-amber-500/30 bg-amber-500/6',
  get_technician_availability:  'border-teal-500/30 bg-teal-500/6',
  create_work_order:            'border-orange-500/30 bg-orange-500/6',
  schedule_technician:          'border-orange-500/30 bg-orange-500/6',
  create_purchase_order:        'border-red-500/30 bg-red-500/6',
  set_monitoring_checkpoint:    'border-green-500/30 bg-green-500/6',
  notify_human:                 'border-pink-500/30 bg-pink-500/6',
}

function faultType(s: Station): string {
  if (s.machine_temp > 86)   return 'bearing_overtemp'
  if (s.vibration > 0.70)    return 'vibration_anomaly'
  if (s.tool_life_pct < 25)  return 'tool_wear'
  return 'general_degradation'
}

function ToolResultRow({ label, value }: { label: string; value: unknown }) {
  const v = typeof value === 'object' ? JSON.stringify(value) : String(value)
  return (
    <div className="flex gap-2 text-[10px]">
      <span className="text-gray-500 flex-shrink-0 w-32">{label}</span>
      <span className="text-gray-200 font-mono break-all">{v}</span>
    </div>
  )
}

function ToolResultBlock({ tool, result }: { tool: string; result: Record<string, unknown> }) {
  const [open, setOpen] = useState(false)
  const isWrite = ['create_work_order','schedule_technician','create_purchase_order',
                   'set_monitoring_checkpoint','notify_human'].includes(tool)

  return (
    <div className="rounded-lg border border-white/8 bg-white/3 overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left hover:bg-white/4 transition-colors"
      >
        {isWrite
          ? <CheckCircle2 size={11} className="text-green-400 flex-shrink-0" />
          : <Database size={11} className="text-teal-400 flex-shrink-0" />
        }
        <span className="text-[10px] font-semibold text-gray-300 flex-1">
          {isWrite ? 'Action completed' : 'Data returned'}
        </span>
        {open ? <ChevronDown size={10} className="text-gray-600" /> : <ChevronRight size={10} className="text-gray-600" />}
      </button>
      {open && (
        <div className="px-3 pb-3 flex flex-col gap-1 border-t border-white/6 pt-2">
          {Object.entries(result).map(([k, v]) => (
            <ToolResultRow key={k} label={k} value={v} />
          ))}
        </div>
      )}
    </div>
  )
}

export default function PMAgentModal({ station, apiKey, onClose }: Props) {
  const [events, setEvents] = useState<AgentEvent[]>([])
  const [running, setRunning] = useState(false)
  const [done, setDone]       = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const fault = faultType(station)

  async function startAgent() {
    setEvents([])
    setDone(false)
    setRunning(true)

    try {
      const res = await fetch(`${API_BASE}/api/pm-agent`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          asset_id:        station.code,
          fault_type:      fault,
          sensor_readings: {
            machine_temp:  station.machine_temp,
            vibration:     station.vibration,
            tool_life_pct: station.tool_life_pct,
          },
          api_key: apiKey,
        }),
      })

      const reader  = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer    = ''

      while (true) {
        const { done: d, value } = await reader.read()
        if (d) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue
          try {
            const ev: AgentEvent = JSON.parse(payload)
            setEvents(prev => [...prev, ev])
            if (ev.type === 'done') setDone(true)
            setTimeout(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), 30)
          } catch { /* skip malformed */ }
        }
      }
    } catch (e) {
      setEvents(prev => [...prev, { type: 'error', text: String(e) }])
    } finally {
      setRunning(false)
    }
  }

  useEffect(() => { startAgent() }, [])

  // Count write actions for summary
  const actions = events.filter(e => e.type === 'tool_result' &&
    ['create_work_order','schedule_technician','create_purchase_order',
     'set_monitoring_checkpoint','notify_human'].includes(e.tool ?? ''))

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4"
      style={{ background: 'rgba(2,5,18,0.90)', backdropFilter: 'blur(8px)' }}
    >
      <div className="w-full max-w-2xl max-h-[90vh] flex flex-col rounded-2xl border border-orange-500/25 bg-[#090e1d] shadow-2xl overflow-hidden">

        {/* Header */}
        <div className="flex items-center gap-3 px-5 py-4 border-b border-white/8 flex-shrink-0">
          <div className="w-8 h-8 rounded-full bg-orange-500/15 border border-orange-500/30 flex items-center justify-center flex-shrink-0">
            <Brain size={15} className="text-orange-400" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-bold text-white">PM Agent</span>
              <span className="text-[9px] font-mono text-orange-400 bg-orange-500/10 border border-orange-500/20 rounded px-2 py-0.5">
                {station.code}
              </span>
              <span className="text-[9px] font-mono text-gray-500 bg-white/5 border border-white/10 rounded px-2 py-0.5">
                {fault.replace(/_/g, ' ')}
              </span>
            </div>
            <p className="text-[10px] text-gray-500 mt-0.5">
              {station.name} · {station.machine} · claude-sonnet-4-6 tool-use loop
            </p>
          </div>
          {running && <Loader2 size={14} className="text-orange-400 animate-spin flex-shrink-0" />}
          {done    && <CheckCircle2 size={14} className="text-green-400 flex-shrink-0" />}
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors flex-shrink-0 ml-1">
            <X size={16} />
          </button>
        </div>

        {/* Timeline */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">
          {events.map((ev, i) => {
            if (ev.type === 'thinking') return (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                  <div className="w-2 h-2 rounded-full bg-white/30 mt-1" />
                  <div className="w-px flex-1 bg-white/6 min-h-[8px]" />
                </div>
                <div className="flex-1 pb-1">
                  <p className="text-[10px] font-semibold text-gray-500 mb-1 uppercase tracking-wider">Agent Reasoning</p>
                  <p className="text-[11px] text-gray-200 leading-relaxed whitespace-pre-wrap">{ev.text}</p>
                </div>
              </div>
            )

            if (ev.type === 'tool_call') {
              const label  = TOOL_LABELS[ev.tool ?? ''] ?? ev.tool
              const colors = TOOL_COLORS[ev.tool ?? ''] ?? 'border-white/10 bg-white/3'
              const isWrite = ['create_work_order','schedule_technician','create_purchase_order',
                               'set_monitoring_checkpoint','notify_human'].includes(ev.tool ?? '')
              return (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div className={`w-2 h-2 rounded-full mt-1 ${isWrite ? 'bg-orange-400' : 'bg-blue-400'}`} />
                    <div className="w-px flex-1 bg-white/6 min-h-[8px]" />
                  </div>
                  <div className={`flex-1 rounded-lg border p-3 pb-2 ${colors}`}>
                    <div className="flex items-center gap-2 mb-2">
                      <Wrench size={10} className={isWrite ? 'text-orange-400' : 'text-blue-400'} />
                      <span className="text-[10px] font-bold text-white">{label}</span>
                      <span className="text-[9px] font-mono text-gray-600 ml-auto">{ev.tool}</span>
                    </div>
                    {ev.input && Object.keys(ev.input).length > 0 && (
                      <div className="flex flex-col gap-0.5">
                        {Object.entries(ev.input).map(([k, v]) => (
                          <div key={k} className="flex gap-2 text-[9px]">
                            <span className="text-gray-500 w-24 flex-shrink-0">{k}</span>
                            <span className="text-gray-300 font-mono">{String(v)}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              )
            }

            if (ev.type === 'tool_result') return (
              <div key={i} className="flex gap-3">
                <div className="flex flex-col items-center gap-1 flex-shrink-0">
                  <div className="w-1.5 h-1.5 rounded-full bg-teal-400/50 mt-1.5" />
                  <div className="w-px flex-1 bg-white/6 min-h-[8px]" />
                </div>
                <div className="flex-1">
                  <ToolResultBlock tool={ev.tool ?? ''} result={ev.result ?? {}} />
                </div>
              </div>
            )

            if (ev.type === 'done') return (
              <div key={i} className="rounded-xl border border-green-500/30 bg-green-500/6 p-4 mt-2">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle2 size={14} className="text-green-400" />
                  <span className="text-[11px] font-bold text-green-300">Agent completed — {actions.length} action{actions.length !== 1 ? 's' : ''} taken</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  {actions.map((a, j) => (
                    <span key={j} className="text-[9px] font-mono bg-green-500/10 border border-green-500/20 text-green-400 rounded px-2 py-0.5">
                      {TOOL_LABELS[a.tool ?? ''] ?? a.tool}
                    </span>
                  ))}
                </div>
              </div>
            )

            if (ev.type === 'error') return (
              <div key={i} className="rounded-lg border border-red-500/30 bg-red-500/6 p-3">
                <p className="text-[10px] text-red-400">{ev.text}</p>
              </div>
            )

            return null
          })}

          {running && events.length === 0 && (
            <div className="flex items-center gap-2 text-[10px] text-orange-400 animate-pulse py-4">
              <Loader2 size={12} className="animate-spin" />
              Connecting to PM agent…
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-white/8 flex-shrink-0 bg-black/20">
          <span className="text-[9px] font-mono text-gray-700">
            {events.filter(e => e.type === 'tool_call').length} tool calls ·{' '}
            {events.filter(e => e.type === 'thinking').length} reasoning blocks
          </span>
          <div className="flex gap-2">
            {done && (
              <button
                onClick={startAgent}
                className="text-[11px] text-orange-300 hover:text-white px-3 py-1.5 rounded-lg border border-orange-500/30 hover:border-orange-400/50 bg-orange-500/8 transition-all"
              >
                Run Again
              </button>
            )}
            <button
              onClick={onClose}
              className="text-[11px] text-gray-400 hover:text-white px-4 py-1.5 rounded-lg border border-white/10 hover:border-white/20 transition-all"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
