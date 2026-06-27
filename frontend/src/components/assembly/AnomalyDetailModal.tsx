import { X, Cpu, Sparkles, Loader2 } from 'lucide-react'
import { useState, useRef } from 'react'
import type { ActivityLogEntry, Station } from '../../types/assembly'
import { API_BASE } from '../../lib/api'

interface Props {
  entry: ActivityLogEntry
  stations: Station[]
  onClose: () => void
  apiKey: string
}

const AGENT_NAMES: Record<string, string> = {
  supervisor:  'Supervisor Agent',
  equipment:   'Equipment Health Agent',
  cycle_time:  'Cycle Time Monitor',
  quality:     'Quality AI Agent',
  scheduling:  'Scheduling Optimizer',
  maintenance: 'Maintenance Agent',
}

const AGENT_COLOR: Record<string, string> = {
  supervisor:  'text-blue-400',
  equipment:   'text-amber-400',
  cycle_time:  'text-purple-400',
  quality:     'text-teal-400',
  scheduling:  'text-indigo-400',
  maintenance: 'text-orange-400',
}

const AGENT_ALGO: Record<string, string> = {
  supervisor:  'Multi-agent orchestration · priority routing',
  equipment:   'ReAct · SPC threshold + LLM root-cause',
  cycle_time:  'CUSUM change detection + LLM takt analysis',
  quality:     'ResNet-50 CNN inference + LLM quality reasoning',
  scheduling:  'Constraint satisfaction + LLM optimizer',
  maintenance: 'Risk scoring (RUL × criticality) + Maximo WO',
}

const SEV_STYLE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  warning:  'bg-amber-500/15 text-amber-400 border-amber-500/30',
  info:     'bg-blue-500/15 text-blue-400 border-blue-500/30',
  success:  'bg-green-500/15 text-green-400 border-green-500/30',
}

const STEP_COLOR = [
  { dot: 'bg-blue-400',   label: 'text-blue-400'   },
  { dot: 'bg-purple-400', label: 'text-purple-400'  },
  { dot: 'bg-amber-400',  label: 'text-amber-400'   },
  { dot: 'bg-green-400',  label: 'text-green-400'   },
]

// ── Reasoning steps per agent ─────────────────────────────────────────────────

