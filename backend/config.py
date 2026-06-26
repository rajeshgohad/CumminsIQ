TICK_INTERVAL = 3  # seconds between WebSocket broadcasts

BU_BASELINES = {
    "engine": {
        "name": "Engine Business Unit",
        "location": "Columbus, IN",
        "oee": 78.4,
        "production_per_hour": 47,
        "production_today": 376,
        "equipment_health": 76,
        "downtime_today": 2.1,
        "alert_count": 3,
        "status": "warning",
        "primary_metric_label": "OEE",
        "primary_metric": 78.4,
    },
    "powgen": {
        "name": "Power Generation",
        "location": "Global — 847 Sites",
        "availability": 94.2,
        "sites_monitored": 847,
        "sla_risk_sites": 3,
        "equipment_health": 88,
        "alert_count": 5,
        "status": "normal",
        "primary_metric_label": "Availability",
        "primary_metric": 94.2,
    },
    "filtration": {
        "name": "Filtration",
        "location": "Lake Mills, WI",
        "production_per_hour": 12400,
        "scrap_rate": 4.1,
        "forecast_accuracy": 73.2,
        "equipment_health": 82,
        "alert_count": 2,
        "status": "normal",
        "primary_metric_label": "Forecast Acc.",
        "primary_metric": 73.2,
    },
    "component": {
        "name": "Component",
        "location": "Charleston, SC",
        "turbo_health": 82,
        "ecm_outdated_pct": 23,
        "equipment_health": 74,
        "alert_count": 6,
        "status": "critical",
        "primary_metric_label": "Turbo Health",
        "primary_metric": 82.0,
    },
}

ALERT_TEMPLATES = {
    "engine": [
        {"severity": "critical", "message": "Assembly conveyor bearing temperature critical — Station 7", "asset": "CONV-07"},
        {"severity": "warning", "message": "Station 12 cycle time exceeded threshold by 18%", "asset": "STN-12"},
        {"severity": "warning", "message": "Tool life at 91% — torque wrench TW-04 replacement due", "asset": "TW-04"},
        {"severity": "info",    "message": "Shift B productivity 4% below target — rebalancing suggested", "asset": "LINE-A"},
        {"severity": "warning", "message": "Spare part ENG-4521 stock below reorder point — 3 units left", "asset": "PARTS"},
    ],
    "powgen": [
        {"severity": "critical", "message": "Generator G-447 at AZURE-DC-WEST — fuel pressure anomaly", "asset": "G-447"},
        {"severity": "warning",  "message": "Site CAT-DATA-03 SLA at risk — generator health 62/100", "asset": "G-821"},
        {"severity": "warning",  "message": "Load bank test overdue at 3 sites — past 90-day window", "asset": "LBT"},
        {"severity": "info",     "message": "Site HOSP-CHI-01 fuel resupply required within 8 days", "asset": "G-334"},
        {"severity": "warning",  "message": "Generator G-112 telemetry offline — 47 minutes", "asset": "G-112"},
    ],
    "filtration": [
        {"severity": "warning", "message": "Lake Mills Line 3 scrap rate 5.2% — above 5% threshold", "asset": "LINE-3"},
        {"severity": "warning", "message": "SKU FG-FS1040 demand deviation +34% — reforecast needed", "asset": "FS1040"},
        {"severity": "info",    "message": "NanoForce filter NF-7821 service interval approaching — 47 units", "asset": "NF-7821"},
        {"severity": "warning", "message": "Lube filter LF-9000 inventory at 12-day supply only", "asset": "LF-9000"},
    ],
    "component": [
        {"severity": "critical", "message": "Turbocharger TRB-44821 boost pressure anomaly — VGT failure risk", "asset": "TRB-44821"},
        {"severity": "critical", "message": "DPF regeneration failure — Unit ECM-5529 requires intervention", "asset": "ECM-5529"},
        {"severity": "warning",  "message": "ECM firmware outdated — 187 field units below v4.2.1 minimum", "asset": "ECM-FW"},
        {"severity": "warning",  "message": "Holset HX55W shaft speed variance — Unit TRB-44901", "asset": "TRB-44901"},
        {"severity": "info",     "message": "DEF consumption +12% above baseline — 23 units flagged", "asset": "AFT-DEF"},
    ],
}

STATUS_THRESHOLDS = {
    "engine":     {"critical": 65, "warning": 75},
    "powgen":     {"critical": 85, "warning": 92},
    "filtration": {"critical": 60, "warning": 70},
    "component":  {"critical": 65, "warning": 75},
}
