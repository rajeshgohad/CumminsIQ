from __future__ import annotations
import asyncio
import json
import time
from database import get_conn

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a predictive maintenance agent for the Automotive Columbus IN engine assembly plant.

ROLE: When a fault is detected on assembly equipment, schedule the optimal maintenance
intervention that prevents unplanned failure while minimising production disruption.

REASONING FRAMEWORK — follow these steps in order, showing your reasoning at each step:
1. Assess fault severity — call get_sensor_data, then get_fault_prognosis to estimate days to failure
2. Check production schedule — what jobs depend on this equipment and when are they due?
3. Check parts inventory — is the required part in stock?
4. If NOT in stock — check supplier lead time vs. time-to-failure; if lead time > TTF, escalate urgency
5. Check technician availability — who is available with the right certification?
6. Find the optimal repair window — satisfies all constraints (TTF, production jobs, technician shift)
7. Execute — create work order, book technician, reorder parts if needed
8. Monitor — set a checkpoint so we know immediately if the fault accelerates before the repair

Always explain your reasoning before calling a tool. After each tool result, explain what it means
for your decision. At the end, give a clear summary of everything you scheduled and why.
"""

# ── Tool definitions (Anthropic tool_use schema) ─────────────────────────────

TOOL_DEFINITIONS = [
    {
        "name": "get_sensor_data",
        "description": "Query the sensor historian for recent temperature, vibration, and current draw readings for an asset. Returns last 10 readings with trend summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string", "description": "Asset ID, e.g. STN-01"}
            },
            "required": ["asset_id"]
        }
    },
    {
        "name": "get_fault_prognosis",
        "description": "Run the ML prognostic model: given the asset's sensor trend, return estimated days-to-failure with a probability distribution and confidence interval.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string"},
                "fault_type": {"type": "string", "description": "e.g. bearing_wear, overheating, vibration_anomaly, tool_wear"}
            },
            "required": ["asset_id", "fault_type"]
        }
    },
    {
        "name": "get_production_schedule",
        "description": "Query MES/ERP: which production jobs run on this asset, when they are due, and their criticality.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string"}
            },
            "required": ["asset_id"]
        }
    },
    {
        "name": "check_parts_inventory",
        "description": "Query CMMS parts inventory: is the required part in stock and how many units are available.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_name": {"type": "string", "description": "Part name or part number, e.g. SKF-6205-2Z or SB-2204"}
            },
            "required": ["part_name"]
        }
    },
    {
        "name": "get_supplier_lead_time",
        "description": "Query procurement system: how many days for a supplier to deliver this part, and what is the unit cost.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_name": {"type": "string"}
            },
            "required": ["part_name"]
        }
    },
    {
        "name": "get_technician_availability",
        "description": "Query workforce management: which technicians are available and hold the required certification for this type of repair.",
        "input_schema": {
            "type": "object",
            "properties": {
                "required_cert": {"type": "string", "description": "Required certification, e.g. Mechanical, Electrical, Hydraulic, PLC"},
                "within_hours": {"type": "integer", "description": "Look for availability within the next N hours", "default": 48}
            },
            "required": ["required_cert"]
        }
    },
    {
        "name": "create_work_order",
        "description": "Write to CMMS: create a work order with asset, fault type, required parts, priority, and work description.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id": {"type": "string"},
                "fault_type": {"type": "string"},
                "priority": {"type": "string", "enum": ["CRITICAL", "HIGH", "MEDIUM", "LOW"]},
                "description": {"type": "string", "description": "Detailed maintenance procedure and context"},
                "part_required": {"type": "string", "description": "Part name or number required (optional)"}
            },
            "required": ["asset_id", "fault_type", "priority", "description"]
        }
    },
    {
        "name": "schedule_technician",
        "description": "Write to workforce management: book a technician for a specific repair window linked to a work order.",
        "input_schema": {
            "type": "object",
            "properties": {
                "technician_name": {"type": "string"},
                "wo_number":       {"type": "string", "description": "Work order number to link this booking to"},
                "start_offset_hours": {"type": "number", "description": "Hours from now when the work window starts"},
                "duration_hours":     {"type": "number", "description": "Estimated repair duration in hours"}
            },
            "required": ["technician_name", "wo_number", "start_offset_hours", "duration_hours"]
        }
    },
    {
        "name": "create_purchase_order",
        "description": "Write to procurement: reorder a part with quantity and supplier, stating the reason and urgency.",
        "input_schema": {
            "type": "object",
            "properties": {
                "part_name": {"type": "string"},
                "quantity":  {"type": "integer"},
                "reason":    {"type": "string", "description": "Business justification for the order"}
            },
            "required": ["part_name", "quantity", "reason"]
        }
    },
    {
        "name": "set_monitoring_checkpoint",
        "description": "Configure a real-time alert: if the named sensor parameter exceeds the threshold value before the repair window, immediately escalate to the named contact.",
        "input_schema": {
            "type": "object",
            "properties": {
                "asset_id":            {"type": "string"},
                "parameter":           {"type": "string", "description": "Sensor to watch: temperature, vibration, or current_draw"},
                "threshold":           {"type": "number", "description": "Alert threshold value"},
                "escalation_contact":  {"type": "string", "description": "Name or role to notify on breach"}
            },
            "required": ["asset_id", "parameter", "threshold", "escalation_contact"]
        }
    },
    {
        "name": "notify_human",
        "description": "Send a message to a specific person (by name or role) with full context and a recommended action, requiring their decision.",
        "input_schema": {
            "type": "object",
            "properties": {
                "recipient":           {"type": "string"},
                "message":             {"type": "string", "description": "Full context message"},
                "recommended_action":  {"type": "string"},
                "urgency":             {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
            },
            "required": ["recipient", "message", "recommended_action", "urgency"]
        }
    },
]

# ── DB init + seed ────────────────────────────────────────────────────────────

def init_pm_tables():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS pm_assets (
        asset_id          TEXT PRIMARY KEY,
        asset_name        TEXT,
        asset_type        TEXT,
        machine_model     TEXT,
        days_to_failure   REAL,
        last_prognosis_ts INTEGER
    );

    CREATE TABLE IF NOT EXISTS pm_sensor_history (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id     TEXT NOT NULL,
        ts           INTEGER NOT NULL,
        temperature  REAL,
        vibration    REAL,
        current_draw REAL
    );
    CREATE INDEX IF NOT EXISTS idx_psh ON pm_sensor_history(asset_id, ts DESC);

    CREATE TABLE IF NOT EXISTS pm_production_schedule (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id     TEXT NOT NULL,
        job_id       TEXT,
        job_name     TEXT,
        criticality  TEXT,
        due_date     INTEGER,
        quantity     INTEGER,
        product_type TEXT
    );

    CREATE TABLE IF NOT EXISTS pm_parts_inventory (
        part_number       TEXT PRIMARY KEY,
        part_name         TEXT,
        qty_in_stock      INTEGER DEFAULT 0,
        location          TEXT,
        unit_cost         REAL,
        compatible_assets TEXT
    );

    CREATE TABLE IF NOT EXISTS pm_suppliers (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        part_name      TEXT,
        supplier_name  TEXT,
        lead_time_days INTEGER,
        unit_cost      REAL,
        min_order_qty  INTEGER DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS pm_technicians (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        name               TEXT,
        shift              TEXT,
        certifications     TEXT,
        is_available       INTEGER DEFAULT 1,
        available_from     TEXT,
        current_assignment TEXT
    );

    CREATE TABLE IF NOT EXISTS pm_work_orders_cmms (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        wo_number    TEXT UNIQUE,
        asset_id     TEXT,
        fault_type   TEXT,
        priority     TEXT,
        description  TEXT,
        part_required TEXT,
        status       TEXT DEFAULT 'open',
        created_at   INTEGER
    );

    CREATE TABLE IF NOT EXISTS pm_technician_bookings (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        technician_name  TEXT,
        wo_number        TEXT,
        start_ts         INTEGER,
        end_ts           INTEGER,
        created_at       INTEGER
    );

    CREATE TABLE IF NOT EXISTS pm_purchase_orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        po_number   TEXT UNIQUE,
        part_name   TEXT,
        quantity    INTEGER,
        supplier    TEXT,
        reason      TEXT,
        total_cost  REAL,
        status      TEXT DEFAULT 'submitted',
        created_at  INTEGER
    );

    CREATE TABLE IF NOT EXISTS pm_monitoring_checkpoints (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        asset_id            TEXT,
        parameter           TEXT,
        threshold           REAL,
        escalation_contact  TEXT,
        active              INTEGER DEFAULT 1,
        created_at          INTEGER
    );

    CREATE TABLE IF NOT EXISTS pm_notifications (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient          TEXT,
        message            TEXT,
        recommended_action TEXT,
        urgency            TEXT,
        sent_at            INTEGER
    );
    """)
    conn.commit()
    _seed_pm_data(conn)


