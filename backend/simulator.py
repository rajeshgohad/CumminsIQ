import random
import time
from copy import deepcopy
from config import BU_BASELINES, ALERT_TEMPLATES, STATUS_THRESHOLDS

_alert_id_counter = 1000


def _new_alert_id():
    global _alert_id_counter
    _alert_id_counter += 1
    return _alert_id_counter


def _fluctuate(value: float, pct: float = 0.02, min_val: float = 0, max_val: float = 100) -> float:
    delta = value * pct * random.uniform(-1, 1)
    return round(max(min_val, min(max_val, value + delta)), 1)


def _compute_status(bu_key: str, health: float) -> str:
    t = STATUS_THRESHOLDS[bu_key]
    if health <= t["critical"]:
        return "critical"
    if health <= t["warning"]:
        return "warning"
    return "normal"


class SimulationEngine:
    def __init__(self):
        self.state = deepcopy(BU_BASELINES)
        self.alerts = self._seed_alerts()
        self.history = {bu: [] for bu in self.state}

    def _seed_alerts(self):
        alerts = []
        ts = int(time.time())
        for bu, templates in ALERT_TEMPLATES.items():
            for i, t in enumerate(templates[:self.state[bu]["alert_count"]]):
                alerts.append({
                    "id": _new_alert_id(),
                    "bu": bu,
                    "bu_name": self.state[bu]["name"],
                    "severity": t["severity"],
                    "message": t["message"],
                    "asset": t["asset"],
                    "timestamp": ts - (i * 420),
                })
        alerts.sort(key=lambda x: x["timestamp"], reverse=True)
        return alerts

    def tick(self):
        ts = int(time.time())

        for bu_key, data in self.state.items():
            if bu_key == "engine":
                data["oee"] = _fluctuate(data["oee"], 0.015, 60, 95)
                data["production_per_hour"] = round(_fluctuate(data["production_per_hour"], 0.02, 30, 60))
                data["production_today"] += random.randint(0, 2)
                data["equipment_health"] = _fluctuate(data["equipment_health"], 0.01, 40, 100)
                data["downtime_today"] = round(_fluctuate(data["downtime_today"], 0.03, 0, 14), 1)
                data["primary_metric"] = data["oee"]

            elif bu_key == "powgen":
                data["availability"] = _fluctuate(data["availability"], 0.005, 80, 99.9)
                data["equipment_health"] = _fluctuate(data["equipment_health"], 0.008, 50, 100)
                data["sla_risk_sites"] = max(0, data["sla_risk_sites"] + random.choice([-1, 0, 0, 1]))
                data["primary_metric"] = data["availability"]

            elif bu_key == "filtration":
                data["production_per_hour"] = round(_fluctuate(data["production_per_hour"], 0.02, 8000, 15000))
                data["scrap_rate"] = _fluctuate(data["scrap_rate"], 0.03, 1.5, 8.0)
                data["forecast_accuracy"] = _fluctuate(data["forecast_accuracy"], 0.01, 55, 90)
                data["equipment_health"] = _fluctuate(data["equipment_health"], 0.01, 50, 100)
                data["primary_metric"] = data["forecast_accuracy"]

            elif bu_key == "component":
                data["turbo_health"] = _fluctuate(data["turbo_health"], 0.01, 50, 100)
                data["ecm_outdated_pct"] = _fluctuate(data["ecm_outdated_pct"], 0.02, 10, 40)
                data["equipment_health"] = _fluctuate(data["equipment_health"], 0.015, 40, 100)
                data["primary_metric"] = data["turbo_health"]

            data["status"] = _compute_status(bu_key, data["equipment_health"])

            # Track history for sparkline (keep last 12 ticks)
            self.history[bu_key].append(round(data["primary_metric"], 1))
            if len(self.history[bu_key]) > 12:
                self.history[bu_key].pop(0)

            # Randomly generate a new alert (~6% chance per BU per tick)
            if random.random() < 0.06:
                templates = ALERT_TEMPLATES[bu_key]
                t = random.choice(templates)
                new_alert = {
                    "id": _new_alert_id(),
                    "bu": bu_key,
                    "bu_name": data["name"],
                    "severity": t["severity"],
                    "message": t["message"],
                    "asset": t["asset"],
                    "timestamp": ts,
                }
                self.alerts.insert(0, new_alert)
                data["alert_count"] = min(data["alert_count"] + 1, 15)

            # Randomly resolve an alert (~4% chance)
            if random.random() < 0.04 and data["alert_count"] > 0:
                self.alerts = [a for a in self.alerts if a["bu"] != bu_key][:]
                data["alert_count"] = max(0, data["alert_count"] - 1)

        # Keep alert list bounded to last 50
        self.alerts = self.alerts[:50]

    def get_snapshot(self) -> dict:
        total_alerts = sum(d["alert_count"] for d in self.state.values())
        weighted_oee = (
            self.state["engine"]["oee"] * 0.45
            + self.state["powgen"]["availability"] * 0.25
            + self.state["filtration"]["forecast_accuracy"] * 0.15
            + self.state["component"]["turbo_health"] * 0.15
        )
        total_downtime = self.state["engine"]["downtime_today"]
        plants_online = 12 - (1 if self.state["engine"]["status"] == "critical" else 0)

        return {
            "timestamp": int(time.time()),
            "summary": {
                "total_alerts": total_alerts,
                "overall_score": round(weighted_oee, 1),
                "total_downtime": total_downtime,
                "plants_online": plants_online,
            },
            "bus": {
                bu_key: {**data, "history": self.history[bu_key]}
                for bu_key, data in self.state.items()
            },
            "alerts": self.alerts[:20],
        }