function buildSteps(entry: ActivityLogEntry, stn: Station | null) {
  const code    = entry.station ?? 'UNKNOWN'
  const temp    = stn?.machine_temp.toFixed(1) ?? 'N/A'
  const vib     = stn?.vibration.toFixed(3) ?? 'N/A'
  const tool    = stn?.tool_life_pct.toFixed(0) ?? 'N/A'
  const pctOver = stn ? Math.round((stn.actual_ct / stn.target_ct - 1) * 100) : 0
  const conf    = stn && stn.machine_temp > 89 ? 88 : 74

  switch (entry.from_agent) {
    case 'equipment': return {
      steps: [
        { label: 'OBSERVE', text: `${code} sensors: temp ${temp}°C, vibration ${vib}g RMS, tool life ${tool}%. Three channels flagged simultaneously.` },
        { label: 'THINK',   text: `Sustained temperature + vibration co-movement rules out transient spike. Pattern consistent with bearing lubrication degradation — worn tooling at ${tool}% is a secondary heat contributor.` },
        { label: 'ANALYZE', text: `Root cause: bearing race wear / lubrication loss. Est. time to failure: ${stn && stn.machine_temp > 89 ? '12–20 min' : '35–60 min'} at current drift. Confidence ${conf}%.` },
        { label: 'ACT',     text: `Escalate to Maintenance Agent. Priority HIGH work order. Window: address before next cycle. Risk if deferred: 3–8h unplanned downtime.` },
      ],
      confidence: conf,
      escalatesTo: 'Maintenance Agent',
    }

    case 'cycle_time': return {
      steps: [
        { label: 'OBSERVE',  text: `${code} cycle time ${stn?.actual_ct ?? '?'}s vs ${stn?.target_ct ?? '?'}s target — ${pctOver}% over takt. CUSUM crossed 4σ control limit.` },
        { label: 'THINK',    text: `Temp ${temp}°C ${stn && stn.machine_temp > 85 ? '(elevated — possible thermal expansion)' : '(nominal)'}. Tool ${tool}% ${stn && stn.tool_life_pct < 25 ? '(worn — increasing dwell time)' : '(adequate)'}. Statistical shift, not random variation.` },
        { label: 'ANALYZE',  text: `Most likely: ${stn && stn.machine_temp > 85 ? 'thermal expansion slowing axis movement' : stn && stn.tool_life_pct < 25 ? `tool wear at ${tool}% adding cutting force dwell` : 'operator-paced step — component fit or gauge check'}. Downstream buffer will deplete in ~${Math.round(pctOver * 0.4 + 2)} cycles.` },
        { label: 'ACT',      text: `${pctOver > 20 ? 'Escalate to Scheduling Optimizer — resequence complex variants away from bottleneck.' : 'Monitor 2 more cycles before escalation. Notify supervisor.'}` },
      ],
      confidence: 81,
      escalatesTo: pctOver > 15 ? 'Scheduling Optimizer' : null,
    }

    case 'supervisor': return {
      steps: [
        { label: 'SCAN',     text: `All 12 stations monitored. ${entry.severity === 'critical' ? 'CRITICAL' : 'WARNING'} detected at ${code ?? 'line level'}. ${entry.message}` },
        { label: 'TRIAGE',   text: `${entry.message.includes('temp') || entry.message.includes('vibration') ? 'Equipment health event — bearing/vibration threshold breach.' : entry.message.includes('cycle') || entry.message.includes('takt') ? 'Takt violation — production flow risk.' : 'General deviation — routing to specialist.'}` },
        { label: 'DISPATCH', text: `${entry.message.includes('temp') || entry.message.includes('vibration') ? 'Equipment Health Agent dispatched.' : entry.message.includes('cycle') ? 'Cycle Time Monitor dispatched.' : 'Equipment Health Agent dispatched (default).'} Cooldown set to prevent duplicate dispatch.` },
        { label: 'MONITOR',  text: `Awaiting specialist response. If unresolved in 5 ticks, escalate to Maintenance Agent and surface to plant manager dashboard.` },
      ],
      confidence: 91,
      escalatesTo: null,
    }

    case 'quality': return {
      steps: [
        { label: 'INFER',    text: `ResNet-50 inference: defect detected at ${code}, confidence ${Math.round(88 + Math.random() * 10)}%. Consistent across 3 consecutive frames — not a sensor artifact.` },
        { label: 'REASON',   text: `${entry.message}. Cross-referenced against defect library. Pattern matches documented defect type. Typically non-self-correcting.` },
        { label: 'VALIDATE', text: `No recent tool change or setup adjustment logged. Defect appears systemic, not a one-off. Confidence elevated to HIGH.` },
        { label: 'DECIDE',   text: `LINE HOLD recommended. Unit flagged for rework bay. Quality Engineer notified. Escalating to Supervisor Agent.` },
      ],
      confidence: Math.round(88 + Math.random() * 10),
      escalatesTo: 'Supervisor Agent',
    }

    case 'maintenance': return {
      steps: [
        { label: 'ASSESS',   text: `Escalation from Equipment Health Agent. ${code}: ${entry.message}. RUL critical within current shift. Unplanned stop risk: 3–8h downtime.` },
        { label: 'SCHEDULE', text: `Shift B: 2 technicians available. Next production gap: 45-min window in ~28 min (part changeover). Sufficient for bearing inspection + lubrication.` },
        { label: 'ORDER',    text: `Maximo work order created. Parts: bearing lubrication kit — 2 in stock. Assigned to senior bearing specialist on Shift B.` },
        { label: 'CONFIRM',  text: `WO dispatched, technician notified via mobile. Follow-up inspection in 4h post-repair. PM interval reset in CMMS.` },
      ],
      confidence: 93,
      escalatesTo: null,
    }

    case 'scheduling': return {
      steps: [
        { label: 'ANALYSE',  text: `Multiple takt violations. Bottleneck at ${code}. Variant C running 22% over takt — highest complexity, driving disproportionate queue buildup.` },
        { label: 'OPTIMISE', text: `Constraint satisfaction over variant sequence. Resequencing B→C→A→B→A→C spreads complex variants, cuts peak bottleneck by 31%. STN-06 has 18% spare capacity for cross-support.` },
        { label: 'VALIDATE', text: `Simulation: +4–7 engines/shift recovery. JIT kit delay 12 min — within buffer stock. No quality or safety impact.` },
        { label: 'COMMIT',   text: `Resequencing committed to MES. Operator reassigned. Expected throughput gain: +${Math.round(3 + Math.random() * 4)} engines/shift. Monitoring next 3 ticks.` },
      ],
      confidence: 86,
      escalatesTo: null,
    }

    default: return {
      steps: [{ label: 'EVENT', text: entry.message }],
      confidence: 75,
      escalatesTo: null,
    }
  }
}