def _seed_pm_data(conn):
    # Only seed if empty
    if conn.execute("SELECT COUNT(*) FROM pm_assets").fetchone()[0] > 0:
        return

    now = int(time.time())

    # Assets (mapped to assembly station codes)
    assets = [
        ("STN-01", "Cylinder Block Prep",    "CNC Machining Centre",  "Haas VF-4SS"),
        ("STN-02", "Crankshaft Install",      "Assembly Press",        "Schuler SMG 400"),
        ("STN-03", "Piston & Con-Rod Assy",   "Manual Assembly",       "Trumpf TruPunch 5000"),
        ("STN-06", "Fuel Injection System",   "Robotic Assembly",      "FANUC M-20iA"),
        ("STN-09", "ECM & Electrical",        "Electronic Assembly",   "Siemens SIPLACE SX4"),
        ("STN-12", "Engine Test Cell",        "Test Equipment",        "AVL PUMA Open"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO pm_assets(asset_id,asset_name,asset_type,machine_model) VALUES(?,?,?,?)",
        assets
    )

    # Sensor history — STN-01 showing degradation (bearing wear pattern)
    readings = []
    for i in range(20):
        ts = now - (20 - i) * 1800  # every 30 min over last 10h
        readings.append(("STN-01", ts, round(84.0 + i * 0.22, 1), round(0.61 + i * 0.009, 3), round(14.2 + i * 0.08, 1)))
        readings.append(("STN-02", ts, round(76.0 + i * 0.05, 1), round(0.42 + i * 0.003, 3), round(12.8 + i * 0.02, 1)))
        readings.append(("STN-06", ts, round(71.0 + i * 0.03, 1), round(0.31 + i * 0.001, 3), round(10.1,              1)))
    conn.executemany(
        "INSERT INTO pm_sensor_history(asset_id,ts,temperature,vibration,current_draw) VALUES(?,?,?,?,?)",
        readings
    )

    # Production schedule
    jobs = [
        ("STN-01", "ENG-2847", "ISX15 Engine Block Machining",  "CRITICAL", now + 2 * 86400, 3,  "ISX15"),
        ("STN-01", "ENG-2851", "QSX15 Block Finish",            "HIGH",     now + 5 * 86400, 5,  "QSX15"),
        ("STN-02", "ENG-2850", "Crankshaft Grinding",           "HIGH",     now + 4 * 86400, 8,  "ISX15"),
        ("STN-02", "ENG-2855", "Crankshaft Polish",             "MEDIUM",   now + 8 * 86400, 12, "ISX15"),
        ("STN-06", "ENG-2860", "Fuel Rail Assembly",            "HIGH",     now + 3 * 86400, 6,  "QSX15"),
    ]
    conn.executemany(
        "INSERT INTO pm_production_schedule(asset_id,job_id,job_name,criticality,due_date,quantity,product_type) "
        "VALUES(?,?,?,?,?,?,?)", jobs
    )

    # Parts inventory
    parts = [
        ("SKF-6205-2Z", "SKF Deep Groove Bearing",    2,  "Crib-A, Shelf 3", 42.50,  "STN-01,STN-02"),
        ("SB-2204",     "Spindle Bearing Assembly",   0,  "—",               185.00, "STN-01"),
        ("BSEAL-100",   "Hydraulic Seal Kit",         0,  "—",               95.00,  "STN-02"),
        ("BELT-A45",    "Drive Belt A-45",            5,  "Crib-B, Shelf 1", 28.00,  "STN-03"),
        ("PLC-MOD-7",   "Siemens S7-1200 PLC Module", 1, "Electrical Store", 450.00, "STN-09"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO pm_parts_inventory(part_number,part_name,qty_in_stock,location,unit_cost,compatible_assets) "
        "VALUES(?,?,?,?,?,?)", parts
    )

    # Suppliers
    suppliers = [
        ("SKF-6205-2Z",  "SKF Authorised Distributor",  1, 42.50,  1),
        ("SB-2204",      "NSK Industrial Bearings",     5, 192.00, 1),
        ("SB-2204",      "Motion Industries",           3, 198.00, 1),
        ("BSEAL-100",    "Parker Hannifin Direct",      3, 98.00,  1),
        ("BELT-A45",     "Gates Industrial",            2, 30.00,  2),
        ("PLC-MOD-7",    "Siemens Partner Network",     7, 475.00, 1),
    ]
    conn.executemany(
        "INSERT INTO pm_suppliers(part_name,supplier_name,lead_time_days,unit_cost,min_order_qty) "
        "VALUES(?,?,?,?,?)", suppliers
    )

    # Technicians
    technicians = [
        ("John Smith",    "Shift A (06:00–14:00)", "Mechanical,Electrical",          1, "Now",     None),
        ("Maria Garcia",  "Shift A (06:00–14:00)", "Mechanical,Hydraulic",           1, "Now",     None),
        ("David Chen",    "Shift B (14:00–22:00)", "Electrical,PLC",                 1, "In 6h",   None),
        ("Sarah Johnson", "Shift B (14:00–22:00)", "Mechanical",                     1, "In 6h",   None),
        ("Mike Wilson",   "Shift C (22:00–06:00)", "Mechanical,Electrical,Hydraulic",1, "In 14h",  None),
    ]
    conn.executemany(
        "INSERT INTO pm_technicians(name,shift,certifications,is_available,available_from,current_assignment) "
        "VALUES(?,?,?,?,?,?)", technicians
    )

    conn.commit()
    print("[PM] Seeded PM tables with demo data")


# ── Tool implementations ──────────────────────────────────────────────────────

def _tool_get_sensor_data(asset_id: str) -> dict:
    rows = get_conn().execute(
        "SELECT ts, temperature, vibration, current_draw FROM pm_sensor_history "
        "WHERE asset_id=? ORDER BY ts DESC LIMIT 10", (asset_id,)
    ).fetchall()
    if not rows:
        return {"error": f"No sensor history for {asset_id}"}
    readings = [dict(r) for r in rows]
    temps = [r["temperature"] for r in readings]
    vibs  = [r["vibration"]   for r in readings]
    return {
        "asset_id": asset_id,
        "latest": readings[0],
        "readings_count": len(readings),
        "temperature_trend": f"{temps[-1]}°C → {temps[0]}°C (oldest→latest), Δ{round(temps[0]-temps[-1],1):+}°C",
        "vibration_trend":   f"{vibs[-1]:.3f}g → {vibs[0]:.3f}g, Δ{round(vibs[0]-vibs[-1],3):+.3f}g",
        "assessment": (
            "CRITICAL — sustained upward trend in both temperature and vibration"
            if temps[0] > 88 and vibs[0] > 0.72 else
            "WARNING — temperature or vibration elevated and rising"
            if temps[0] > 85 or vibs[0] > 0.65 else
            "NORMAL — within acceptable range"
        )
    }


def _tool_get_fault_prognosis(asset_id: str, fault_type: str) -> dict:
    row = get_conn().execute(
        "SELECT temperature, vibration, current_draw FROM pm_sensor_history "
        "WHERE asset_id=? ORDER BY ts DESC LIMIT 1", (asset_id,)
    ).fetchone()
    if not row:
        return {"error": f"No sensor data for {asset_id}"}
    temp, vib = row["temperature"], row["vibration"]

    # Simulate ML prognosis
    if temp > 89 or vib > 0.78:
        days, conf = round(1.2 + (92 - temp) * 0.2, 1), 0.88
    elif temp > 86 or vib > 0.68:
        days, conf = round(3.0 + (90 - temp) * 0.4, 1), 0.76
    else:
        days, conf = 6.5, 0.60

    days = max(0.5, days)
    urgency = "CRITICAL" if days < 2 else "HIGH" if days < 4 else "MEDIUM"

    get_conn().execute(
        "UPDATE pm_assets SET days_to_failure=?, last_prognosis_ts=? WHERE asset_id=?",
        (days, int(time.time()), asset_id)
    )
    get_conn().commit()

    return {
        "asset_id": asset_id,
        "fault_type": fault_type,
        "days_to_failure_p50": days,
        "days_to_failure_p10": round(days * 0.55, 1),
        "days_to_failure_p90": round(days * 1.6,  1),
        "model_confidence": conf,
        "urgency": urgency,
        "basis": f"Temp {temp:.1f}°C + vibration {vib:.3f}g RMS — progressive bearing degradation pattern"
    }


def _tool_get_production_schedule(asset_id: str) -> dict:
    rows = get_conn().execute(
        "SELECT job_id, job_name, criticality, due_date, quantity, product_type "
        "FROM pm_production_schedule WHERE asset_id=? ORDER BY due_date ASC", (asset_id,)
    ).fetchall()
    now = int(time.time())
    jobs = []
    for r in rows:
        d = dict(r)
        d["days_until_due"] = round((d["due_date"] - now) / 86400, 1)
        jobs.append(d)
    return {
        "asset_id": asset_id,
        "jobs": jobs,
        "critical_jobs": [j for j in jobs if j["criticality"] == "CRITICAL"],
        "next_job_due_in_days": jobs[0]["days_until_due"] if jobs else None
    }


def _tool_check_parts_inventory(part_name: str) -> dict:
    row = get_conn().execute(
        "SELECT part_number, part_name, qty_in_stock, location, unit_cost, compatible_assets "
        "FROM pm_parts_inventory WHERE part_name LIKE ? OR part_number LIKE ?",
        (f"%{part_name}%", f"%{part_name}%")
    ).fetchone()
    if not row:
        return {"found": False, "message": f"'{part_name}' not found in parts inventory"}
    d = dict(row)
    d["in_stock"] = d["qty_in_stock"] > 0
    return d


def _tool_get_supplier_lead_time(part_name: str) -> dict:
    rows = get_conn().execute(
        "SELECT supplier_name, lead_time_days, unit_cost, min_order_qty "
        "FROM pm_suppliers WHERE part_name LIKE ?", (f"%{part_name}%",)
    ).fetchall()
    if not rows:
        return {"found": False, "message": f"No suppliers found for '{part_name}'"}
    suppliers = [dict(r) for r in rows]
    best = min(suppliers, key=lambda x: x["lead_time_days"])
    return {
        "part_name": part_name,
        "suppliers": suppliers,
        "fastest_supplier": best["supplier_name"],
        "fastest_lead_time_days": best["lead_time_days"],
        "unit_cost": best["unit_cost"]
    }


def _tool_get_technician_availability(required_cert: str, within_hours: int = 48) -> dict:
    rows = get_conn().execute(
        "SELECT name, shift, certifications, available_from, current_assignment "
        "FROM pm_technicians WHERE certifications LIKE ? AND is_available=1",
        (f"%{required_cert}%",)
    ).fetchall()
    techs = [dict(r) for r in rows]
    return {
        "required_cert": required_cert,
        "available": techs,
        "count": len(techs),
        "best_option": techs[0] if techs else None
    }


def _tool_create_work_order(asset_id: str, fault_type: str, priority: str,
                             description: str, part_required: str | None = None) -> dict:
    ts = int(time.time())
    wo = f"WO-PM-{ts % 100000:05d}"
    get_conn().execute(
        "INSERT INTO pm_work_orders_cmms(wo_number,asset_id,fault_type,priority,description,part_required,status,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (wo, asset_id, fault_type, priority, description, part_required, "open", ts)
    )
    get_conn().commit()
    return {"success": True, "wo_number": wo, "asset_id": asset_id, "priority": priority, "status": "Created in CMMS"}


def _tool_schedule_technician(technician_name: str, wo_number: str,
                               start_offset_hours: float, duration_hours: float) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO pm_technician_bookings(technician_name,wo_number,start_ts,end_ts,created_at) "
        "VALUES(?,?,?,?,?)",
        (technician_name, wo_number, ts + int(start_offset_hours * 3600),
         ts + int((start_offset_hours + duration_hours) * 3600), ts)
    )
    get_conn().execute(
        "UPDATE pm_technicians SET is_available=0, current_assignment=? WHERE name=?",
        (wo_number, technician_name)
    )
    get_conn().commit()
    window = f"in {start_offset_hours:.0f}h" if start_offset_hours > 0 else "immediately"
    return {
        "success": True,
        "technician": technician_name,
        "wo_number": wo_number,
        "window": f"Starting {window}, duration {duration_hours}h",
        "confirmation": f"{technician_name} booked — CMMS and workforce system updated"
    }


def _tool_create_purchase_order(part_name: str, quantity: int, reason: str) -> dict:
    ts  = int(time.time())
    po  = f"PO-{ts % 100000:05d}"
    row = get_conn().execute(
        "SELECT unit_cost, supplier_name, lead_time_days FROM pm_suppliers "
        "WHERE part_name LIKE ? ORDER BY lead_time_days ASC LIMIT 1",
        (f"%{part_name}%",)
    ).fetchone()
    d = dict(row) if row else {}
    total = round(d.get("unit_cost", 0) * quantity, 2)
    get_conn().execute(
        "INSERT INTO pm_purchase_orders(po_number,part_name,quantity,supplier,reason,total_cost,status,created_at) "
        "VALUES(?,?,?,?,?,?,?,?)",
        (po, part_name, quantity, d.get("supplier_name","TBD"), reason, total, "submitted", ts)
    )
    get_conn().commit()
    return {
        "success": True,
        "po_number": po,
        "part_name": part_name,
        "quantity": quantity,
        "supplier": d.get("supplier_name", "TBD"),
        "total_cost": f"${total:,.2f}",
        "expected_delivery_days": d.get("lead_time_days", "Unknown")
    }


def _tool_set_monitoring_checkpoint(asset_id: str, parameter: str,
                                     threshold: float, escalation_contact: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO pm_monitoring_checkpoints(asset_id,parameter,threshold,escalation_contact,active,created_at) "
        "VALUES(?,?,?,?,1,?)",
        (asset_id, parameter, threshold, escalation_contact, ts)
    )
    get_conn().commit()
    return {
        "success": True,
        "monitoring": f"{asset_id} {parameter} > {threshold}",
        "escalates_to": escalation_contact,
        "status": "Active checkpoint configured in monitoring system"
    }


def _tool_notify_human(recipient: str, message: str,
                        recommended_action: str, urgency: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO pm_notifications(recipient,message,recommended_action,urgency,sent_at) "
        "VALUES(?,?,?,?,?)",
        (recipient, message, recommended_action, urgency, ts)
    )
    get_conn().commit()
    return {
        "success": True,
        "recipient": recipient,
        "urgency": urgency,
        "channels": "Teams + SMS + email",
        "sent_at": ts
    }


# ── Dispatcher ────────────────────────────────────────────────────────────────

_DISPATCH = {
    "get_sensor_data":            lambda i: _tool_get_sensor_data(i["asset_id"]),
    "get_fault_prognosis":        lambda i: _tool_get_fault_prognosis(i["asset_id"], i["fault_type"]),
    "get_production_schedule":    lambda i: _tool_get_production_schedule(i["asset_id"]),
    "check_parts_inventory":      lambda i: _tool_check_parts_inventory(i["part_name"]),
    "get_supplier_lead_time":     lambda i: _tool_get_supplier_lead_time(i["part_name"]),
    "get_technician_availability":lambda i: _tool_get_technician_availability(
        i["required_cert"], i.get("within_hours", 48)),
    "create_work_order":          lambda i: _tool_create_work_order(
        i["asset_id"], i["fault_type"], i["priority"], i["description"], i.get("part_required")),
    "schedule_technician":        lambda i: _tool_schedule_technician(
        i["technician_name"], i["wo_number"], i["start_offset_hours"], i["duration_hours"]),
    "create_purchase_order":      lambda i: _tool_create_purchase_order(
        i["part_name"], i["quantity"], i["reason"]),
    "set_monitoring_checkpoint":  lambda i: _tool_set_monitoring_checkpoint(
        i["asset_id"], i["parameter"], i["threshold"], i["escalation_contact"]),
    "notify_human":               lambda i: _tool_notify_human(
        i["recipient"], i["message"], i["recommended_action"], i["urgency"]),
}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_pm_agent(asset_id: str, fault_type: str,
                       sensor_readings: dict, api_key: str):
    """
    Agentic loop using Claude tool_use.
    Yields SSE-formatted strings: data: <json>\n\n
    """
    import anthropic as _ant

    client = _ant.Anthropic(api_key=api_key)
    loop   = asyncio.get_event_loop()

    row = get_conn().execute(
        "SELECT asset_name, machine_model FROM pm_assets WHERE asset_id=?", (asset_id,)
    ).fetchone()
    meta = dict(row) if row else {"asset_name": asset_id, "machine_model": "Unknown"}

    initial = (
        f"FAULT DETECTED — {meta['asset_name']} ({asset_id}) · {meta['machine_model']}\n\n"
        f"Fault type: {fault_type}\n"
        f"Current sensor readings:\n"
        f"  Temperature : {sensor_readings.get('machine_temp', sensor_readings.get('temperature', 'N/A'))}°C\n"
        f"  Vibration   : {sensor_readings.get('vibration', 'N/A')}g RMS\n"
        f"  Tool Life   : {sensor_readings.get('tool_life_pct', 'N/A')}%\n\n"
        f"Follow your reasoning framework. Take all necessary actions to prevent failure "
        f"while minimising disruption to the production schedule."
    )

    messages = [{"role": "user", "content": initial}]

    for _ in range(15):  # safety cap at 15 rounds
        response = await loop.run_in_executor(
            None,
            lambda m=messages: client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=m,
            )
        )

        tool_results = []

        for block in response.content:
            if block.type == "text" and block.text.strip():
                yield f"data: {json.dumps({'type': 'thinking', 'text': block.text})}\n\n"

            elif block.type == "tool_use":
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"

                try:
                    fn     = _DISPATCH.get(block.name)
                    result = fn(block.input) if fn else {"error": f"Unknown tool: {block.name}"}
                except Exception as exc:
                    result = {"error": str(exc)}

                yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': result})}\n\n"

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            break

        if tool_results:
            messages.append({"role": "user", "content": tool_results})
