import { Wifi, WifiOff, Loader2, RefreshCw, LayoutDashboard, Factory, Timer, Wrench, ScanEye } from 'lucide-react'
import { useEffect, useState } from 'react'
import ApiKeyButton from './ApiKeyButton'

export type Page = 'executive' | 'assembly' | 'cycle_time' | 'maintenance' | 'vision'

interface HeaderProps {
  connectionState: 'connecting' | 'connected' | 'disconnected'
  lastUpdated: number | null
  activePage: Page
  onPageChange: (p: Page) => void
  apiKey: string
  onApiKeyChange: (k: string) => void
}

const PAGES: { id: Page; label: string; icon: React.ElementType }[] = [
  { id: 'executive',   label: 'Executive',          icon: LayoutDashboard },
  { id: 'assembly',    label: 'Assembly Line',       icon: Factory },
  { id: 'cycle_time',  label: 'Cycle Time AI',       icon: Timer },
  { id: 'maintenance', label: 'Predictive Maint.',   icon: Wrench },
  { id: 'vision',      label: 'Vision Inspection',   icon: ScanEye },
]

export default function Header({ connectionState, lastUpdated, activePage, onPageChange, apiKey, onApiKeyChange }: HeaderProps) {
  const [now, setNow] = useState(new Date())

  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000)
    return () => clearInterval(t)
  }, [])

  const secsAgo = lastUpdated ? Math.floor((Date.now() / 1000) - lastUpdated) : null

  return (
    <header className="bg-[#0D1220] border-b border-gray-800 sticky top-0 z-50">
      <div className="flex items-center justify-between px-6 py-3">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-lg bg-cummins-blue flex items-center justify-center font-bold text-white text-lg select-none">
            C
          </div>
          <div>
            <p className="text-white font-semibold leading-none tracking-wide text-sm">CumminsIQ</p>
            <p className="text-gray-500 text-xs mt-0.5">Predictive Operations Platform</p>
          </div>
        </div>

        {/* Nav tabs */}
        <nav className="flex items-center gap-1 bg-black/30 rounded-xl p-1 border border-gray-800">
          {PAGES.map(p => {
            const Icon = p.icon
            const active = activePage === p.id
            return (
              <button
                key={p.id}
                onClick={() => onPageChange(p.id)}
                className={`flex items-center gap-2 px-4 py-1.5 rounded-lg text-xs font-medium transition-all duration-200 ${
                  active
                    ? 'bg-cummins-blue text-white shadow-lg shadow-cummins-blue/20'
                    : 'text-gray-500 hover:text-gray-300 hover:bg-white/5'
                }`}
              >
                <Icon size={12} />
                {p.label}
              </button>
            )
          })}
        </nav>

        {/* Clock + connection */}
        <div className="flex items-center gap-5">
          <div className="text-right hidden sm:block">
            <p className="text-white text-sm font-mono">
              {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
            </p>
            <p className="text-gray-500 text-xs">
              {now.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
            </p>
          </div>

          <ApiKeyButton apiKey={apiKey} onChange={onApiKeyChange} />

          <div className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-xs font-medium ${
            connectionState === 'connected'
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : connectionState === 'connecting'
              ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              : 'bg-red-500/10 border-red-500/30 text-red-400'
          }`}>
            {connectionState === 'connected'    && <Wifi size={12} />}
            {connectionState === 'connecting'   && <Loader2 size={12} className="animate-spin" />}
            {connectionState === 'disconnected' && <WifiOff size={12} />}
            <span className="capitalize">{connectionState}</span>
            {connectionState === 'connected' && secsAgo !== null && (
              <span className="text-gray-500 flex items-center gap-1">
                · <RefreshCw size={10} /> {secsAgo}s ago
              </span>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
