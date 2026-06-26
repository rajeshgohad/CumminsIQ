import random
import time
from copy import deepcopy
from assembly_data import STATIONS, OPERATORS, CURRENT_SHIFT, TARGET_PER_HOUR
from agents import AgentOrchestrator
import database as db

def _drift_mr(value: float, pct: float, lo: float, hi: float, center: float) -> float:
    """Mean-reverting drift — small noise + gentle pull back toward center."""
    noise  = value * pct * random.uniform(-1, 1)
    revert = (center - value) * 0.06   # 6% pull toward normal per tick
    return round(max(lo, min(hi, value + noise + revert)), 2)

def _status(actual: int, target: int, temp: float, vib: float, tool: float) -> str:
    over = actual / target
    if over > 1.22 or temp > 91 or vib > 0.82 or tool < 8:
        return "critical"
    if over > 1.12 or temp > 87 or vib > 0.68 or tool < 18:
        return "warning"
    return "running"

class AssemblySimulator:
    def __init__(self):
        self._orchestrator = AgentOrchestrator()
        self._parts_today = 376
        self._tick_count = 0
        self._last_saved_event_id = 0
        self._save_every = 3   # write station readings every Nth tick

        shift_ops = OPERATORS.get(CURRENT_SHIFT, OPERATORS["B"])
        # Pick 1-2 stations to be "stressed" — running warm but not yet critical
        stressed = set(random.sample(range(12), k=random.randint(1, 2)))

        self._stations: list[dict] = []
        for i, stn in enumerate(STATIONS):
            tgt = stn["target_ct"]
            degraded = i in stressed
            temp_n  = round(random.uniform(80, 85) if degraded else random.uniform(62, 74), 1)
            vib_n   = round(random.uniform(0.52, 0.62) if degraded else random.uniform(0.18, 0.38), 3)
            tool_n  = random.randint(28, 42) if degraded else random.randint(55, 90)
            self._stations.append({
                "id": stn["id"],
                "code": stn["code"],
                "name": stn["name"],
                "machine": stn["machine"],
                "target_ct": tgt,
                "actual_ct": tgt + (random.randint(8, 20) if degraded else random.randint(-8, 10)),
                "operator": shift_ops[i],
                "machine_temp": temp_n,
                "vibration": vib_n,
                "tool_life_pct": tool_n,
                "parts_count": random.randint(30, 55),
                "status": "running",
                "agent_active": False,
                # Normal operating centre — drift reverts toward this
                "_temp_center": temp_n,
                "_vib_center":  vib_n,
                "_ct_center":   float(tgt + (12 if degraded else 0)),
            })

    def tick(self):
        self._tick_count += 1
        ts = int(time.time())

        # Fluctuate station params — mean-reverting so most stations stay healthy
        for stn in self._stations:
            tgt = stn["target_ct"]
            stn["actual_ct"]     = int(_drift_mr(stn["actual_ct"],    0.03, int(tgt * 0.88), int(tgt * 1.30), stn["_ct_center"]))
            stn["machine_temp"]  = _drift_mr(stn["machine_temp"],     0.02, 58, 93, stn["_temp_center"])
            stn["vibration"]     = _drift_mr(stn["vibration"],        0.03, 0.12, 0.86, stn["_vib_center"])
            # Tool life decays; simulate a tool change when critically low
            stn["tool_life_pct"] -= random.uniform(0, 0.15)
            if stn["tool_life_pct"] < 12:
                stn["tool_life_pct"] = random.uniform(78, 95)   # new tool installed
            stn["parts_count"]  += random.randint(0, 2)
            stn["status"]        = _status(stn["actual_ct"], tgt,
                                           stn["machine_temp"], stn["vibration"],
                                           stn["tool_life_pct"])

        # Run agent orchestration
        self._orchestrator.tick(self._stations)
        agent_snap = self._orchestrator.get_snapshot()

        # Mark stations being watched by agents
        watched = {v["station"] for v in agent_snap["agents"].values() if v["station"]}
        for stn in self._stations:
            stn["agent_active"] = stn["code"] in watched

        # OEE proxy
        ok = sum(1 for s in self._stations if s["actual_ct"] <= s["target_ct"] * 1.10)
        oee = round((ok / len(self._stations)) * 100 * random.uniform(0.97, 1.02), 1)

        self._parts_today += random.randint(0, 1)
        prod_hr = random.randint(44, TARGET_PER_HOUR + 2)

        bottleneck = max(self._stations, key=lambda s: s["actual_ct"] / s["target_ct"])

        # ── Persist to SQLite ────────────────────────────────────────────────
        try:
            # Agent events & work orders — every tick (low volume)
            self._last_saved_event_id = db.save_agent_events(
                self._orchestrator.activity_log, self._last_saved_event_id
            )
            # Station readings & line metrics — every Nth tick
            if self._tick_count % self._save_every == 0:
                db.save_station_readings(self._stations, ts)
                db.save_line_metric(ts, oee, prod_hr, self._parts_today,
                                    CURRENT_SHIFT, bottleneck["code"])
            # Prune once an hour
            if self._tick_count % 1200 == 0:
                db.prune_old_data()
        except Exception as e:
            print(f"[DB] write error: {e}")

        return {
            "timestamp": ts,
            "line": {
                "oee": oee,
                "production_per_hour": prod_hr,
                "production_today": self._parts_today,
                "shift": CURRENT_SHIFT,
                "shift_start": "14:00",
                "shift_end": "22:00",
                "target_per_hour": TARGET_PER_HOUR,
                "bottleneck_station": bottleneck["code"],
            },
            "stations": deepcopy(self._stations),
            **agent_snap,
        }

    def get_snapshot(self) -> dict:
        return self.tick()
