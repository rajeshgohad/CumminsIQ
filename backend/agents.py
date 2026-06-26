from __future__ import annotations
import random
import time
from copy import deepcopy

_log_id = 9000

def _next_log_id():
    global _log_id
    _log_id += 1
    return _log_id

def _wo_number():
    return f"WO-{random.randint(2800, 2999)}"

# ── Agent state machine ─────────────────────────────────────────────────────
AGENT_DEFS = {
    "supervisor": {
        "name": "Supervisor Agent",
        "role": "Orchestrates all AI agents — dispatches specialists on anomaly detection",
        "icon": "cpu",
        "color": "blue",
    },
    "cycle_time": {
        "name": "Cycle Time Monitor",
        "role": "Tracks takt time adherence per station — identifies bottlenecks",
        "icon": "timer",
        "color": "purple",
    },
    "equipment": {
        "name": "Equipment Health Agent",
        "role": "Monitors machine parameters — temp, vibration, tool life",
        "icon": "wrench",
        "color": "amber",
    },
    "quality": {
        "name": "Quality AI Agent",
        "role": "AI visual inspection — detects defects, presence/absence of features",
        "icon": "eye",
        "color": "teal",
    },
    "scheduling": {
        "name": "Scheduling Optimizer",
        "role": "Analyzes production sequence — suggests reordering for throughput",
        "icon": "calendar",
        "color": "indigo",
    },
    "maintenance": {
        "name": "Maintenance Agent",
        "role": "Creates work orders in Maximo — schedules preventive maintenance",
        "icon": "clipboard",
        "color": "orange",
    },
}

# ── Message templates ────────────────────────────────────────────────────────
def _classify_anomaly(station) -> tuple[str, str]:
    """Returns (anomaly_description, specialist_agent_name)."""
    if station["machine_temp"] > 87:
        return (f"bearing temp {station['machine_temp']:.1f}°C (threshold 87°C)", "Equipment Health Agent")
    if station["vibration"] > 0.68:
        return (f"vibration {station['vibration']:.2f}g RMS (baseline 0.40g)", "Equipment Health Agent")
    if station["tool_life_pct"] < 18:
        return (f"tool life {station['tool_life_pct']:.0f}% — change due", "Equipment Health Agent")
    over = int((station["actual_ct"] / station["target_ct"] - 1) * 100)
    if over > 12:
        return (f"cycle time +{over}% over takt ({station['actual_ct']}s vs {station['target_ct']}s)", "Cycle Time Monitor")
    return ("parameter deviation detected", "Equipment Health Agent")

def _supervisor_observe_msgs(stations):
    critical = [s for s in stations if s["status"] == "critical"]
    warnings  = [s for s in stations if s["status"] == "warning"]
    n_issues  = len(critical) + len(warnings)
    if n_issues == 0:
        return "All 12 stations nominal — OEE tracking at target. Continuous monitoring active."
    primary = (critical + warnings)[0]
    anomaly, specialist = _classify_anomaly(primary)
    sev = "CRITICAL" if primary in critical else "WARNING"
    others = n_issues - 1
    tail = f" (+{others} more station{'s' if others > 1 else ''} flagged)" if others else ""
    return f"{sev} at {primary['code']}: {anomaly} — dispatching {specialist}{tail}."

def _ct_detect_msg(station):
    pct = round((station["actual_ct"] / station["target_ct"] - 1) * 100, 1)
    return (f"{station['code']} cycle time {station['actual_ct']}s vs {station['target_ct']}s target "
            f"(+{pct}%) — takt violation risk, downstream buffer depleting.")

def _equip_detect_msg(station):
    if station["machine_temp"] > 87:
        return (f"{station['code']} bearing temperature {station['machine_temp']:.1f}°C — "
                f"threshold 87°C. Consecutive readings trending up. Failure risk: HIGH.")
    if station["vibration"] > 0.75:
        return (f"{station['code']} vibration {station['vibration']:.2f}g RMS — "
                f"normal baseline 0.4g. Possible bearing wear or imbalance.")
    return (f"{station['code']} tool life at {station['tool_life_pct']}% — "
            f"replacement recommended before next shift.")

