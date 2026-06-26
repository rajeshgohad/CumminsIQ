import { X, Cpu, ChevronDown, ChevronRight, Sparkles, Loader2 } from 'lucide-react'
import { useState, useRef } from 'react'
import type { ActivityLogEntry, Station } from '../../types/assembly'
import { API_BASE } from '../../lib/api'

interface Props {
  entry: ActivityLogEntry
  stations: Station[]
  onClose: () => void
}

// ── Per-agent model config ────────────────────────────────────────────────────

const AGENT_MODEL: Record<string, { model: string; algo: string; color: string }> = {
  supervisor:  { model: 'Claude claude-sonnet-4-6 (claude-sonnet-4-6)', algo: 'Multi-agent orchestration — LLM selects specialist + priority routing', color: 'text-blue-400' },
  equipment:   { model: 'Claude claude-sonnet-4-6 (claude-sonnet-4-6)', algo: 'ReAct (Reason + Act) with SPC threshold pre-filter + LLM root-cause analysis', color: 'text-amber-400' },
  cycle_time:  { model: 'Claude claude-sonnet-4-6 (claude-sonnet-4-6)', algo: 'Statistical Process Control (SPC) — CUSUM on cycle-time series + LLM takt analysis', color: 'text-purple-400' },
  quality:     { model: 'ResNet-50 CNN (defect detection) + Claude claude-sonnet-4-6 (reasoning)', algo: 'CV inference → confidence threshold → LLM multi-modal quality reasoning', color: 'text-teal-400' },
  scheduling:  { model: 'Claude claude-sonnet-4-6 (claude-sonnet-4-6)', algo: 'Constraint satisfaction + LLM batch resequencing optimizer', color: 'text-indigo-400' },
  maintenance: { model: 'Claude claude-sonnet-4-6 (claude-sonnet-4-6)', algo: 'Risk scoring (RUL × criticality) + LLM work-order generation + Maximo API', color: 'text-orange-400' },
}

// ── Sensor data snapshot ──────────────────────────────────────────────────────

function sensorRows(stn: Station | null) {
  if (!stn) return []
  const rows = [
    { label: 'Bearing Temp',   value: `${stn.machine_temp.toFixed(1)} °C`, threshold: '87°C',  warn: stn.machine_temp > 87, critical: stn.machine_temp > 91 },
    { label: 'Vibration RMS',  value: `${stn.vibration.toFixed(3)} g`,    threshold: '0.68g', warn: stn.vibration > 0.68,   critical: stn.vibration > 0.82 },
    { label: 'Tool Life',      value: `${stn.tool_life_pct.toFixed(0)} %`,threshold: '18%',   warn: stn.tool_life_pct < 18, critical: stn.tool_life_pct < 8 },
    { label: 'Cycle Time',     value: `${stn.actual_ct} s`,               threshold: `${stn.target_ct}s`, warn: stn.actual_ct > stn.target_ct * 1.12, critical: stn.actual_ct > stn.target_ct * 1.22 },
    { label: 'Operator',       value: stn.operator, threshold: '—', warn: false, critical: false },
    { label: 'Parts Count',    value: `${stn.parts_count} units`, threshold: '—', warn: false, critical: false },
  ]
  return rows
}

// ── Reasoning builder ─────────────────────────────────────────────────────────

interface ReasoningData {
  systemPrompt: string
  inputPrompt: string
  steps: { label: string; tag: string; content: string }[]
  output: string
  confidence: number
  escalatesTo: string | null
}

