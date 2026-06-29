import { useState } from 'react'
import { Loader2 } from 'lucide-react'
import Header, { type Page } from './components/Header'
import ExecutiveDashboard from './pages/ExecutiveDashboard'
import AssemblyLineDashboard from './pages/AssemblyLineDashboard'
import CycleTimeAgentPage from './pages/CycleTimeAgentPage'
import PredictiveMaintenancePage from './pages/PredictiveMaintenancePage'
import VisionInspectionPage from './pages/VisionInspectionPage'
import { useWebSocket } from './hooks/useWebSocket'

export default function App() {
  const [activePage, setActivePage] = useState<Page>('executive')
  const [apiKey, setApiKey] = useState('')
  const { data, connectionState } = useWebSocket()

  return (
    <div className="min-h-screen flex flex-col">
      <Header
        connectionState={connectionState}
        lastUpdated={data?.timestamp ?? null}
        activePage={activePage}
        onPageChange={setActivePage}
        apiKey={apiKey}
        onApiKeyChange={setApiKey}
      />

      {activePage === 'executive' && (
        !data ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-gray-500">
            <Loader2 size={36} className="animate-spin text-cummins-blue" />
            <div className="text-center">
              <p className="text-white font-medium">Connecting to AutomotiveIQ Platform</p>
              <p className="text-sm mt-1">Waiting for live data feed…</p>
            </div>
          </div>
        ) : (
          <ExecutiveDashboard data={data} />
        )
      )}

      {activePage === 'assembly'    && <AssemblyLineDashboard onPageChange={setActivePage} apiKey={apiKey} />}
      {activePage === 'cycle_time'  && <CycleTimeAgentPage apiKey={apiKey} />}
      {activePage === 'maintenance' && <PredictiveMaintenancePage apiKey={apiKey} />}
      {activePage === 'vision'      && <VisionInspectionPage apiKey={apiKey} />}
    </div>
  )
}
