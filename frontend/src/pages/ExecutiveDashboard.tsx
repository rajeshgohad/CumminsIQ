import { Cog, Zap, Filter, Wrench } from 'lucide-react'
import KPISummary from '../components/KPISummary'
import BUCard from '../components/BUCard'
import AlertFeed from '../components/AlertFeed'
import type { DashboardSnapshot } from '../types'

interface Props {
  data: DashboardSnapshot
}

export default function ExecutiveDashboard({ data }: Props) {
  const { bus, summary, alerts } = data

  return (
    <main className="p-5 flex flex-col gap-5 max-w-[1600px] mx-auto">

      {/* KPI Summary Row */}
      <KPISummary summary={summary} />

      {/* BU Cards — 2x2 grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-5">

        {/* Engine BU */}
        <BUCard
          title="Engine Business Unit"
          icon={<Cog size={18} />}
          location={bus.engine.location}
          status={bus.engine.status}
          primaryMetricLabel="OEE"
          primaryMetric={bus.engine.oee}
          alertCount={bus.engine.alert_count}
          history={bus.engine.history}
          borderColor="border-t-blue-500"
          metrics={[
            {
              label: 'Production / Hour',
              value: `${bus.engine.production_per_hour} engines`,
              highlight: bus.engine.production_per_hour >= 45 ? 'good' : 'warn',
            },
            {
              label: 'Engines Today',
              value: bus.engine.production_today,
              highlight: 'neutral',
            },
            {
              label: 'Equipment Health',
              value: `${bus.engine.equipment_health.toFixed(1)} / 100`,
              highlight: bus.engine.equipment_health >= 80 ? 'good' : bus.engine.equipment_health >= 65 ? 'warn' : 'bad',
            },
            {
              label: 'Downtime Today',
              value: `${bus.engine.downtime_today}h`,
              highlight: bus.engine.downtime_today < 1 ? 'good' : bus.engine.downtime_today < 3 ? 'warn' : 'bad',
            },
          ]}
        />

        {/* Power Generation BU */}
        <BUCard
          title="Power Generation"
          icon={<Zap size={18} />}
          location={bus.powgen.location}
          status={bus.powgen.status}
          primaryMetricLabel="Availability"
          primaryMetric={bus.powgen.availability}
          alertCount={bus.powgen.alert_count}
          history={bus.powgen.history}
          borderColor="border-t-purple-500"
          metrics={[
            {
              label: 'Sites Monitored',
              value: bus.powgen.sites_monitored.toLocaleString(),
              highlight: 'neutral',
            },
            {
              label: 'SLA Risk Sites',
              value: bus.powgen.sla_risk_sites,
              highlight: bus.powgen.sla_risk_sites === 0 ? 'good' : bus.powgen.sla_risk_sites <= 3 ? 'warn' : 'bad',
            },
            {
              label: 'Equipment Health',
              value: `${bus.powgen.equipment_health.toFixed(1)} / 100`,
              highlight: bus.powgen.equipment_health >= 85 ? 'good' : bus.powgen.equipment_health >= 70 ? 'warn' : 'bad',
            },
            {
              label: 'Coverage',
              value: '42% monitored',
              highlight: 'warn',
            },
          ]}
        />

        {/* Filtration BU */}
        <BUCard
          title="Filtration"
          icon={<Filter size={18} />}
          location={bus.filtration.location}
          status={bus.filtration.status}
          primaryMetricLabel="Forecast Acc."
          primaryMetric={bus.filtration.forecast_accuracy}
          alertCount={bus.filtration.alert_count}
          history={bus.filtration.history}
          borderColor="border-t-teal-500"
          metrics={[
            {
              label: 'Production / Hour',
              value: `${bus.filtration.production_per_hour.toLocaleString()} filters`,
              highlight: 'neutral',
            },
            {
              label: 'Scrap Rate',
              value: `${bus.filtration.scrap_rate.toFixed(1)}%`,
              highlight: bus.filtration.scrap_rate < 2.5 ? 'good' : bus.filtration.scrap_rate < 4.5 ? 'warn' : 'bad',
            },
            {
              label: 'Equipment Health',
              value: `${bus.filtration.equipment_health.toFixed(1)} / 100`,
              highlight: bus.filtration.equipment_health >= 80 ? 'good' : bus.filtration.equipment_health >= 65 ? 'warn' : 'bad',
            },
            {
              label: 'Benchmark Scrap',
              value: '1.8% target',
              highlight: 'warn',
            },
          ]}
        />

        {/* Component BU */}
        <BUCard
          title="Component"
          icon={<Wrench size={18} />}
          location={bus.component.location}
          status={bus.component.status}
          primaryMetricLabel="Turbo Health"
          primaryMetric={bus.component.turbo_health}
          alertCount={bus.component.alert_count}
          history={bus.component.history}
          borderColor="border-t-orange-500"
          metrics={[
            {
              label: 'Turbo Health Score',
              value: `${bus.component.turbo_health.toFixed(1)} / 100`,
              highlight: bus.component.turbo_health >= 85 ? 'good' : bus.component.turbo_health >= 70 ? 'warn' : 'bad',
            },
            {
              label: 'ECM Firmware Outdated',
              value: `${bus.component.ecm_outdated_pct.toFixed(1)}%`,
              highlight: bus.component.ecm_outdated_pct < 5 ? 'good' : bus.component.ecm_outdated_pct < 20 ? 'warn' : 'bad',
            },
            {
              label: 'Equipment Health',
              value: `${bus.component.equipment_health.toFixed(1)} / 100`,
              highlight: bus.component.equipment_health >= 80 ? 'good' : bus.component.equipment_health >= 65 ? 'warn' : 'bad',
            },
            {
              label: 'Turbo Failure Rate',
              value: '0.8% (target 0.3%)',
              highlight: 'bad',
            },
          ]}
        />
      </div>

      {/* Alert Feed */}
      <AlertFeed alerts={alerts} />

    </main>
  )
}