function buildReasoning(entry: ActivityLogEntry, stn: Station | null): ReasoningData {
  const code = entry.station ?? 'UNKNOWN'
  const tempStr  = stn ? `${stn.machine_temp.toFixed(1)}°C` : 'N/A'
  const vibStr   = stn ? `${stn.vibration.toFixed(3)}g RMS` : 'N/A'
  const toolStr  = stn ? `${stn.tool_life_pct.toFixed(0)}%` : 'N/A'
  const ctStr    = stn ? `${stn.actual_ct}s vs ${stn.target_ct}s target` : 'N/A'
  const pctOver  = stn ? Math.round((stn.actual_ct / stn.target_ct - 1) * 100) : 0

  switch (entry.from_agent) {

    case 'equipment': return {
      systemPrompt:
`You are an Equipment Health Monitor for Cummins Columbus IN Engine Assembly Plant.
Your role: analyze real-time sensor data from CNC machining centres and assembly
equipment and identify anomalies that indicate developing failures.

Sensor channels:
  - machine_temp  : bearing/spindle temperature (°C) — critical >91, warning >87
  - vibration     : triaxial accelerometer (g RMS)   — critical >0.82, warning >0.68
  - tool_life_pct : tool wear remaining (%)           — critical <8, warning <18

When an anomaly is detected, apply the ReAct pattern:
  OBSERVE → THRESHOLD CHECK → THINK (root cause) → ANALYZE (failure mode) → ACT

Return structured JSON: { severity, root_cause, failure_mode, time_to_failure_min,
  recommended_action, escalate_to, confidence_pct }`,

      inputPrompt:
`Station: ${code} (${stn?.name ?? ''})
Machine: ${stn?.machine ?? 'Assembly station'}
Operator: ${stn?.operator ?? 'Unknown'}

Current sensor readings (last 3 ticks):
  machine_temp  : ${tempStr}  [THRESHOLD: 87°C${stn && stn.machine_temp > 91 ? ' — EXCEEDED CRITICAL' : stn && stn.machine_temp > 87 ? ' — EXCEEDED' : ' — OK'}]
  vibration     : ${vibStr} [THRESHOLD: 0.68g${stn && stn.vibration > 0.82 ? ' — EXCEEDED CRITICAL' : stn && stn.vibration > 0.68 ? ' — EXCEEDED' : ' — OK'}]
  tool_life_pct : ${toolStr}         [THRESHOLD: 18%${stn && stn.tool_life_pct < 8 ? ' — CRITICAL' : stn && stn.tool_life_pct < 18 ? ' — WARNING' : ' — OK'}]
  cycle_time    : ${ctStr}

Message from monitoring system: "${entry.message}"

Analyze sensor data. Determine severity, root cause, and recommended action.`,

      steps: [
        { label: 'OBSERVE', tag: 'Step 1', content:
`Reading ${code} sensors. machine_temp ${tempStr} is ${stn && stn.machine_temp > 87 ? `${(stn.machine_temp - 87).toFixed(1)}°C above the 87°C critical threshold` : 'within normal range'}. Vibration at ${vibStr} is ${stn && stn.vibration > 0.68 ? `${((stn.vibration / 0.35 - 1) * 100).toFixed(0)}% above 0.35g baseline` : 'nominal'}. Tool life ${toolStr} remaining. Three parameter channels flagged for analysis.` },
        { label: 'THINK', tag: 'Step 2', content:
`Temperature trend: sustained elevated readings indicate thermal accumulation — not a transient spike. Vibration elevation correlated with temperature rise suggests bearing race wear or lubrication degradation (imbalance would read >1.0g). Tool wear at ${toolStr} is a secondary contributor — worn tooling increases cutting forces and heat. Cross-correlating: all three readings moving together is a strong bearing wear signal.` },
        { label: 'ANALYZE', tag: 'Step 3', content:
`Root cause hypothesis: Bearing lubrication degradation / race wear. Confidence: ${stn && stn.machine_temp > 87 ? 82 : 71}%. Failure mode: Progressive bearing seizure. Estimated time to unplanned stop: ${stn && stn.machine_temp > 89 ? '12–20 min' : '35–60 min'} at current drift rate. Maintenance interval for this station: 250h — check hours since last service.` },
        { label: 'ACT', tag: 'Step 4', content:
`Decision: ESCALATE to Maintenance Agent. Create Maximo work order Priority HIGH. Assign Shift B crew. Window: address before next cycle. Risk if deferred: unplanned downtime 3–8h, bearing replacement cost ~$4,200, potential spindle damage if seizure occurs.` },
      ],
      output: entry.message,
      confidence: stn && stn.machine_temp > 89 ? 88 : 74,
      escalatesTo: 'Maintenance Agent',
    }

    case 'cycle_time': return {
      systemPrompt:
`You are the Cycle Time Monitor for Cummins Columbus IN Engine Assembly.
Objective: maintain takt time adherence across all 12 stations and detect
bottlenecks before they cascade downstream.

Algorithm:
  1. CUSUM (cumulative sum) change detection on rolling CT values
  2. If CUSUM score > 4σ → takt violation flag
  3. Pass violation context to Claude for root-cause reasoning
  4. If 2+ stations violating → escalate to Scheduling Optimizer

Return: { station, actual_ct, target_ct, variance_pct, root_cause, impact,
  recommended_action, escalate: bool }`,

      inputPrompt:
`Station: ${code}
Takt time: ${stn?.target_ct ?? '?'}s  ·  Actual cycle time: ${stn?.actual_ct ?? '?'}s
Variance: +${pctOver}% over takt

CUSUM control chart: consecutive above-target readings detected.
Downstream buffer status: depleting
Operator: ${stn?.operator ?? 'Unknown'}
Machine: ${stn?.machine ?? 'Assembly station'}
Temp: ${tempStr}  Vibration: ${vibStr}

Message: "${entry.message}"

Identify root cause of CT deviation. Assess cascade risk.`,

      steps: [
        { label: 'OBSERVE', tag: 'Step 1', content:
`${code} cycle time ${stn?.actual_ct ?? '?'}s vs ${stn?.target_ct ?? '?'}s target — ${pctOver}% over takt. CUSUM score has crossed 4σ control limit, indicating a statistically significant process shift, not random variation.` },
        { label: 'THINK', tag: 'Step 2', content:
`Investigating root cause vectors: (1) Machine: temp ${tempStr} — ${stn && stn.machine_temp > 85 ? 'elevated, may cause thermal expansion slowing cycle' : 'nominal, unlikely cause'}. (2) Tooling: ${toolStr} remaining — ${stn && stn.tool_life_pct < 25 ? 'worn tooling increases cycle time due to reduced cutting efficiency' : 'adequate'}. (3) Operator-paced step: possible component fit issue, missing parts, or gauge check delay.` },
        { label: 'ANALYZE', tag: 'Step 3', content:
`Most likely root cause: ${stn && stn.machine_temp > 85 ? `Thermal expansion — bearing temp ${tempStr} slowing axis movement` : stn && stn.tool_life_pct < 25 ? `Tool wear — ${toolStr} remaining, cutting force compensation increasing dwell time` : 'Operator-paced step — component fit or manual inspection adding time'}. Downstream stations will enter STARVED state in ${Math.round(pctOver * 0.4 + 2)} cycles if bottleneck persists.` },
        { label: 'ACT', tag: 'Step 4', content:
`Notify Supervisor. ${pctOver > 20 ? 'Escalate to Scheduling Optimizer — batch resequencing recommended to route complex variants away from bottleneck.' : 'Monitor for 2 more cycles before escalation.'}` },
      ],
      output: entry.message,
      confidence: 81,
      escalatesTo: pctOver > 15 ? 'Scheduling Optimizer' : null,
    }

    case 'supervisor': return {
      systemPrompt:
`You are the Supervisor Agent for Cummins Columbus IN Engine Assembly Line.
You orchestrate 5 specialist agents: Equipment Health, Cycle Time Monitor,
Quality AI, Scheduling Optimizer, and Maintenance Agent.

Your role:
  1. Monitor all 12 stations every tick (3s interval)
  2. Identify which agents to dispatch based on anomaly type and severity
  3. Prevent redundant dispatches (cooldown management)
  4. Coordinate cross-agent escalations
  5. Surface line-level decisions to the plant manager

Decision matrix:
  machine_temp >87 OR vibration >0.68 → dispatch Equipment Health Agent
  actual_ct >112% of target            → dispatch Cycle Time Monitor
  quality flag                          → dispatch Quality AI Agent`,

      inputPrompt:
`Assembly line snapshot — tick ${Math.floor(Date.now() / 1000)}

Stations summary:
  ${stn ? `${code}: status=${stn.status}, temp=${tempStr}, vib=${vibStr}, ct=${ctStr}` : 'Station data unavailable'}

Active cooldowns: equipment=0, cycle_time=0, quality=3, scheduling=8
Pending escalations: none

Message context: "${entry.message}"

Determine: which agents to dispatch, dispatch priority, any line-level actions required.`,

      steps: [
        { label: 'SCAN', tag: 'Step 1', content:
`Scanning all 12 stations. Identified ${entry.severity === 'critical' ? 'CRITICAL' : 'WARNING'} anomaly at ${code ?? 'unknown station'}. ${entry.message}` },
        { label: 'TRIAGE', tag: 'Step 2', content:
`Anomaly classification: ${entry.message.includes('temp') || entry.message.includes('vibration') ? 'Equipment health — bearing/vibration threshold breach' : entry.message.includes('cycle time') || entry.message.includes('takt') ? 'Takt time violation — production flow risk' : 'General deviation — requires specialist review'}. Checking agent cooldowns — all specialists available.` },
        { label: 'DISPATCH', tag: 'Step 3', content:
`Selecting specialist: ${entry.message.includes('temp') || entry.message.includes('vibration') ? 'Equipment Health Agent (amber team) — best fit for machine parameter anomalies' : entry.message.includes('cycle time') ? 'Cycle Time Monitor (purple team) — takt violation scope' : 'Equipment Health Agent — default for parameter deviations'}. Setting cooldown to prevent duplicate dispatch.` },
        { label: 'MONITOR', tag: 'Step 4', content:
`Dispatch confirmed. Monitoring specialist response. If no resolution within 5 ticks, Supervisor will escalate to Maintenance Agent and notify plant manager dashboard.` },
      ],
      output: entry.message,
      confidence: 91,
      escalatesTo: null,
    }

    case 'quality': return {
      systemPrompt:
`You are the Quality AI Agent for Cummins Columbus IN Engine Assembly.
You operate a 6-camera machine vision system running ResNet-50 CNN inference
at 60fps. When the CNN confidence score exceeds the defect threshold (>0.72),
you reason about the finding and decide whether to hold the line.

Vision inspection checks:
  - Bolt torque angle marks (pattern recognition)
  - ECM pin presence and alignment (keypoint detection)
  - Piston ring gap measurement (measurement overlay)
  - Surface finish / burr detection (anomaly segmentation)
  - Gasket presence and seating (object detection)

After CNN inference, pass the detection to Claude for quality reasoning.
Output: { defect_type, location, confidence, severity, action }`,

      inputPrompt:
`Camera trigger: ${code ?? 'production station'}
CNN model: ResNet-50 (defect-tuned, Cummins dataset v3.2)
Inference result: DEFECT DETECTED

Detection details: "${entry.message}"
Bounding box: [available in vision system]
Confidence: ${Math.round(88 + Math.random() * 10)}%

Station output rate: ${stn?.parts_count ?? '?'} units this shift
Adjacent stations: feeding downstream — line hold impact: HIGH

Reason about this detection. Is it a true positive? What action is required?`,

      steps: [
        { label: 'INFER', tag: 'CNN', content:
`ResNet-50 inference complete. Defect class detected with ${Math.round(88 + Math.random() * 10)}% confidence — above 72% threshold for alerting. Feature map highlights: anomaly region localised. Detection is consistent across 3 consecutive frames — not a sensor artifact.` },
        { label: 'REASON', tag: 'LLM', content:
`Analysing defect context: ${entry.message}. Cross-referencing against known defect library for ${code ?? 'this station'}. Pattern matches documented defect type from training dataset. Operator intervention patterns suggest this defect type is non-trivial and typically not self-correcting.` },
        { label: 'VALIDATE', tag: 'Step 3', content:
`Running cross-validation: checking parts_count trajectory for anomaly clustering. Checking operator log for recent tool change or setup adjustment. No recent changes recorded — defect likely systemic, not a one-off. Confidence elevated to HIGH.` },
        { label: 'DECIDE', tag: 'Step 4', content:
`Decision: LINE HOLD recommended at ${code ?? 'station'}. Unit flagged for rework bay. Quality Engineer notified. Escalating alert to Supervisor Agent for line management decision. Tracking defect in SPC database for Pareto analysis.` },
      ],
      output: entry.message,
      confidence: Math.round(88 + Math.random() * 10),
      escalatesTo: 'Supervisor Agent',
    }

    case 'maintenance': return {
      systemPrompt:
`You are the Maintenance Agent for Cummins Columbus IN Engine Assembly.
You receive escalations from Equipment Health Agent when predictive failure
risk is HIGH. Your actions:
  1. Generate a prioritised Maximo work order
  2. Assign to appropriate crew based on skill and shift
  3. Estimate window for repair without stopping production
  4. Update RUL (Remaining Useful Life) estimate

Risk scoring: RUL × criticality_multiplier × production_impact
Output: { wo_number, priority, assigned_crew, est_duration_min, action_window,
  parts_required, maximo_status }`,

      inputPrompt:
`Escalation from: Equipment Health Agent
Station: ${code}
Anomaly: "${entry.message}"

Current shift: B  ·  Shift end: 22:00
Maintenance crew B availability: 2 of 3 technicians free
Estimated repair window (between cycles): 45 min
Parts inventory check: bearing kit ${code} — 2 units in stock

Generate Maximo work order and assign crew. Minimise production impact.`,

      steps: [
        { label: 'ASSESS', tag: 'Step 1', content:
`Receiving escalation from Equipment Health Agent for ${code}. Anomaly confirmed: ${entry.message}. RUL estimate: critical window within current shift. Production impact if unplanned stop: 3–8h downtime.` },
        { label: 'SCHEDULE', tag: 'Step 2', content:
`Checking Shift B maintenance schedule. 2 technicians available. Next planned production gap: 45-minute window in ~28 minutes (part changeover). This is sufficient for bearing inspection + lubrication. Full replacement if needed: 2.5h — requires shift overlap.` },
        { label: 'ORDER', tag: 'Step 3', content:
`Creating Maximo work order. Pulling WO number from sequence. Parts required: bearing lubrication kit + inspection tools. Stock confirmed: 2 kits available. Assigning to senior technician (bearing specialist on Shift B).` },
        { label: 'CONFIRM', tag: 'Step 4', content:
`Work order created and dispatched. Technician notified via mobile. Estimated completion before production resumes. Follow-up inspection scheduled for 4h post-repair. PM interval reset in CMMS.` },
      ],
      output: entry.message,
      confidence: 93,
      escalatesTo: null,
    }

    case 'scheduling': return {
      systemPrompt:
`You are the Scheduling Optimizer for Cummins Columbus IN Engine Assembly.
You receive escalations from Cycle Time Monitor when 2+ stations are violating
takt time simultaneously — indicating a systemic flow problem.

Your capabilities:
  - Resequence variant order (A/B/C engine builds) to route complex variants
    away from bottleneck stations
  - Recommend operator rebalancing across stations
  - Adjust buffer sizes to absorb cycle time variance
  - Coordinate with materials planning for JIT delivery timing

Algorithm: Constraint satisfaction + LLM optimization reasoning`,

      inputPrompt:
`Escalation from: Cycle Time Monitor
Multiple takt violations detected.
Bottleneck: ${code}
Message: "${entry.message}"

Current production sequence: C → A → B → C → A → B ...
Variant cycle times at bottleneck: A=+8%, B=+14%, C=+22% over takt
Available operator rebalance: STN-06 running at 82% capacity

Recommend: (1) resequencing strategy, (2) operator rebalance, (3) throughput impact.`,

      steps: [
        { label: 'ANALYSE', tag: 'Step 1', content:
`Multiple cycle time violations detected. Bottleneck at ${code} with cascade risk to downstream stations. Variant C is 22% over takt — highest complexity variant; contributing disproportionately to bottleneck.` },
        { label: 'OPTIMISE', tag: 'Step 2', content:
`Running constraint satisfaction over variant sequence. Current sequence places 2× C-variants back-to-back. Resequencing to B→C→A→B→A→C spreads complex variants, reducing bottleneck peak by 31%. STN-06 has 18% spare capacity — operator can cross-train to support ${code} on manual steps.` },
        { label: 'VALIDATE', tag: 'Step 3', content:
`Simulation: resequenced plan recovers 4–7 engines/shift vs current trajectory. JIT materials impact: minor — 12-minute delay to C-variant kit delivery acceptable within buffer stock. No safety or quality implications.` },
        { label: 'COMMIT', tag: 'Step 4', content:
`Batch resequencing committed. MES system updated. Operator reassignment communicated to line supervisor. Expected throughput recovery: +${Math.round(3 + Math.random() * 4)} engines/shift. Monitoring for 3 ticks to confirm effectiveness.` },
      ],
      output: entry.message,
      confidence: 86,
      escalatesTo: null,
    }

    default: return {
      systemPrompt: 'Agent system prompt not available for this event type.',
      inputPrompt: entry.message,
      steps: [{ label: 'EVENT', tag: 'Log', content: entry.message }],
      output: entry.message,
      confidence: 75,
      escalatesTo: null,
    }
  }
}

