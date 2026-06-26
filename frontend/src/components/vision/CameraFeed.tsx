import { useEffect, useState } from 'react'
import { Camera, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react'

export interface Inspection {
  id: string
  station: string
  title: string
  spec: string
  render: (state: InspectionState) => React.ReactNode
  passCondition: () => boolean   // called each cycle to determine outcome
}

export type InspectionState = 'scanning' | 'pass' | 'fail' | 'warn'

interface Props {
  inspection: Inspection
  frameRate?: number   // seconds between re-evaluation
}

function ScanOverlay() {
  return (
    <div className="absolute inset-0 overflow-hidden pointer-events-none">
      <div className="absolute left-0 right-0 h-px bg-green-400/60 animate-[scan_2s_linear_infinite]"
        style={{ boxShadow: '0 0 8px 2px rgba(74,222,128,0.4)' }} />
      <style>{`
        @keyframes scan { 0% { top: 0%; } 100% { top: 100%; } }
      `}</style>
    </div>
  )
}

export default function CameraFeed({ inspection, frameRate = 5 }: Props) {
  const [state, setState] = useState<InspectionState>('scanning')
  const [frameCount, setFrameCount] = useState(0)
  const [confidence, setConfidence] = useState(0)

  useEffect(() => {
    setState('scanning')
    const t = setTimeout(() => {
      const pass = inspection.passCondition()
      setState(pass ? 'pass' : 'fail')
      setConfidence(pass ? Math.round(92 + Math.random() * 7) : Math.round(88 + Math.random() * 10))
      setFrameCount(c => c + 1)
    }, 1200)
    return () => clearTimeout(t)
  }, [frameCount, inspection])

  useEffect(() => {
    const t = setInterval(() => setFrameCount(c => c + 1), frameRate * 1000)
    return () => clearInterval(t)
  }, [frameRate])

  const stateColor = state === 'pass' ? 'border-green-500/60' : state === 'fail' ? 'border-red-500/60' : state === 'warn' ? 'border-amber-500/60' : 'border-gray-600/40'
  const StateIcon  = state === 'pass' ? CheckCircle2 : state === 'fail' ? XCircle : AlertTriangle

  return (
    <div className={`rounded-xl border ${stateColor} bg-black overflow-hidden transition-colors duration-500`}>
      {/* Camera header bar */}
      <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-900/80 border-b border-white/5">
        <Camera size={10} className="text-gray-500" />
        <span className="text-[9px] font-mono text-gray-500">{inspection.station}</span>
        <span className="text-[9px] text-gray-600 flex-1 truncate">{inspection.title}</span>
        <div className={`flex items-center gap-1 text-[9px] font-bold ${
          state === 'scanning' ? 'text-gray-500' :
          state === 'pass'    ? 'text-green-400' :
          state === 'fail'    ? 'text-red-400'   : 'text-amber-400'
        }`}>
          {state !== 'scanning' && <StateIcon size={9} />}
          {state === 'scanning' ? (
            <span className="animate-pulse">SCANNING…</span>
          ) : (
            <span>{state.toUpperCase()} {confidence}%</span>
          )}
        </div>
      </div>

      {/* Camera view */}
      <div className="relative aspect-[4/3] bg-[#060810]">
        {inspection.render(state)}
        {state === 'scanning' && <ScanOverlay />}

        {/* Corner crosshairs */}
        <div className="absolute top-2 left-2 w-4 h-4 border-t border-l border-green-500/40" />
        <div className="absolute top-2 right-2 w-4 h-4 border-t border-r border-green-500/40" />
        <div className="absolute bottom-2 left-2 w-4 h-4 border-b border-l border-green-500/40" />
        <div className="absolute bottom-2 right-2 w-4 h-4 border-b border-r border-green-500/40" />

        {/* Frame counter */}
        <div className="absolute bottom-2 left-1/2 -translate-x-1/2 text-[8px] font-mono text-green-500/40">
          FR#{String(frameCount).padStart(6, '0')}
        </div>
      </div>

      {/* Spec bar */}
      <div className="px-3 py-1.5 bg-gray-900/60 border-t border-white/5">
        <p className="text-[9px] text-gray-500">{inspection.spec}</p>
      </div>
    </div>
  )
}