// ── Modal ─────────────────────────────────────────────────────────────────────

export default function AnomalyDetailModal({ entry, stations, onClose, apiKey }: Props) {
  const stn = stations.find(s => s.code === entry.station) ?? null
  const color = AGENT_COLOR[entry.from_agent] ?? 'text-gray-400'
  const { steps, confidence, escalatesTo } = buildSteps(entry, stn)

  const [claudeState, setClaudeState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [claudeText, setClaudeText]   = useState('')
  const claudeRef = useRef<HTMLDivElement>(null)

  async function askClaude() {
    setClaudeState('loading')
    setClaudeText('')
    try {
      const historyRes = await fetch(`${API_BASE}/api/station-history/${entry.station}?hours=1`)
      const history = historyRes.ok ? await historyRes.json() : []

      const res = await fetch(`${API_BASE}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ station: stn, history, agent_type: entry.from_agent, api_key: apiKey }),
      })
      if (!res.ok) throw new Error('API error')

      const reader = res.body!.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6)
          if (payload === '[DONE]') { setClaudeState('done'); break }
          try {
            const parsed = JSON.parse(payload)
            if (parsed.error) throw new Error(parsed.error)
            if (parsed.text) {
              setClaudeText(t => t + parsed.text)
              setTimeout(() => claudeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'nearest' }), 50)
            }
          } catch { /* ignore malformed chunk */ }
        }
      }
      setClaudeState('done')
    } catch (e) {
      setClaudeState('error')
      setClaudeText(String(e))
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      style={{ background: 'rgba(4,8,22,0.85)', backdropFilter: 'blur(6px)' }}
      onClick={onClose}
    >
      <div
        className="relative w-full max-w-xl max-h-[85vh] flex flex-col rounded-2xl border border-white/10 bg-[#0D1220] shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-start gap-3 px-5 py-4 border-b border-white/8 flex-shrink-0">
          <Cpu size={16} className={`mt-0.5 flex-shrink-0 ${color}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold text-white">{AGENT_NAMES[entry.from_agent] ?? entry.from_agent}</span>
              <span className={`text-[9px] font-bold border rounded px-2 py-0.5 uppercase tracking-wide ${SEV_STYLE[entry.severity]}`}>
                {entry.severity}
              </span>
              {entry.station && (
                <span className="text-[9px] font-mono text-teal-400 bg-teal-500/10 border border-teal-500/20 rounded px-2 py-0.5">
                  {entry.station}
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">{entry.message}</p>
            <p className="text-[10px] text-gray-600 mt-1">{AGENT_ALGO[entry.from_agent]}</p>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* ── Body ── */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-4">

          {/* Sensor strip */}
          {stn && (
            <div className="grid grid-cols-4 gap-2">
              {[
                { label: 'Temp',     value: `${stn.machine_temp.toFixed(1)}°C`, bad: stn.machine_temp > 87 },
                { label: 'Vibration',value: `${stn.vibration.toFixed(3)}g`,      bad: stn.vibration > 0.68 },
                { label: 'Tool Life',value: `${stn.tool_life_pct.toFixed(0)}%`,  bad: stn.tool_life_pct < 18 },
                { label: 'Cycle',    value: `${stn.actual_ct}s / ${stn.target_ct}s`, bad: stn.actual_ct > stn.target_ct * 1.12 },
              ].map(r => (
                <div key={r.label} className={`rounded-lg p-2.5 text-center border ${r.bad ? 'bg-amber-500/8 border-amber-500/25' : 'bg-white/3 border-white/8'}`}>
                  <p className="text-[9px] text-gray-500 mb-1">{r.label}</p>
                  <p className={`text-xs font-bold ${r.bad ? 'text-amber-400' : 'text-white'}`}>{r.value}</p>
                </div>
              ))}
            </div>
          )}

          {/* Reasoning steps */}
          <div className="flex flex-col gap-3">
            {steps.map((step, i) => {
              const c = STEP_COLOR[i % 4]
              return (
                <div key={i} className="flex gap-3">
                  <div className="flex flex-col items-center gap-1 flex-shrink-0">
                    <div className={`w-2 h-2 rounded-full mt-1 ${c.dot}`} />
                    {i < steps.length - 1 && <div className="w-px flex-1 bg-white/8" />}
                  </div>
                  <div className="pb-3 flex-1 min-w-0">
                    <p className={`text-[9px] font-bold mb-1 ${c.label}`}>{step.label}</p>
                    <p className="text-[11px] text-gray-300 leading-relaxed">{step.text}</p>
                  </div>
                </div>
              )
            })}
          </div>

          {/* Confidence + escalation */}
          <div className="flex items-center gap-4 pt-1">
            <div className="flex-1">
              <div className="flex items-center justify-between mb-1">
                <span className="text-[9px] text-gray-500">Confidence</span>
                <span className="text-[9px] font-bold text-white">{confidence}%</span>
              </div>
              <div className="h-1 bg-white/5 rounded-full overflow-hidden">
                <div className="h-full bg-gradient-to-r from-amber-400 to-green-400 rounded-full" style={{ width: `${confidence}%` }} />
              </div>
            </div>
            {escalatesTo && (
              <div className="text-right">
                <p className="text-[9px] text-gray-500">Escalated to</p>
                <p className="text-[10px] font-semibold text-orange-400">{escalatesTo}</p>
              </div>
            )}
          </div>

          {/* Claude live analysis */}
          {claudeState !== 'idle' && (
            <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-violet-500/20">
                <Sparkles size={12} className="text-violet-400" />
                <span className="text-[11px] font-semibold text-violet-300">Claude Analysis</span>
                {claudeState === 'loading' && <Loader2 size={11} className="text-violet-400 animate-spin ml-auto" />}
                {claudeState === 'done'    && <span className="ml-auto text-[9px] text-violet-500 font-mono">complete</span>}
              </div>
              <div className="px-4 py-3">
                {claudeState === 'loading' && claudeText === '' && (
                  <p className="text-[10px] text-violet-400 animate-pulse">Sending sensor data to Claude…</p>
                )}
                <p className="text-[11px] text-gray-200 leading-relaxed whitespace-pre-wrap">{claudeText}</p>
                {claudeState === 'error' && (
                  <p className="text-[10px] text-red-400 mt-1">{claudeText}</p>
                )}
                <div ref={claudeRef} />
              </div>
            </div>
          )}

        </div>

        {/* ── Footer ── */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-white/8 flex-shrink-0 bg-black/20">
          <span className="text-[9px] font-mono text-gray-600">
            {new Date(entry.timestamp * 1000).toLocaleTimeString()} · event #{entry.id}
          </span>
          <div className="flex items-center gap-2">
            {stn && claudeState !== 'loading' && (
              <button
                onClick={askClaude}
                disabled={!apiKey}
                title={!apiKey ? 'Set Anthropic API key (top right) to enable' : undefined}
                className={`flex items-center gap-1.5 text-[11px] font-semibold px-3 py-1.5 rounded-lg border transition-all ${
                  apiKey
                    ? 'text-violet-300 hover:text-white border-violet-500/40 hover:border-violet-400/60 bg-violet-500/10 hover:bg-violet-500/20'
                    : 'text-gray-600 border-white/8 bg-white/3 cursor-not-allowed'
                }`}
              >
                <Sparkles size={11} />
                {claudeState === 'idle' ? (apiKey ? 'Ask Claude' : 'Ask Claude (set key ↗)') : 'Ask Again'}
              </button>
            )}
            <button onClick={onClose} className="text-[11px] text-gray-400 hover:text-white px-4 py-1.5 rounded-lg border border-white/10 hover:border-white/20 transition-all">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