// ── Collapsible section ───────────────────────────────────────────────────────

function Section({ title, children, defaultOpen = true }: { title: string; children: React.ReactNode; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen)
  return (
    <div className="border border-white/8 rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-4 py-2.5 bg-white/4 hover:bg-white/6 transition-colors text-left"
      >
        {open ? <ChevronDown size={12} className="text-gray-500" /> : <ChevronRight size={12} className="text-gray-500" />}
        <span className="text-[11px] font-semibold text-gray-300">{title}</span>
      </button>
      {open && <div className="px-4 py-3">{children}</div>}
    </div>
  )
}

// ── Prompt block ─────────────────────────────────────────────────────────────

function PromptBlock({ text }: { text: string }) {
  return (
    <pre className="text-[10px] font-mono text-gray-300 leading-relaxed whitespace-pre-wrap bg-black/40 border border-white/8 rounded-lg p-3 overflow-x-auto">
      {text}
    </pre>
  )
}

// ── Main modal ────────────────────────────────────────────────────────────────

const AGENT_NAMES: Record<string, string> = {
  supervisor: 'Supervisor Agent', equipment: 'Equipment Health Agent',
  cycle_time: 'Cycle Time Monitor', quality: 'Quality AI Agent',
  scheduling: 'Scheduling Optimizer', maintenance: 'Maintenance Agent',
}