def _quality_detect_msg(station):
    issues = [
        f"ECM pin bend detected on unit #{random.randint(4800,4899)} at {station['code']}",
        f"Surface burr anomaly — fuel line debris risk at {station['code']}",
        f"Feature absence: drilling before tapping not confirmed at {station['code']}",
        f"Masking incomplete before paint — {station['code']} — downstream quality risk",
        f"Torque value out of spec: {random.uniform(185,210):.1f} Nm vs 195 Nm target at {station['code']}",
    ]
    return random.choice(issues)

def _maintenance_act_msg(station, wo):
    return (f"Work Order {wo} created in Maximo — {station['code']} bearing inspection. "
            f"Priority: HIGH. Assigned to Shift B maintenance crew. ETA: 45 min.")

def _scheduling_act_msg(station):
    gain = random.randint(3, 7)
    return (f"Batch resequenced: variant C→B→A — bottleneck at {station['code']} mitigated. "
            f"Projected throughput gain: +{gain} engines/shift.")

# ── AgentOrchestrator ────────────────────────────────────────────────────────
class AgentOrchestrator:
    def __init__(self):
        self.activity_log: list[dict] = []
        self._agent_states: dict[str, dict] = {
            k: {"status": "idle", "current_action": "Initializing…", "active": False,
                "station": None, "_ticks_in_state": 0, "_pending": None}
            for k in AGENT_DEFS
        }
        self._cooldowns: dict[str, int] = {k: 0 for k in AGENT_DEFS}

    def _log(self, from_agent: str, to_agent: str | None, msg_type: str,
             message: str, severity: str = "info", station: str | None = None):
        self.activity_log.insert(0, {
            "id": _next_log_id(),
            "timestamp": int(time.time()),
            "from_agent": from_agent,
            "to_agent": to_agent,
            "type": msg_type,          # observe|detect|dispatch|analyze|act|escalate|alert
            "message": message,
            "severity": severity,       # info|warning|critical|success
            "station": station,
        })
        if len(self.activity_log) > 60:
            self.activity_log = self.activity_log[:60]

    def _set_agent(self, agent_id: str, status: str, action: str,
                   active: bool = True, station: str | None = None):
        s = self._agent_states[agent_id]
        s["status"] = status
        s["current_action"] = action
        s["active"] = active
        s["station"] = station
        s["_ticks_in_state"] = 0

    def _decrement_cooldowns(self):
        for k in self._cooldowns:
            if self._cooldowns[k] > 0:
                self._cooldowns[k] -= 1

    def tick(self, stations: list[dict]):
        self._decrement_cooldowns()
        ts = int(time.time())

        # ── Supervisor always runs ──────────────────────────────────────────
        critical_stns = [s for s in stations if s["status"] == "critical"]
        warning_stns  = [s for s in stations if s["status"] == "warning"]
        all_bad = critical_stns + warning_stns

        sup_msg = _supervisor_observe_msgs(stations)
        self._set_agent("supervisor", "orchestrating" if all_bad else "observing",
                        sup_msg, active=True, station=None)

        if all_bad and random.random() < 0.4:   # log only 40% of observe ticks to reduce noise
            self._log("supervisor", None, "observe", sup_msg,
                      "warning" if not critical_stns else "critical")

        # ── Dispatch equipment agent for temp/vibration/tool issues ─────────
        equip_targets = [s for s in stations
                         if s["machine_temp"] > 86 or s["vibration"] > 0.72 or s["tool_life_pct"] < 15]
        if equip_targets and self._cooldowns["equipment"] == 0:
            target = equip_targets[0]
            detect_msg = _equip_detect_msg(target)
            anomaly, _ = _classify_anomaly(target)
            dispatch_msg = (f"Supervisor → Equipment Health Agent: {target['code']} flagged — {anomaly}")
            self._log("supervisor", "equipment", "dispatch", dispatch_msg,
                      "critical" if target["machine_temp"] > 88 else "warning", target["code"])
            self._set_agent("equipment", "detecting", detect_msg, True, target["code"])
            self._log("equipment", None, "detect", detect_msg,
                      "critical" if target["machine_temp"] > 88 else "warning", target["code"])

            # Equipment → Maintenance escalation
            if target["machine_temp"] > 87 or target["vibration"] > 0.78:
                wo = _wo_number()
                esc_msg = f"Escalating to Maintenance Agent — predictive failure risk at {target['code']}"
                self._log("equipment", "maintenance", "escalate", esc_msg, "critical", target["code"])
                act_msg = _maintenance_act_msg(target, wo)
                self._set_agent("maintenance", "acting", act_msg, True, target["code"])
                self._log("maintenance", None, "act", act_msg, "success", target["code"])
                self._cooldowns["maintenance"] = 8

            self._cooldowns["equipment"] = 6

        elif self._cooldowns["equipment"] == 0:
            self._set_agent("equipment", "observing",
                            "Monitoring machine parameters across all 12 stations", True, None)

        # ── Dispatch cycle time agent for takt violations ────────────────────
        ct_targets = [s for s in stations if s["actual_ct"] > s["target_ct"] * 1.12]
        if ct_targets and self._cooldowns["cycle_time"] == 0:
            target = ct_targets[0]
            detect_msg = _ct_detect_msg(target)
            pct_over = int((target["actual_ct"] / target["target_ct"] - 1) * 100)
            self._log("supervisor", "cycle_time", "dispatch",
                      f"Supervisor → Cycle Time Monitor: {target['code']} cycle time +{pct_over}% over takt ({target['actual_ct']}s vs {target['target_ct']}s target)",
                      "warning", target["code"])
            self._set_agent("cycle_time", "detecting", detect_msg, True, target["code"])
            self._log("cycle_time", None, "detect", detect_msg, "warning", target["code"])

            # Cycle time → Scheduling escalation
            if len(ct_targets) >= 2 and self._cooldowns["scheduling"] == 0:
                esc_msg = (f"Multiple takt violations ({len(ct_targets)} stations) — "
                           "escalating to Scheduling Optimizer for batch resequencing")
                self._log("cycle_time", "scheduling", "escalate", esc_msg, "warning")
                act_msg = _scheduling_act_msg(target)
                self._set_agent("scheduling", "acting", act_msg, True, target["code"])
                self._log("scheduling", None, "act", act_msg, "success", target["code"])
                self._cooldowns["scheduling"] = 10

            self._cooldowns["cycle_time"] = 5

        elif self._cooldowns["cycle_time"] == 0:
            self._set_agent("cycle_time", "observing",
                            f"Monitoring takt time — tracking {len(stations)} stations", True, None)

        # ── Quality agent — random inspection with occasional defect ─────────
        if self._cooldowns["quality"] == 0:
            # 20% chance of triggering a quality scan with a finding
            if random.random() < 0.20:
                target = random.choice(stations)
                detect_msg = _quality_detect_msg(target)
                self._set_agent("quality", "detecting", detect_msg, True, target["code"])
                self._log("quality", None, "detect", detect_msg, "critical", target["code"])
                esc_msg = f"Line hold recommended at {target['code']} — defect confirmed by AI vision"
                self._log("quality", "supervisor", "alert", esc_msg, "critical", target["code"])
                sup_resp = (f"Line hold initiated at {target['code']} — "
                            f"unit routed to rework. Quality Engineer notified.")
                self._log("supervisor", None, "act", sup_resp, "warning", target["code"])
                self._cooldowns["quality"] = 8
            else:
                scan_stn = random.choice(stations)
                self._set_agent("quality", "observing",
                                f"AI visual scan active — {scan_stn['code']} output monitoring",
                                True, scan_stn["code"])
                if random.random() < 0.25:
                    self._log("quality", None, "observe",
                              f"Visual inspection clear — {scan_stn['code']} output nominal",
                              "info", scan_stn["code"])
                self._cooldowns["quality"] = 3

        # ── Maintenance agent — show open WOs when idle ─────────────────────
        maint = self._agent_states["maintenance"]
        if maint["status"] == "acting" and maint["_ticks_in_state"] > 3:
            open_wos = random.randint(2, 5)
            self._set_agent("maintenance", "observing",
                            f"Monitoring {open_wos} open work orders — next PM: STN-04 in 2h",
                            True, None)

        # Increment tick counters
        for s in self._agent_states.values():
            s["_ticks_in_state"] = s.get("_ticks_in_state", 0) + 1

    def get_snapshot(self) -> dict:
        pub = {}
        for k, v in self._agent_states.items():
            pub[k] = {
                "id": k,
                **AGENT_DEFS[k],
                "status": v["status"],
                "current_action": v["current_action"],
                "active": v["active"],
                "station": v["station"],
            }
        return {
            "agents": pub,
            "activity_log": self.activity_log[:30],
        }
