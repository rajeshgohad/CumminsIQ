import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, XCircle, ScanSearch } from 'lucide-react'

export interface LogEntry {
  id: number
  ts: number
  station: string
  check: string
  result: 'pass' | 'fail'
  detail: string
  confidence: number
}

interface Props {
  onDefectClick?: (entry: LogEntry) => void
}

const FAIL_DETAILS = [
  ['STN-09 · ECM & Electrical',    'ECM Connector Pin', 'Bent pin detected — P31 deflection 18°'],
  ['STN-05 · Cylinder Head Torque','Bolt Torque Angle',  'B3 torque mark absent — under-torqued'],
  ['STN-03 · Piston & Con-Rod',    'Ring End Gap',       'Gap 0.48mm exceeds 0.40mm limit'],
  ['STN-01 · Cylinder Block Prep', 'Surface Finish',     'Burr detected — height 0.38mm > 0.15mm limit'],
  ['STN-04 · Final Torque',        'Torque Angle',       'Measured 67° vs target 90° — rework required'],
  ['STN-05 · Cylinder Head Torque','Head Gasket',        'Gasket fold detected — seating incomplete'],
]

let _logId = 0

export default function DefectLog({ onDefectClick }: Props) {
  const [entries, setEntries] = useState<LogEntry[]>([])

  useEffect(() => {
    const seed: LogEntry[] = [
      { id: ++_logId, ts: Date.now() / 1000 - 280, station: 'STN-03 · Piston & Con-Rod', check: 'Ring End Gap',   result: 'fail', detail: 'Gap 0.51mm exceeds 0.40mm limit', confidence: 94 },
      { id: ++_logId, ts: Date.now() / 1000 - 195, station: 'STN-09 · ECM & Electrical', check: 'Pin Inspection', result: 'fail', detail: 'Bent pin P31 — deflection 22°', confidence: 97 },
      { id: ++_logId, ts: Date.now() / 1000 - 120, station: 'STN-01 · Block Prep',       check: 'Surface Finish', result: 'pass', detail: 'Ra 0.9μm — within spec',          confidence: 99 },
      { id: ++_logId, ts: Date.now() / 1000 - 60,  station: 'STN-05 · Head Torque',      check: 'Bolt Pattern',   result: 'pass', detail: 'All 6 torque marks confirmed',     confidence: 98 },
    ]
    setEntries(seed)

    const t = setInterval(() => {
      const isFail = Math.random() < 0.22
      const now = Date.now() / 1000
      let entry: LogEntry
      if (isFail) {
        const [station, check, detail] = FAIL_DETAILS[Math.floor(Math.random() * FAIL_DETAILS.length)]
        entry = { id: ++_logId, ts: now, station, check, result: 'fail', detail, confidence: Math.round(88 + Math.random() * 10) }
      } else {
        const passes = [
          ['STN-05 · Cylinder Head Torque','Bolt Pattern',   'All 6 torque marks confirmed'],
          ['STN-01 · Cylinder Block Prep', 'Surface Finish', 'Ra 0.8μm · no burrs detected'],
          ['STN-03 · Piston & Con-Rod',    'Ring End Gap',   'Gap 0.29mm — within 0.20–0.40mm spec'],
          ['STN-09 · ECM & Electrical',    'Pin Inspection', '50 pins present · alignment nominal'],
          ['STN-04 · Final Torque',        'Torque Angle',   '91° confirmed — within ±5° tolerance'],
        ]
        const [station, check, detail] = passes[Math.floor(Math.random() * passes.length)]
        entry = { id: ++_logId, ts: now, station, check, result: 'pass', detail, confidence: Math.round(93 + Math.random() * 6) }
      }
      setEntries(prev => [entry, ...prev].slice(0, 30))
    }, 8000)

    return () => clearInterval(t)
  }, [])

  function timeAgo(ts: number) {
    const d = Math.floor(Date.now() / 1000 - ts)
    if (d < 60) return `${d}s ago`
    if (d < 3600) return `${Math.floor(d / 60)}m ago`
    return `${Math.floor(d / 3600)}h ago`
  }

  return (
    <div className="flex flex-col gap-2 h-full">
      <div className="flex items-center gap-2 mb-1">
        <AlertTriangle size={13} className="text-amber-400" />
        <span className="text-xs font-semibold text-white">Inspection Event Log</span>
        <span className="ml-auto text-[10px] text-gray-500">{entries.filter(e => e.result === 'fail').length} defects / {entries.length} inspections</span>
      </div>

      <div className="flex flex-col gap-1.5 flex-1 overflow-y-auto">
        {entries.map(e => (
          <div key={e.id} className={`rounded-lg border px-3 py-2 flex items-start gap-2.5 transition-all
            ${e.result === 'fail' ? 'border-red-500/25 bg-red-500/5' : 'border-green-500/15 bg-green-500/3'}`}>
            {e.result === 'fail'
              ? <XCircle size={12} className="text-red-400 flex-shrink-0 mt-0.5" />
              : <CheckCircle2 size={12} className="text-green-400 flex-shrink-0 mt-0.5" />}
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-[10px] font-mono text-gray-400">{e.station}</span>
                <span className={`ml-auto text-[9px] font-bold ${e.result === 'fail' ? 'text-red-400' : 'text-green-400'}`}>
                  {e.result === 'fail' ? 'FAIL' : 'PASS'} {e.confidence}%
                </span>
              </div>
              <p className="text-[10px] font-semibold text-white mb-0.5">{e.check}</p>
              <p className="text-[9px] text-gray-500 leading-relaxed">{e.detail}</p>
              {e.result === 'fail' && onDefectClick && (
                <button
                  onClick={() => onDefectClick(e)}
                  className="mt-1.5 flex items-center gap-1 text-[9px] font-semibold text-teal-400 hover:text-white border border-teal-500/30 bg-teal-500/8 hover:bg-teal-500/20 rounded px-2 py-0.5 transition-all"
                >
                  <ScanSearch size={9} />
                  Investigate with AI Agent
                </button>
              )}
            </div>
            <span className="text-[9px] text-gray-600 flex-shrink-0">{timeAgo(e.ts)}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
