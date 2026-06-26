export type Severity = 'critical' | 'warning' | 'info' | 'normal'
export type Status = 'critical' | 'warning' | 'normal'

export interface Alert {
  id: number
  bu: string
  bu_name: string
  severity: Severity
  message: string
  asset: string
  timestamp: number
}

export interface EngineBU {
  name: string
  location: string
  oee: number
  production_per_hour: number
  production_today: number
  equipment_health: number
  downtime_today: number
  alert_count: number
  status: Status
  primary_metric_label: string
  primary_metric: number
  history: number[]
}

export interface PowerGenBU {
  name: string
  location: string
  availability: number
  sites_monitored: number
  sla_risk_sites: number
  equipment_health: number
  alert_count: number
  status: Status
  primary_metric_label: string
  primary_metric: number
  history: number[]
}

export interface FiltrationBU {
  name: string
  location: string
  production_per_hour: number
  scrap_rate: number
  forecast_accuracy: number
  equipment_health: number
  alert_count: number
  status: Status
  primary_metric_label: string
  primary_metric: number
  history: number[]
}

export interface ComponentBU {
  name: string
  location: string
  turbo_health: number
  ecm_outdated_pct: number
  equipment_health: number
  alert_count: number
  status: Status
  primary_metric_label: string
  primary_metric: number
  history: number[]
}

export interface Summary {
  total_alerts: number
  overall_score: number
  total_downtime: number
  plants_online: number
}

export interface DashboardSnapshot {
  timestamp: number
  summary: Summary
  bus: {
    engine: EngineBU
    powgen: PowerGenBU
    filtration: FiltrationBU
    component: ComponentBU
  }
  alerts: Alert[]
}