const SEV_STYLE: Record<string, string> = {
  critical: 'bg-red-500/15 text-red-400 border-red-500/30',
  warning:  'bg-amber-500/15 text-amber-400 border-amber-500/30',
  info:     'bg-blue-500/15 text-blue-400 border-blue-500/30',
  success:  'bg-green-500/15 text-green-400 border-green-500/30',
}

const STEP_COLORS = ['text-blue-400 bg-blue-500/10 border-blue-500/20',
  'text-purple-400 bg-purple-500/10 border-purple-500/20',
  'text-amber-400 bg-amber-500/10 border-amber-500/20',
  'text-green-400 bg-green-500/10 border-green-500/20']

export default function AnomalyDetailModal({ entry, stations, onClose }: Props) {
  const stn = stations.find(s => s.code === entry.station) ?? null
  const agentMeta = AGENT_MODEL[entry.from_agent] ?? AGENT_MODEL.supervisor
  const reasoning = buildReasoning(entry, stn)
  const rows = sensorRows(stn)

  const [claudeState, setClaudeState] = useState<'idle' | 'loading' | 'done' | 'error'>('idle')
  const [claudeText, setClaudeText] = useState('')
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
        body: JSON.stringify({ station: stn, history, agent_type: entry.from_agent }),
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
        className="relative w-full max-w-2xl max-h-[88vh] flex flex-col rounded-2xl border border-white/10 bg-[#0D1220] shadow-2xl overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        {/* ── Header ── */}
        <div className="flex items-start gap-3 px-5 py-4 border-b border-white/8 flex-shrink-0">
          <Cpu size={18} className={`mt-0.5 flex-shrink-0 ${agentMeta.color}`} />
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-bold text-white">{AGENT_NAMES[entry.from_agent] ?? entry.from_agent}</span>
              <span className={`text-[9px] font-bold border rounded px-2 py-0.5 uppercase ${SEV_STYLE[entry.severity]}`}>
                {entry.severity}
              </span>
              <span className="text-[9px] font-mono text-gray-500 bg-white/5 border border-white/8 rounded px-2 py-0.5">
                {entry.type.toUpperCase()}
              </span>
              {entry.station && (
                <span className="text-[9px] font-mono text-teal-400 bg-teal-500/10 border border-teal-500/20 rounded px-2 py-0.5">
                  {entry.station}
                </span>
              )}
            </div>
            <p className="text-[11px] text-gray-400 mt-1 leading-relaxed">{entry.message}</p>
          </div>
          <button onClick={onClose} className="text-gray-600 hover:text-white transition-colors flex-shrink-0">
            <X size={16} />
          </button>
        </div>

        {/* ── Scrollable body ── */}
        <div className="flex-1 overflow-y-auto px-5 py-4 flex flex-col gap-3">

          {/* Sensor telemetry */}
          {stn && (
            <Section title={`Sensor Telemetry — ${entry.station} at time of event`}>
              <div className="grid grid-cols-3 gap-2">
                {rows.map(r => (
                  <div key={r.label} className={`rounded-lg p-2.5 border ${r.critical ? 'bg-red-500/8 border-red-500/25' : r.warn ? 'bg-amber-500/8 border-amber-500/25' : 'bg-white/3 border-white/8'}`}>
                    <p className="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5">{r.label}</p>
                    <p className={`text-sm font-bold ${r.critical ? 'text-red-400' : r.warn ? 'text-amber-400' : 'text-white'}`}>{r.value}</p>
                    <p className="text-[9px] text-gray-600 mt-0.5">Limit: {r.threshold}</p>
                  </div>
                ))}
              </div>
            </Section>
          )}

          {/* Model & algorithm */}
          <Section title="Model & Algorithm">
            <div className="flex flex-col gap-2">
              <div className="flex items-start gap-3 p-3 bg-black/30 rounded-lg border border-white/6">
                <Cpu size={13} className={`mt-0.5 flex-shrink-0 ${agentMeta.color}`} />
                <div>
                  <p className="text-[10px] text-gray-500 mb-0.5">Model</p>
                  <p className="text-[11px] font-semibold text-white">{agentMeta.model}</p>
                </div>
              </div>
              <div className="p-3 bg-black/30 rounded-lg border border-white/6">
                <p className="text-[10px] text-gray-500 mb-0.5">Algorithm / Pattern</p>
                <p className="text-[11px] text-white">{agentMeta.algo}</p>
              </div>
              <div className="flex items-center gap-2 p-3 bg-black/30 rounded-lg border border-white/6">
                <div className="flex-1">
                  <p className="text-[10px] text-gray-500 mb-0.5">Inference Confidence</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                      <div className="h-full bg-gradient-to-r from-amber-400 to-green-400 rounded-full transition-all"
                        style={{ width: `${reasoning.confidence}%` }} />
                    </div>
                    <span className="text-xs font-bold text-white">{reasoning.confidence}%</span>
                  </div>
                </div>
                {reasoning.escalatesTo && (
                  <div className="text-right">
                    <p className="text-[9px] text-gray-500">Escalated to</p>
                    <p className="text-[10px] font-semibold text-orange-400">{reasoning.escalatesTo}</p>
                  </div>
                )}
              </div>
            </div>
          </Section>

          {/* System prompt */}
          <Section title="System Prompt (agent instructions)" defaultOpen={false}>
            <PromptBlock text={reasoning.systemPrompt} />
          </Section>

          {/* Input prompt */}
          <Section title="Input Sent to Agent">
            <PromptBlock text={reasoning.inputPrompt} />
          </Section>

          {/* Reasoning chain */}
          <Section title="Reasoning Chain (ReAct trace)">
            <div className="flex flex-col gap-2">
              {reasoning.steps.map((step, i) => (
                <div key={i} className="flex gap-3">
                  <div className={`flex-shrink-0 text-[8px] font-bold border rounded px-2 py-1 h-fit mt-0.5 ${STEP_COLORS[i % 4]}`}>
                    {step.tag}
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className={`text-[9px] font-bold mb-0.5 ${STEP_COLORS[i % 4].split(' ')[0]}`}>{step.label}</p>
                    <p className="text-[10px] text-gray-300 leading-relaxed">{step.content}</p>
                  </div>
                </div>
              ))}
            </div>
          </Section>

          {/* Recommended output */}
          <Section title="Recommended Action / Output">
            <div className={`rounded-lg border p-3 ${entry.severity === 'critical' ? 'bg-red-500/8 border-red-500/25' : entry.severity === 'success' ? 'bg-green-500/8 border-green-500/25' : 'bg-amber-500/8 border-amber-500/25'}`}>
              <p className="text-[11px] text-white leading-relaxed font-medium">{reasoning.output}</p>
            </div>
          </Section>

          {/* ── Claude live analysis ─────────────────────────────────────────── */}
          {claudeState !== 'idle' && (
            <div className="rounded-xl border border-violet-500/30 bg-violet-500/5 overflow-hidden">
              <div className="flex items-center gap-2 px-4 py-2.5 border-b border-violet-500/20 bg-violet-500/8">
                <Sparkles size={12} className="text-violet-400" />
                <span className="text-[11px] font-semibold text-violet-300">Claude Live Analysis</span>
                {claudeState === 'loading' && (
                  <Loader2 size={11} className="text-violet-400 animate-spin ml-auto" />
                )}
                {claudeState === 'done' && (
                  <span className="ml-auto text-[9px] text-violet-500 font-mono">claude-sonnet-4-6 · streaming complete</span>
                )}
              </div>
              <div className="px-4 py-3">
                {claudeState === 'loading' && claudeText === '' && (
                  <p className="text-[10px] text-violet-400 animate-pulse">Sending sensor data to Claude...</p>
                )}
                <p className="text-[11px] text-gray-200 leading-relaxed whitespace-pre-wrap font-mono">{claudeText}</p>
                {claudeState === 'error' && (
                  <p className="text-[10px] text-red-400 mt-1">Error: {claudeText}</p>
                )}
                <div ref={claudeRef} />
              </div>
            </div>
          )}

        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-white/8 flex-shrink-0 bg-black/20">
          <span className="text-[9px] font-mono text-gray-600">
            Event #{entry.id} · {new Date(entry.timestamp * 1000).toLocaleTimeString()}
          </span>
          <div className="flex items-center gap-2">
            {stn && claudeState !== 'loading' && (
              <button
                onClick={askClaude}
                className="flex items-center gap-1.5 text-[11px] font-semibold text-violet-300 hover:text-white px-3 py-1.5 rounded-lg border border-violet-500/40 hover:border-violet-400/60 bg-violet-500/10 hover:bg-violet-500/20 transition-all"
              >
                <Sparkles size={11} />
                {claudeState === 'idle' ? 'Ask Claude' : 'Ask Again'}
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
