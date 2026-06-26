export type StationStatus = 'running' | 'warning' | 'critical' | 'idle' | 'blocked'
export type AgentStatus = 'idle' | 'observing' | 'orchestrating' | 'detecting' | 'analyzing' | 'acting'
export type LogSeverity = 'info' | 'warning' | 'critical' | 'success'
export type LogType = 'observe' | 'detect' | 'dispatch' | 'analyze' | 'act' | 'escalate' | 'alert'

export interface Station {
  id: number
  code: string
  name: string
  machine: string
  target_ct: number
  actual_ct: number
  operator: string
  machine_temp: number
  vibration: number
  tool_life_pct: number
  parts_count: number
  status: StationStatus
  agent_active: boolean
}

export interface Agent {
  id: string
  name: string
  role: string
  icon: string
  color: string
  status: AgentStatus
  current_action: string
  active: boolean
  station: string | null
}

export interface ActivityLogEntry {
  id: number
  timestamp: number
  from_agent: string
  to_agent: string | null
  type: LogType
  message: string
  severity: LogSeverity
  station: string | null
}

export interface LineMetrics {
  oee: number
  production_per_hour: number
  production_today: number
  shift: string
  shift_start: string
  shift_end: string
  target_per_hour: number
  bottleneck_station: string
}

export interface AssemblySnapshot {
  timestamp: number
  line: LineMetrics
  stations: Station[]
  agents: Record<string, Agent>
  activity_log: ActivityLogEntry[]
}
