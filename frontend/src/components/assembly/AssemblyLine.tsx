import { ArrowRight } from 'lucide-react'
import StationCard from './StationCard'
import type { Station } from '../../types/assembly'

interface Props { stations: Station[] }

export default function AssemblyLine({ stations }: Props) {
  const row1 = stations.slice(0, 6)
  const row2 = stations.slice(6, 12)

  return (
    <div className="flex flex-col gap-3">
      <div className="text-[10px] text-gray-600 font-mono uppercase tracking-widest">
        Line A — Columbus IN Engine Assembly
      </div>

      {/* Row 1: STN-01 to STN-06 */}
      <div className="grid grid-cols-6 gap-2 items-stretch">
        {row1.map(stn => (
          <StationCard key={stn.id} station={stn} />
        ))}
      </div>

      {/* Flow arrows row 1 */}
      <div className="flex items-center px-2 gap-1">
        {row1.map((_, i) => (
          <div key={i} className="flex-1 flex items-center">
            <div className="flex-1 h-px bg-gradient-to-r from-gray-700 to-gray-600" />
            {i < row1.length - 1 && <ArrowRight size={10} className="text-gray-600 flex-shrink-0" />}
          </div>
        ))}
        <ArrowRight size={10} className="text-gray-600 flex-shrink-0 rotate-90" />
      </div>

      {/* Row 2: STN-07 to STN-12 (reversed for snake layout) */}
      <div className="grid grid-cols-6 gap-2 items-stretch">
        {row2.map(stn => (
          <StationCard key={stn.id} station={stn} />
        ))}
      </div>

      {/* Flow arrows row 2 */}
      <div className="flex items-center px-2 gap-1">
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600 to-gray-700" />
        <ArrowRight size={10} className="text-gray-600" />
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600 to-gray-700" />
        <ArrowRight size={10} className="text-gray-600" />
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600 to-gray-700" />
        <ArrowRight size={10} className="text-gray-600" />
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600 to-gray-700" />
        <ArrowRight size={10} className="text-gray-600" />
        <div className="flex-1 h-px bg-gradient-to-r from-gray-600 to-gray-700" />
        <div className="flex items-center gap-1 text-[9px] font-mono text-teal-400 bg-teal-500/10 border border-teal-500/30 rounded px-2 py-0.5 flex-shrink-0">
          <span>▶ SHIP</span>
        </div>
      </div>
    </div>
  )
}
