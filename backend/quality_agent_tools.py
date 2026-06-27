from __future__ import annotations
import asyncio
import json
import time
from database import get_conn

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a Quality Intelligence Agent for the Cummins Columbus IN engine manufacturing plant.

ROLE: When a quality signal is detected, you own the problem from detection to closure.
You do not just detect problems — you find root cause, contain the affected population,
correct the process, and verify the fix worked.

You have authority to:
- Quarantine parts, assemblies, and finished engines
- Place holds on production operations
- Create NCRs and CAPAs
- Notify suppliers of quality escapes
- Trigger 100% inspection on suspect populations
- Release holds once evidence confirms resolution

You MUST escalate to a human (notify_human) when:
- A potential field escape is detected (shipped engine may be affected)
- Root cause cannot be determined after 3 reasoning cycles
- Containment would stop more than one full production line

REASONING FRAMEWORK — follow in order, show your reasoning before each tool call:

STEP 1 — CHARACTERIZE: What exactly is the defect? What feature? What operation?
STEP 2 — SCOPE: Which serial numbers are affected? Any already shipped?
STEP 3 — CONTAIN: Quarantine suspect population. Place operation hold. Stop the bleeding.
STEP 4 — ROOT CAUSE: What process parameter caused this? Check tooling, coolant,
         operator, material, machine maintenance. Check measurement system first.
STEP 5 — CORRECT: Fix the process. Disposition the quarantined parts.
STEP 6 — VERIFY: Set enhanced monitoring. Trigger first-article after correction.
STEP 7 — LEARN: Update control plan. Check sister components. Log to knowledge graph.

Always show your reasoning before calling a tool.
After each tool result, state what it means for your investigation.
At the end, give a clear structured summary of all actions taken.
"""

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    # ── PERCEPTION ─────────────────────────────────────────────────────────────
    {
        "name": "get_inspection_result",
        "description": "Pull CMM / vision / gauge measurement data for a station and feature. Returns recent inspection records with measured values, tolerances, and pass/fail results.",
        "input_schema": {"type": "object", "properties": {
            "station":       {"type": "string", "description": "Station code, e.g. STN-03"},
            "feature":       {"type": "string", "description": "Feature name, e.g. Ring End Gap"},
            "serial_number": {"type": "string", "description": "Optional — filter to one serial number"}
        }, "required": ["station", "feature"]}
    },
    {
        "name": "get_spc_chart",
        "description": "Pull Statistical Process Control data for a feature — Xbar-R values, Cpk trend, and Western Electric rule violations.",
        "input_schema": {"type": "object", "properties": {
            "station": {"type": "string"},
            "feature": {"type": "string"}
        }, "required": ["station", "feature"]}
    },
    {
        "name": "get_test_results",
        "description": "Pull engine test cell results — performance, leakage, vibration, and endurance data for a serial number.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"}
        }, "required": ["serial_number"]}
    },
    {
        "name": "get_visual_inspection_log",
        "description": "Pull operator visual inspection records and any findings from MES for a serial number or station.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"},
            "station":       {"type": "string"}
        }, "required": []}
    },
    {
        "name": "get_gauge_calibration_status",
        "description": "Check if measurement equipment at a station is in calibration and whether the gauge R&R (GR&R) is capable. GR&R > 30% is unacceptable.",
        "input_schema": {"type": "object", "properties": {
            "station": {"type": "string", "description": "Station code"}
        }, "required": ["station"]}
    },
    # ── TRACEABILITY ───────────────────────────────────────────────────────────
    {
        "name": "get_serial_number_history",
        "description": "Full traveler for a serial number — every operation, timestamp, operator, machine, material lot, and inspection result in chronological order.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"}
        }, "required": ["serial_number"]}
    },
    {
        "name": "get_material_lot_traceability",
        "description": "Given a material lot number, find every serial number that used it — forward and backward trace.",
        "input_schema": {"type": "object", "properties": {
            "lot_number": {"type": "string", "description": "Material lot number, e.g. LOT-MCR-4471"}
        }, "required": ["lot_number"]}
    },
    {
        "name": "get_affected_population",
        "description": "Given a time window and station, return all serial numbers that passed through — the full suspect list.",
        "input_schema": {"type": "object", "properties": {
            "station":     {"type": "string"},
            "hours_back":  {"type": "integer", "description": "How many hours back to search", "default": 8}
        }, "required": ["station"]}
    },
    {
        "name": "get_engine_location",
        "description": "Where is this serial number right now? In-process, final assembly, test cell, shipping hold, or shipped to customer.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"}
        }, "required": ["serial_number"]}
    },
    {
        "name": "get_shipment_records",
        "description": "Has this serial number been shipped? Returns customer name, ship date, and PO number if shipped.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"}
        }, "required": ["serial_number"]}
    },
    # ── ROOT CAUSE ─────────────────────────────────────────────────────────────
    {
        "name": "get_process_parameters",
        "description": "Pull machine parameters at the time a serial number ran through a station — spindle speed, feed rate, torque, temperature, coolant flow and concentration, cycle time.",
        "input_schema": {"type": "object", "properties": {
            "serial_number": {"type": "string"},
            "station":       {"type": "string"}
        }, "required": ["serial_number", "station"]}
    },
    {
        "name": "get_tooling_history",
        "description": "What cutting tool / hone / fixture was in use? Tool life remaining at that point? When was the last tool change?",
        "input_schema": {"type": "object", "properties": {
            "station":       {"type": "string"},
            "serial_number": {"type": "string", "description": "Optional — get tool state when this serial ran"}
        }, "required": ["station"]}
    },
    {
        "name": "get_material_cert",
        "description": "Pull material certificate for a lot — chemistry, hardness, heat treatment, supplier, and heat number.",
        "input_schema": {"type": "object", "properties": {
            "lot_number": {"type": "string"}
        }, "required": ["lot_number"]}
    },
    {
        "name": "get_operator_log",
        "description": "Who ran the operation? Returns operator name, shift, training level, and any deviations logged.",
        "input_schema": {"type": "object", "properties": {
            "station":       {"type": "string"},
            "serial_number": {"type": "string"}
        }, "required": ["station"]}
    },
    {
        "name": "get_maintenance_history",
        "description": "Was the machine serviced recently? Returns PM history, any alarms or faults logged around the time of suspect production.",
        "input_schema": {"type": "object", "properties": {
            "station": {"type": "string"}
        }, "required": ["station"]}
    },
    {
        "name": "get_engineering_drawing",
        "description": "Pull current revision of drawing and GD&T for the feature in question — confirms the actual tolerance and any special notes.",
        "input_schema": {"type": "object", "properties": {
            "component": {"type": "string", "description": "Component name, e.g. ISX15 Compression Ring"},
            "feature":   {"type": "string", "description": "Feature name, e.g. Ring End Gap"}
        }, "required": ["component", "feature"]}
    },
    {
        "name": "query_failure_knowledge_graph",
        "description": "Search historical NCRs and CAPAs for this component, feature, or defect type. Has this happened before? What fixed it?",
        "input_schema": {"type": "object", "properties": {
            "component":   {"type": "string"},
            "defect_type": {"type": "string", "description": "e.g. ring_gap_oversize, bent_pin, surface_finish"}
        }, "required": ["component", "defect_type"]}
    },
    {
        "name": "get_similar_components",
        "description": "Are there sister parts or family components with the same feature that could also be affected by this root cause?",
        "input_schema": {"type": "object", "properties": {
            "component": {"type": "string"},
            "feature":   {"type": "string"}
        }, "required": ["component", "feature"]}
    },
    # ── ACTION ─────────────────────────────────────────────────────────────────
    {
        "name": "quarantine_serial_numbers",
        "description": "Place a hold in MES on a list of serial numbers — they cannot move forward until released. Records the reason and optionally links to an NCR.",
        "input_schema": {"type": "object", "properties": {
            "serial_numbers": {"type": "array", "items": {"type": "string"}},
            "reason":         {"type": "string"},
            "ncr_number":     {"type": "string", "description": "Optional NCR to link"}
        }, "required": ["serial_numbers", "reason"]}
    },
    {
        "name": "place_operation_hold",
        "description": "Stop a specific operation at a station — no new parts can enter until hold is lifted.",
        "input_schema": {"type": "object", "properties": {
            "station": {"type": "string"},
            "machine": {"type": "string", "description": "Specific machine or 'all'"},
            "reason":  {"type": "string"}
        }, "required": ["station", "machine", "reason"]}
    },
    {
        "name": "create_ncr",
        "description": "Create a Non-Conformance Report with defect description, affected population, discovery point, and severity classification.",
        "input_schema": {"type": "object", "properties": {
            "defect_description":     {"type": "string"},
            "affected_serial_numbers":{"type": "array", "items": {"type": "string"}},
            "severity":               {"type": "string", "enum": ["CRITICAL", "MAJOR", "MINOR"]},
            "discovery_point":        {"type": "string", "description": "Where/how defect was found"},
            "defect_code":            {"type": "string", "description": "Defect classification code"}
        }, "required": ["defect_description", "affected_serial_numbers", "severity", "discovery_point"]}
    },
    {
        "name": "create_capa",
        "description": "Create a Corrective Action / Preventive Action record with root cause, corrective action, verification plan, owner, and due date.",
        "input_schema": {"type": "object", "properties": {
            "ncr_number":         {"type": "string"},
            "root_cause":         {"type": "string"},
            "corrective_action":  {"type": "string"},
            "preventive_action":  {"type": "string"},
            "verification_plan":  {"type": "string"},
            "owner":              {"type": "string"},
            "due_date_days":      {"type": "integer", "description": "Days from today until CAPA due"}
        }, "required": ["ncr_number", "root_cause", "corrective_action", "verification_plan", "owner", "due_date_days"]}
    },
    {
        "name": "trigger_100pct_inspection",
        "description": "Override normal sampling plan — flag every unit in the suspect population for 100% inspection of a specific feature.",
        "input_schema": {"type": "object", "properties": {
            "serial_numbers": {"type": "array", "items": {"type": "string"}},
            "feature":        {"type": "string"},
            "reason":         {"type": "string"}
        }, "required": ["serial_numbers", "feature", "reason"]}
    },
    {
        "name": "disposition_parts",
        "description": "Record disposition decision for NCR parts — rework with instructions, scrap with reason, or use-as-is with engineering approval.",
        "input_schema": {"type": "object", "properties": {
            "serial_numbers": {"type": "array", "items": {"type": "string"}},
            "ncr_number":     {"type": "string"},
            "disposition":    {"type": "string", "enum": ["rework", "scrap", "use-as-is"]},
            "instructions":   {"type": "string", "description": "Rework instructions or scrap reason"}
        }, "required": ["serial_numbers", "ncr_number", "disposition", "instructions"]}
    },
    {
        "name": "release_hold",
        "description": "Lift a quarantine or operation hold once evidence confirms resolution. Logs who released it, why, and what evidence was provided.",
        "input_schema": {"type": "object", "properties": {
            "hold_type":  {"type": "string", "enum": ["quarantine", "operation"]},
            "reference":  {"type": "string", "description": "Serial number(s) or station code"},
            "reason":     {"type": "string"},
            "evidence":   {"type": "string", "description": "What evidence confirms it is safe to release"}
        }, "required": ["hold_type", "reference", "reason", "evidence"]}
    },
    {
        "name": "notify_supplier",
        "description": "Send formal supplier notification with defect description, lot numbers, and required 8D response due date.",
        "input_schema": {"type": "object", "properties": {
            "supplier":          {"type": "string"},
            "defect_description":{"type": "string"},
            "lot_numbers":       {"type": "array", "items": {"type": "string"}},
            "ncr_number":        {"type": "string"},
            "response_due_days": {"type": "integer", "description": "Days until 8D response is due"}
        }, "required": ["supplier", "defect_description", "lot_numbers", "ncr_number", "response_due_days"]}
    },
    {
        "name": "notify_customer",
        "description": "Draft a customer notification for a potential field escape. IMPORTANT: This is flagged for human approval before sending — it does not send automatically.",
        "input_schema": {"type": "object", "properties": {
            "customer":      {"type": "string"},
            "message":       {"type": "string", "description": "Full context message for customer"},
            "serial_numbers":{"type": "array", "items": {"type": "string"}},
            "po_number":     {"type": "string", "description": "Customer PO number if known"}
        }, "required": ["customer", "message", "serial_numbers"]}
    },
    {
        "name": "update_control_plan",
        "description": "Flag the control plan for engineering review with recommended changes based on root cause finding.",
        "input_schema": {"type": "object", "properties": {
            "component":             {"type": "string"},
            "feature":               {"type": "string"},
            "reason":                {"type": "string"},
            "recommended_changes":   {"type": "string"}
        }, "required": ["component", "feature", "reason", "recommended_changes"]}
    },
    {
        "name": "set_enhanced_monitoring",
        "description": "Set tighter SPC alert thresholds or increase inspection frequency on a feature for the next N pieces.",
        "input_schema": {"type": "object", "properties": {
            "station":     {"type": "string"},
            "feature":     {"type": "string"},
            "new_usl":     {"type": "number", "description": "Tighter upper spec limit"},
            "n_pieces":    {"type": "integer", "description": "Apply enhanced monitoring for next N pieces"},
            "reason":      {"type": "string"}
        }, "required": ["station", "feature", "new_usl", "n_pieces", "reason"]}
    },
    {
        "name": "notify_human",
        "description": "Escalate to a named person with full reasoning chain, situation summary, and specific decision needed from them.",
        "input_schema": {"type": "object", "properties": {
            "recipient":          {"type": "string"},
            "message":            {"type": "string"},
            "recommended_action": {"type": "string"},
            "urgency":            {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
        }, "required": ["recipient", "message", "recommended_action", "urgency"]}
    },
]

# ── DB init + seed ────────────────────────────────────────────────────────────

def init_quality_tables():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS qa_engines (
        serial_number TEXT PRIMARY KEY,
        product_type  TEXT,
        build_date    INTEGER,
        current_op    TEXT,
        status        TEXT DEFAULT 'in-process'
    );
    CREATE TABLE IF NOT EXISTS qa_inspection_results (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number  TEXT,
        station        TEXT,
        feature        TEXT,
        measured_value REAL,
        usl            REAL,
        lsl            REAL,
        unit           TEXT,
        result         TEXT,
        inspector      TEXT,
        ts             INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_spc_data (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        station     TEXT,
        feature     TEXT,
        subgroup_id INTEGER,
        xbar        REAL,
        r_value     REAL,
        cpk         REAL,
        ts          INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_test_results (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT,
        test_type     TEXT,
        parameter     TEXT,
        measured      REAL,
        limit_value   REAL,
        unit          TEXT,
        result        TEXT,
        ts            INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_visual_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT,
        station       TEXT,
        inspector     TEXT,
        findings      TEXT,
        result        TEXT,
        ts            INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_gauge_calibration (
        gauge_id      TEXT PRIMARY KEY,
        gauge_name    TEXT,
        station       TEXT,
        cal_due_ts    INTEGER,
        grr_pct       REAL,
        status        TEXT
    );
    CREATE TABLE IF NOT EXISTS qa_material_lots (
        lot_number    TEXT PRIMARY KEY,
        material_type TEXT,
        supplier      TEXT,
        heat_number   TEXT,
        serial_numbers TEXT,
        received_ts   INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_engine_locations (
        serial_number TEXT PRIMARY KEY,
        location      TEXT,
        location_detail TEXT,
        updated_ts    INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_shipments (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT,
        customer      TEXT,
        ship_date     INTEGER,
        po_number     TEXT,
        destination   TEXT
    );
    CREATE TABLE IF NOT EXISTS qa_process_params (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_number TEXT,
        station       TEXT,
        spindle_rpm   INTEGER,
        feed_mm_min   REAL,
        coolant_pct   REAL,
        coolant_lpm   REAL,
        cycle_time_s  INTEGER,
        ts            INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_tooling_history (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        station         TEXT,
        tool_id         TEXT,
        tool_name       TEXT,
        life_pct_at_use REAL,
        change_life_limit REAL,
        last_change_days_ago INTEGER,
        serial_numbers  TEXT,
        ts              INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_material_certs (
        lot_number     TEXT PRIMARY KEY,
        material_spec  TEXT,
        supplier       TEXT,
        hardness_hb    TEXT,
        heat_treat     TEXT,
        chemistry_ok   INTEGER,
        cert_number    TEXT
    );
    CREATE TABLE IF NOT EXISTS qa_operator_log (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        station       TEXT,
        serial_number TEXT,
        operator_name TEXT,
        shift         TEXT,
        cert_level    TEXT,
        deviation     TEXT,
        ts            INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_machine_maintenance (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        station     TEXT,
        event_type  TEXT,
        description TEXT,
        days_ago    INTEGER,
        status      TEXT,
        ts          INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_drawings (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        component   TEXT,
        feature     TEXT,
        nominal     REAL,
        usl         REAL,
        lsl         REAL,
        unit        TEXT,
        revision    TEXT,
        notes       TEXT
    );
    CREATE TABLE IF NOT EXISTS qa_failure_kg (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        ncr_number       TEXT,
        component        TEXT,
        feature          TEXT,
        defect_type      TEXT,
        root_cause       TEXT,
        corrective_action TEXT,
        closed_date      TEXT,
        notes            TEXT
    );
    CREATE TABLE IF NOT EXISTS qa_similar_components (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        component  TEXT,
        feature    TEXT,
        similar    TEXT,
        notes      TEXT
    );
    -- Write tables
    CREATE TABLE IF NOT EXISTS qa_quarantine (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_numbers TEXT,
        reason        TEXT,
        ncr_number    TEXT,
        quarantined_at INTEGER,
        released_at   INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_operation_holds (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        station    TEXT,
        machine    TEXT,
        reason     TEXT,
        placed_at  INTEGER,
        lifted_at  INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_ncrs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        ncr_number      TEXT UNIQUE,
        defect_description TEXT,
        serial_numbers  TEXT,
        severity        TEXT,
        discovery_point TEXT,
        defect_code     TEXT,
        status          TEXT DEFAULT 'open',
        created_at      INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_capas (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        capa_number       TEXT UNIQUE,
        ncr_number        TEXT,
        root_cause        TEXT,
        corrective_action TEXT,
        preventive_action TEXT,
        verification_plan TEXT,
        owner             TEXT,
        due_date          INTEGER,
        status            TEXT DEFAULT 'open',
        created_at        INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_100pct (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_numbers TEXT,
        feature       TEXT,
        reason        TEXT,
        created_at    INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_dispositions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        serial_numbers TEXT,
        ncr_number    TEXT,
        disposition   TEXT,
        instructions  TEXT,
        created_at    INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_hold_releases (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        hold_type  TEXT,
        reference  TEXT,
        reason     TEXT,
        evidence   TEXT,
        released_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_supplier_notifs (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier         TEXT,
        defect_description TEXT,
        lot_numbers      TEXT,
        ncr_number       TEXT,
        response_due_days INTEGER,
        sent_at          INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_customer_notifs (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        customer      TEXT,
        message       TEXT,
        serial_numbers TEXT,
        po_number     TEXT,
        status        TEXT DEFAULT 'pending_human_approval',
        created_at    INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_control_plan_flags (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        component            TEXT,
        feature              TEXT,
        reason               TEXT,
        recommended_changes  TEXT,
        flagged_at           INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_enhanced_monitoring (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        station    TEXT,
        feature    TEXT,
        new_usl    REAL,
        n_pieces   INTEGER,
        reason     TEXT,
        active     INTEGER DEFAULT 1,
        created_at INTEGER
    );
    CREATE TABLE IF NOT EXISTS qa_human_escalations (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        recipient          TEXT,
        message            TEXT,
        recommended_action TEXT,
        urgency            TEXT,
        sent_at            INTEGER
    );
    """)
    conn.commit()
    _seed_quality_data(conn)


def _seed_quality_data(conn):
    if conn.execute("SELECT COUNT(*) FROM qa_engines").fetchone()[0] > 0:
        return

    now = int(time.time())

    # Engines
    engines = [
        ("ENG-2847-001", "ISX15", now - 8*3600, "STN-03 Piston & Con-Rod", "in-process"),
        ("ENG-2847-002", "ISX15", now - 7*3600, "STN-04 Cylinder Head",    "in-process"),
        ("ENG-2847-003", "ISX15", now - 6*3600, "STN-05 Oil System",       "in-process"),
        ("ENG-2847-004", "ISX15", now - 5*3600, "Test Cell 1",             "in-test"),
        ("ENG-2847-005", "ISX15", now - 4*3600, "Shipping Hold",           "shipping-hold"),
        ("ENG-2847-006", "ISX15", now - 3*86400,"SHIPPED",                 "shipped"),
        ("ENG-2847-007", "ISX15", now - 2*3600, "STN-03 Piston & Con-Rod", "in-process"),
        ("ENG-2847-008", "ISX15", now - 1*3600, "STN-02 Crankshaft",      "in-process"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO qa_engines(serial_number,product_type,build_date,current_op,status) VALUES(?,?,?,?,?)",
        engines
    )

    # Engine locations
    locations = [
        ("ENG-2847-001", "in-process",     "STN-03 · Piston & Con-Rod Assy",  now),
        ("ENG-2847-002", "in-process",     "STN-04 · Cylinder Head Torque",   now),
        ("ENG-2847-003", "in-process",     "STN-05 · Oil System & Sump",      now),
        ("ENG-2847-004", "test-cell",      "Test Cell 1 · Performance Test",  now),
        ("ENG-2847-005", "shipping-hold",  "Shipping Bay 3 · Awaiting QA",    now),
        ("ENG-2847-006", "shipped",        "Fleet Solutions Inc · Chicago IL", now - 3*86400),
        ("ENG-2847-007", "in-process",     "STN-03 · Piston & Con-Rod Assy",  now),
        ("ENG-2847-008", "in-process",     "STN-02 · Crankshaft Install",     now),
    ]
    conn.executemany(
        "INSERT OR REPLACE INTO qa_engine_locations(serial_number,location,location_detail,updated_ts) VALUES(?,?,?,?)",
        locations
    )

    # Shipment records — ENG-2847-006 is shipped
    conn.execute(
        "INSERT INTO qa_shipments(serial_number,customer,ship_date,po_number,destination) VALUES(?,?,?,?,?)",
        ("ENG-2847-006", "Fleet Solutions Inc", now - 3*86400, "PO-FS-44821", "Chicago IL Distribution Centre")
    )

    # Material lots — LOT-MCR-4471 is the suspect piston ring batch
    lots = [
        ("LOT-MCR-4471", "Compression Piston Ring", "Mahle GmbH",    "HEAT-MCR-8819",
         "ENG-2847-001,ENG-2847-002,ENG-2847-003,ENG-2847-006,ENG-2847-007", now - 5*86400),
        ("LOT-MCR-4468", "Compression Piston Ring", "Mahle GmbH",    "HEAT-MCR-8815",
         "ENG-2847-004,ENG-2847-005", now - 12*86400),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO qa_material_lots(lot_number,material_type,supplier,heat_number,serial_numbers,received_ts) VALUES(?,?,?,?,?,?)",
        lots
    )

    # Inspection results — Ring End Gap at STN-03 (spec 0.20–0.40mm)
    inspections = [
        ("ENG-2847-001", "STN-03", "Ring End Gap", 0.51, 0.40, 0.20, "mm", "FAIL", "Vision-AI", now - 2*3600),
        ("ENG-2847-002", "STN-03", "Ring End Gap", 0.43, 0.40, 0.20, "mm", "FAIL", "Vision-AI", now - 4*3600),
        ("ENG-2847-003", "STN-03", "Ring End Gap", 0.41, 0.40, 0.20, "mm", "FAIL", "Vision-AI", now - 5*3600),
        ("ENG-2847-004", "STN-03", "Ring End Gap", 0.32, 0.40, 0.20, "mm", "PASS", "Vision-AI", now - 6*3600),
        ("ENG-2847-005", "STN-03", "Ring End Gap", 0.29, 0.40, 0.20, "mm", "PASS", "Vision-AI", now - 7*3600),
        ("ENG-2847-006", "STN-03", "Ring End Gap", 0.47, 0.40, 0.20, "mm", "FAIL", "Vision-AI", now - 3*86400),
        ("ENG-2847-007", "STN-03", "Ring End Gap", 0.49, 0.40, 0.20, "mm", "FAIL", "Vision-AI", now - 1*3600),
    ]
    conn.executemany(
        "INSERT INTO qa_inspection_results(serial_number,station,feature,measured_value,usl,lsl,unit,result,inspector,ts) "
        "VALUES(?,?,?,?,?,?,?,?,?,?)", inspections
    )

    # SPC data — showing upward drift over last 6 subgroups
    spc_rows = [
        ("STN-03", "Ring End Gap", 1, 0.27, 0.08, 1.42, now - 7*3600),
        ("STN-03", "Ring End Gap", 2, 0.29, 0.07, 1.38, now - 6*3600),
        ("STN-03", "Ring End Gap", 3, 0.31, 0.09, 1.31, now - 5*3600),
        ("STN-03", "Ring End Gap", 4, 0.36, 0.10, 1.08, now - 4*3600),
        ("STN-03", "Ring End Gap", 5, 0.42, 0.11, 0.82, now - 3*3600),
        ("STN-03", "Ring End Gap", 6, 0.47, 0.12, 0.78, now - 2*3600),
    ]
    conn.executemany(
        "INSERT INTO qa_spc_data(station,feature,subgroup_id,xbar,r_value,cpk,ts) VALUES(?,?,?,?,?,?,?)",
        spc_rows
    )

    # Gauge calibration
    conn.execute(
        "INSERT OR IGNORE INTO qa_gauge_calibration(gauge_id,gauge_name,station,cal_due_ts,grr_pct,status) VALUES(?,?,?,?,?,?)",
        ("GAUGE-RG-03", "Ring End Gap Air Gauge", "STN-03", now + 5*86400, 28.0, "MARGINAL — GR&R 28% (limit 30%)")
    )

    # Test results for ENG-2847-004 (in test cell)
    test_rows = [
        ("ENG-2847-004", "Performance",  "Peak Power",       449.0, 450.0, "kW",  "PASS", now - 4*3600),
        ("ENG-2847-004", "Performance",  "Peak Torque",     2049.0, 2050.0,"Nm",  "PASS", now - 4*3600),
        ("ENG-2847-004", "Leakage",      "Oil Consumption",  0.021, 0.025, "L/h", "PASS", now - 3*3600),
        ("ENG-2847-004", "Vibration",    "Overall Level",    1.8,   2.0,   "g",   "PASS", now - 3*3600),
    ]
    conn.executemany(
        "INSERT INTO qa_test_results(serial_number,test_type,parameter,measured,limit_value,unit,result,ts) VALUES(?,?,?,?,?,?,?,?)",
        test_rows
    )

    # Process parameters at STN-03
    params = [
        ("ENG-2847-001", "STN-03", 1200, 0.08, 3.2, 4.8, 142, now - 2*3600),
        ("ENG-2847-007", "STN-03", 1200, 0.08, 3.1, 4.7, 144, now - 1*3600),
        ("ENG-2847-004", "STN-03", 1200, 0.08, 5.8, 8.2, 138, now - 6*3600),  # good run — different lot
    ]
    conn.executemany(
        "INSERT INTO qa_process_params(serial_number,station,spindle_rpm,feed_mm_min,coolant_pct,coolant_lpm,cycle_time_s,ts) "
        "VALUES(?,?,?,?,?,?,?,?)", params
    )

    # Tooling history — BORE-H-047 at STN-03, tool worn beyond change limit
    conn.execute(
        "INSERT INTO qa_tooling_history(station,tool_id,tool_name,life_pct_at_use,change_life_limit,last_change_days_ago,serial_numbers,ts) "
        "VALUES(?,?,?,?,?,?,?,?)",
        ("STN-03", "BORE-H-047", "CBN Hone Assembly", 97.0, 85.0, 34,
         "ENG-2847-001,ENG-2847-002,ENG-2847-003,ENG-2847-006,ENG-2847-007", now)
    )

    # Material certs
    certs = [
        ("LOT-MCR-4471", "Gray Iron ASTM A48-03 Class 30B", "Mahle GmbH",
         "218-242 HB (spec 210-250 HB)", "As-cast — no heat treatment", 1, "CERT-MCR-2024-4471"),
        ("LOT-MCR-4468", "Gray Iron ASTM A48-03 Class 30B", "Mahle GmbH",
         "225-238 HB (spec 210-250 HB)", "As-cast — no heat treatment", 1, "CERT-MCR-2024-4468"),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO qa_material_certs(lot_number,material_spec,supplier,hardness_hb,heat_treat,chemistry_ok,cert_number) "
        "VALUES(?,?,?,?,?,?,?)", certs
    )

    # Operator log — trainee at STN-03
    op_logs = [
        ("STN-03", "ENG-2847-001", "Mike Thornton",  "C", "Level 1 — supervised required", "Running unsupervised — supervisor on break 21:15–22:40", now - 2*3600),
        ("STN-03", "ENG-2847-007", "Mike Thornton",  "C", "Level 1 — supervised required", "Continued unsupervised operation", now - 1*3600),
        ("STN-03", "ENG-2847-004", "Sarah Johnson",  "B", "Level 3 — fully certified",     None, now - 6*3600),
    ]
    conn.executemany(
        "INSERT INTO qa_operator_log(station,serial_number,operator_name,shift,cert_level,deviation,ts) VALUES(?,?,?,?,?,?,?)",
        op_logs
    )

    # Machine maintenance — STN-03 overdue PM + coolant alarm dismissed
    maint = [
        ("STN-03", "PM",          "Scheduled 30-day PM completed",           45, "completed",  now - 45*86400),
        ("STN-03", "ALARM",       "Coolant system pressure low — dismissed",  2, "dismissed",  now - 2*86400),
        ("STN-03", "ALARM",       "Coolant concentration 3.2% (spec 5–8%) — dismissed by operator", 1, "dismissed", now - 86400),
    ]
    conn.executemany(
        "INSERT INTO qa_machine_maintenance(station,event_type,description,days_ago,status,ts) VALUES(?,?,?,?,?,?)",
        maint
    )

    # Engineering drawing
    conn.execute(
        "INSERT INTO qa_drawings(component,feature,nominal,usl,lsl,unit,revision,notes) VALUES(?,?,?,?,?,?,?,?)",
        ("ISX15 Compression Ring", "Ring End Gap", 0.30, 0.40, 0.20, "mm", "Rev C",
         "CRITICAL CHARACTERISTIC — no use-as-is permitted. Oversize gap causes high oil consumption and blow-by.")
    )

    # Failure knowledge graph — this exact failure happened in 2023
    conn.execute(
        "INSERT INTO qa_failure_kg(ncr_number,component,feature,defect_type,root_cause,corrective_action,closed_date,notes) "
        "VALUES(?,?,?,?,?,?,?,?)",
        ("NCR-2023-147", "ISX15 Compression Ring", "Ring End Gap", "ring_gap_oversize",
         "CBN Hone BORE-H-047 at 94% life (change limit was 90%) combined with coolant concentration 3.1% (spec 5–8%). "
         "Worn hone removes less material, increasing gap. Low coolant degrades surface finish and accelerates tool wear.",
         "Reduced hone tool life limit from 90% to 85%. Implemented daily coolant concentration checks. "
         "Added interlock: machine won't run if coolant concentration < 4.5%.",
         "2023-05-02",
         "SAME ROOT CAUSE PATTERN: tool wear + low coolant. Interlock may have been bypassed or not implemented at this station.")
    )

    # Similar components
    conn.execute(
        "INSERT INTO qa_similar_components(component,feature,similar,notes) VALUES(?,?,?,?)",
        ("ISX15 Compression Ring", "Ring End Gap",
         "QSX15 Compression Ring, X15 Performance Compression Ring",
         "All three use same ring geometry and STN-03 honing operation. If root cause is tooling/coolant at STN-03, all families affected.")
    )

    # Visual inspection log
    conn.execute(
        "INSERT INTO qa_visual_log(serial_number,station,inspector,findings,result,ts) VALUES(?,?,?,?,?,?)",
        ("ENG-2847-001", "STN-03", "AI Vision System",
         "Ring gap measurement 0.51mm. Piston ring surface finish acceptable. No visible burrs or chips.",
         "FAIL", now - 2*3600)
    )

    conn.commit()
    print("[QA] Seeded quality agent tables with demo data")


# ── Tool implementations ──────────────────────────────────────────────────────

def _get_inspection_result(station: str, feature: str, serial_number: str | None = None) -> dict:
    q = "SELECT serial_number,measured_value,usl,lsl,unit,result,inspector,ts FROM qa_inspection_results WHERE station=? AND feature LIKE ?"
    args = [station, f"%{feature}%"]
    if serial_number:
        q += " AND serial_number=?"
        args.append(serial_number)
    q += " ORDER BY ts DESC LIMIT 10"
    rows = [dict(r) for r in get_conn().execute(q, args).fetchall()]
    fails = [r for r in rows if r["result"] == "FAIL"]
    return {
        "station": station, "feature": feature,
        "records": rows, "total": len(rows),
        "failures": len(fails),
        "summary": f"{len(fails)} FAIL out of {len(rows)} inspections" if rows else "No records found"
    }


def _get_spc_chart(station: str, feature: str) -> dict:
    rows = [dict(r) for r in get_conn().execute(
        "SELECT subgroup_id,xbar,r_value,cpk,ts FROM qa_spc_data WHERE station=? AND feature LIKE ? ORDER BY subgroup_id",
        (station, f"%{feature}%")
    ).fetchall()]
    if not rows:
        return {"found": False, "message": f"No SPC data for {station} {feature}"}
    xbars = [r["xbar"] for r in rows]
    cpks  = [r["cpk"]  for r in rows]
    we_violations = []
    if len(xbars) >= 4 and all(x > sum(xbars)/len(xbars) for x in xbars[-4:]):
        we_violations.append("WE Rule 2: 4 of last 4 points above mean — process shift detected")
    if cpks[-1] < 1.0:
        we_violations.append(f"Cpk {cpks[-1]:.2f} below 1.0 — process not capable")
    return {
        "station": station, "feature": feature,
        "subgroups": rows,
        "current_cpk": cpks[-1],
        "cpk_trend": f"{cpks[0]:.2f} → {cpks[-1]:.2f} (degrading)" if cpks[-1] < cpks[0] else f"{cpks[0]:.2f} → {cpks[-1]:.2f}",
        "xbar_trend": f"{xbars[0]:.3f} → {xbars[-1]:.3f} mm (upward drift)" if xbars[-1] > xbars[0] else f"{xbars[0]:.3f} → {xbars[-1]:.3f}",
        "western_electric_violations": we_violations,
        "assessment": "SYSTEMATIC SHIFT — not random variation" if we_violations else "Within statistical control"
    }


def _get_test_results(serial_number: str) -> dict:
    rows = [dict(r) for r in get_conn().execute(
        "SELECT test_type,parameter,measured,limit_value,unit,result,ts FROM qa_test_results WHERE serial_number=?",
        (serial_number,)
    ).fetchall()]
    return {"serial_number": serial_number, "results": rows,
            "tests_run": len(rows), "all_pass": all(r["result"]=="PASS" for r in rows) if rows else None,
            "note": "No test results — engine not yet in test cell" if not rows else ""}


def _get_visual_inspection_log(serial_number: str | None = None, station: str | None = None) -> dict:
    q, args = "SELECT * FROM qa_visual_log WHERE 1=1", []
    if serial_number: q += " AND serial_number=?"; args.append(serial_number)
    if station:       q += " AND station=?";       args.append(station)
    rows = [dict(r) for r in get_conn().execute(q + " ORDER BY ts DESC LIMIT 10", args).fetchall()]
    return {"records": rows, "count": len(rows)}


def _get_gauge_calibration_status(station: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM qa_gauge_calibration WHERE station=?", (station,)
    ).fetchone()
    if not row:
        return {"found": False, "message": f"No gauge records for {station}"}
    d = dict(row)
    now = int(time.time())
    d["days_until_cal_due"] = round((d["cal_due_ts"] - now) / 86400, 0)
    d["assessment"] = (
        "ACCEPTABLE — within calibration, GR&R marginal but usable" if d["grr_pct"] < 30
        else "UNACCEPTABLE — GR&R > 30%, measurement system not capable"
    )
    return d


def _get_serial_number_history(serial_number: str) -> dict:
    insp = [dict(r) for r in get_conn().execute(
        "SELECT station,feature,measured_value,result,ts FROM qa_inspection_results WHERE serial_number=? ORDER BY ts",
        (serial_number,)
    ).fetchall()]
    ops  = [dict(r) for r in get_conn().execute(
        "SELECT station,operator_name,shift,deviation,ts FROM qa_operator_log WHERE serial_number=? ORDER BY ts",
        (serial_number,)
    ).fetchall()]
    params = [dict(r) for r in get_conn().execute(
        "SELECT station,coolant_pct,cycle_time_s,ts FROM qa_process_params WHERE serial_number=? ORDER BY ts",
        (serial_number,)
    ).fetchall()]
    loc = get_conn().execute("SELECT * FROM qa_engine_locations WHERE serial_number=?", (serial_number,)).fetchone()
    return {
        "serial_number": serial_number,
        "current_location": dict(loc) if loc else None,
        "inspection_history": insp,
        "operator_history": ops,
        "process_params": params
    }


def _get_material_lot_traceability(lot_number: str) -> dict:
    row = get_conn().execute("SELECT * FROM qa_material_lots WHERE lot_number=?", (lot_number,)).fetchone()
    if not row:
        return {"found": False, "message": f"Lot {lot_number} not found"}
    d = dict(row)
    serials = d["serial_numbers"].split(",") if d["serial_numbers"] else []
    d["serial_list"] = serials
    d["count"] = len(serials)
    return d


def _get_affected_population(station: str, hours_back: int = 8) -> dict:
    cutoff = int(time.time()) - hours_back * 3600
    rows = get_conn().execute(
        "SELECT DISTINCT serial_number FROM qa_inspection_results WHERE station=? AND ts>=? ORDER BY ts DESC",
        (station, cutoff)
    ).fetchall()
    serials = [r[0] for r in rows]
    return {
        "station": station,
        "hours_back": hours_back,
        "affected_serial_numbers": serials,
        "count": len(serials),
        "note": f"All serial numbers that passed through {station} in the last {hours_back}h"
    }


def _get_engine_location(serial_number: str) -> dict:
    row = get_conn().execute("SELECT * FROM qa_engine_locations WHERE serial_number=?", (serial_number,)).fetchone()
    return dict(row) if row else {"found": False, "serial_number": serial_number}


def _get_shipment_records(serial_number: str) -> dict:
    rows = [dict(r) for r in get_conn().execute(
        "SELECT * FROM qa_shipments WHERE serial_number=?", (serial_number,)
    ).fetchall()]
    return {
        "serial_number": serial_number,
        "shipped": len(rows) > 0,
        "records": rows,
        "warning": "FIELD ESCAPE RISK — engine is at customer site" if rows else None
    }


def _get_process_parameters(serial_number: str, station: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM qa_process_params WHERE serial_number=? AND station=?", (serial_number, station)
    ).fetchone()
    if not row:
        return {"found": False, "message": f"No process parameters for {serial_number} at {station}"}
    d = dict(row)
    d["coolant_assessment"] = (
        f"LOW — {d['coolant_pct']}% (spec 5–8%) — BELOW MINIMUM" if d["coolant_pct"] < 5.0
        else f"OK — {d['coolant_pct']}%"
    )
    return d


def _get_tooling_history(station: str, serial_number: str | None = None) -> dict:
    row = get_conn().execute(
        "SELECT * FROM qa_tooling_history WHERE station=? ORDER BY ts DESC LIMIT 1", (station,)
    ).fetchone()
    if not row:
        return {"found": False, "message": f"No tooling history for {station}"}
    d = dict(row)
    d["overdue_for_change"] = d["life_pct_at_use"] > d["change_life_limit"]
    d["assessment"] = (
        f"CRITICAL — tool at {d['life_pct_at_use']}% life, change limit is {d['change_life_limit']}%. "
        f"Tool should have been changed {round(d['life_pct_at_use'] - d['change_life_limit'], 0)}% ago."
        if d["overdue_for_change"] else "Within life limits"
    )
    return d


def _get_material_cert(lot_number: str) -> dict:
    row = get_conn().execute("SELECT * FROM qa_material_certs WHERE lot_number=?", (lot_number,)).fetchone()
    return dict(row) if row else {"found": False, "message": f"No cert for lot {lot_number}"}


def _get_operator_log(station: str, serial_number: str | None = None) -> dict:
    q = "SELECT * FROM qa_operator_log WHERE station=?"
    args = [station]
    if serial_number:
        q += " AND serial_number=?"
        args.append(serial_number)
    rows = [dict(r) for r in get_conn().execute(q + " ORDER BY ts DESC LIMIT 5", args).fetchall()]
    deviations = [r for r in rows if r.get("deviation")]
    return {
        "station": station, "records": rows,
        "deviations_found": len(deviations),
        "deviations": deviations,
        "alert": "DEVIATION LOGGED: Unsupervised Level-1 operator" if deviations else None
    }


def _get_maintenance_history(station: str) -> dict:
    rows = [dict(r) for r in get_conn().execute(
        "SELECT * FROM qa_machine_maintenance WHERE station=? ORDER BY ts DESC", (station,)
    ).fetchall()]
    dismissed_alarms = [r for r in rows if r["status"] == "dismissed"]
    overdue_pm = next((r for r in rows if r["event_type"] == "PM"), None)
    return {
        "station": station, "records": rows,
        "dismissed_alarms": dismissed_alarms,
        "pm_overdue": (overdue_pm["days_ago"] > 30) if overdue_pm else False,
        "last_pm_days_ago": overdue_pm["days_ago"] if overdue_pm else None,
        "assessment": (
            f"WARNING — PM overdue by {overdue_pm['days_ago'] - 30} days. "
            f"{len(dismissed_alarms)} alarm(s) dismissed without corrective action."
            if (overdue_pm and overdue_pm["days_ago"] > 30) else "Maintenance current"
        )
    }


def _get_engineering_drawing(component: str, feature: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM qa_drawings WHERE component LIKE ? AND feature LIKE ?",
        (f"%{component}%", f"%{feature}%")
    ).fetchone()
    return dict(row) if row else {"found": False, "message": f"No drawing for {component} {feature}"}


def _query_failure_knowledge_graph(component: str, defect_type: str) -> dict:
    rows = [dict(r) for r in get_conn().execute(
        "SELECT * FROM qa_failure_kg WHERE (component LIKE ? OR defect_type LIKE ?) ORDER BY closed_date DESC LIMIT 5",
        (f"%{component}%", f"%{defect_type}%")
    ).fetchall()]
    return {
        "matches": rows,
        "count": len(rows),
        "top_match": rows[0] if rows else None,
        "note": "PRECEDENT FOUND — same root cause pattern identified" if rows else "No historical match"
    }


def _get_similar_components(component: str, feature: str) -> dict:
    row = get_conn().execute(
        "SELECT * FROM qa_similar_components WHERE component LIKE ? AND feature LIKE ?",
        (f"%{component}%", f"%{feature}%")
    ).fetchone()
    return dict(row) if row else {"found": False, "message": "No similar components registered"}


# ── Write tools ───────────────────────────────────────────────────────────────

def _quarantine_serial_numbers(serial_numbers: list, reason: str, ncr_number: str | None = None) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_quarantine(serial_numbers,reason,ncr_number,quarantined_at) VALUES(?,?,?,?)",
        (",".join(serial_numbers), reason, ncr_number, ts)
    )
    for sn in serial_numbers:
        get_conn().execute(
            "UPDATE qa_engines SET status='quarantined' WHERE serial_number=?", (sn,)
        )
    get_conn().commit()
    return {"success": True, "quarantined": serial_numbers, "count": len(serial_numbers),
            "reason": reason, "confirmation": f"{len(serial_numbers)} serial number(s) placed on MES hold"}


def _place_operation_hold(station: str, machine: str, reason: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_operation_holds(station,machine,reason,placed_at) VALUES(?,?,?,?)",
        (station, machine, reason, ts)
    )
    get_conn().commit()
    return {"success": True, "station": station, "machine": machine,
            "confirmation": f"Operation hold placed on {station}. No new parts can enter until released."}


def _create_ncr(defect_description: str, affected_serial_numbers: list,
                severity: str, discovery_point: str, defect_code: str | None = None) -> dict:
    ts = int(time.time())
    ncr = f"NCR-{time.strftime('%Y')}-{ts % 10000:04d}"
    get_conn().execute(
        "INSERT INTO qa_ncrs(ncr_number,defect_description,serial_numbers,severity,discovery_point,defect_code,created_at) "
        "VALUES(?,?,?,?,?,?,?)",
        (ncr, defect_description, ",".join(affected_serial_numbers), severity, discovery_point, defect_code, ts)
    )
    get_conn().commit()
    return {"success": True, "ncr_number": ncr, "severity": severity,
            "affected_count": len(affected_serial_numbers), "status": "Open in QMS"}


def _create_capa(ncr_number: str, root_cause: str, corrective_action: str,
                 verification_plan: str, owner: str, due_date_days: int,
                 preventive_action: str | None = None) -> dict:
    ts = int(time.time())
    capa = f"CAPA-{time.strftime('%Y')}-{ts % 10000:04d}"
    due  = ts + due_date_days * 86400
    get_conn().execute(
        "INSERT INTO qa_capas(capa_number,ncr_number,root_cause,corrective_action,preventive_action,verification_plan,owner,due_date,created_at) "
        "VALUES(?,?,?,?,?,?,?,?,?)",
        (capa, ncr_number, root_cause, corrective_action, preventive_action, verification_plan, owner, due, ts)
    )
    get_conn().commit()
    return {"success": True, "capa_number": capa, "ncr_number": ncr_number,
            "owner": owner, "due_date": f"in {due_date_days} days", "status": "Open in QMS"}


def _trigger_100pct_inspection(serial_numbers: list, feature: str, reason: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_100pct(serial_numbers,feature,reason,created_at) VALUES(?,?,?,?)",
        (",".join(serial_numbers), feature, reason, ts)
    )
    get_conn().commit()
    return {"success": True, "serial_numbers": serial_numbers, "feature": feature,
            "confirmation": f"100% inspection flag set for {feature} on {len(serial_numbers)} unit(s)"}


def _disposition_parts(serial_numbers: list, ncr_number: str,
                       disposition: str, instructions: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_dispositions(serial_numbers,ncr_number,disposition,instructions,created_at) VALUES(?,?,?,?,?)",
        (",".join(serial_numbers), ncr_number, disposition, instructions, ts)
    )
    get_conn().commit()
    return {"success": True, "disposition": disposition, "serial_numbers": serial_numbers,
            "instructions": instructions, "confirmation": f"Disposition recorded in NCR {ncr_number}"}


def _release_hold(hold_type: str, reference: str, reason: str, evidence: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_hold_releases(hold_type,reference,reason,evidence,released_at) VALUES(?,?,?,?,?)",
        (hold_type, reference, reason, evidence, ts)
    )
    get_conn().commit()
    return {"success": True, "hold_type": hold_type, "reference": reference,
            "confirmation": f"{hold_type} hold on {reference} released. Evidence logged."}


def _notify_supplier(supplier: str, defect_description: str, lot_numbers: list,
                     ncr_number: str, response_due_days: int) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_supplier_notifs(supplier,defect_description,lot_numbers,ncr_number,response_due_days,sent_at) "
        "VALUES(?,?,?,?,?,?)",
        (supplier, defect_description, ",".join(lot_numbers), ncr_number, response_due_days, ts)
    )
    get_conn().commit()
    return {"success": True, "supplier": supplier, "ncr_number": ncr_number,
            "response_due": f"8D response required in {response_due_days} days",
            "channels": "Email + supplier portal", "confirmation": "Formal notification sent"}


def _notify_customer(customer: str, message: str, serial_numbers: list,
                     po_number: str | None = None) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_customer_notifs(customer,message,serial_numbers,po_number,status,created_at) VALUES(?,?,?,?,?,?)",
        (customer, message, ",".join(serial_numbers), po_number, "pending_human_approval", ts)
    )
    get_conn().commit()
    return {
        "success": True,
        "customer": customer,
        "status": "PENDING HUMAN APPROVAL — notification drafted but NOT sent",
        "note": "Quality Manager must review and approve before transmission to customer",
        "serial_numbers": serial_numbers
    }


def _update_control_plan(component: str, feature: str, reason: str, recommended_changes: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_control_plan_flags(component,feature,reason,recommended_changes,flagged_at) VALUES(?,?,?,?,?)",
        (component, feature, reason, recommended_changes, ts)
    )
    get_conn().commit()
    return {"success": True, "component": component, "feature": feature,
            "confirmation": "Control plan flagged for engineering review with recommended changes attached"}


def _set_enhanced_monitoring(station: str, feature: str, new_usl: float,
                              n_pieces: int, reason: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_enhanced_monitoring(station,feature,new_usl,n_pieces,reason,active,created_at) VALUES(?,?,?,?,?,1,?)",
        (station, feature, new_usl, n_pieces, reason, ts)
    )
    get_conn().commit()
    return {"success": True, "station": station, "feature": feature,
            "new_usl": new_usl, "applies_to": f"Next {n_pieces} pieces",
            "confirmation": f"Enhanced monitoring active — alert if {feature} > {new_usl}mm"}


def _notify_human(recipient: str, message: str, recommended_action: str, urgency: str) -> dict:
    ts = int(time.time())
    get_conn().execute(
        "INSERT INTO qa_human_escalations(recipient,message,recommended_action,urgency,sent_at) VALUES(?,?,?,?,?)",
        (recipient, message, recommended_action, urgency, ts)
    )
    get_conn().commit()
    return {"success": True, "recipient": recipient, "urgency": urgency,
            "channels": "Teams + SMS + email", "confirmation": f"Escalation sent to {recipient}"}


# ── Dispatcher ────────────────────────────────────────────────────────────────

_DISPATCH = {
    "get_inspection_result":       lambda i: _get_inspection_result(i["station"], i["feature"], i.get("serial_number")),
    "get_spc_chart":               lambda i: _get_spc_chart(i["station"], i["feature"]),
    "get_test_results":            lambda i: _get_test_results(i["serial_number"]),
    "get_visual_inspection_log":   lambda i: _get_visual_inspection_log(i.get("serial_number"), i.get("station")),
    "get_gauge_calibration_status":lambda i: _get_gauge_calibration_status(i["station"]),
    "get_serial_number_history":   lambda i: _get_serial_number_history(i["serial_number"]),
    "get_material_lot_traceability":lambda i: _get_material_lot_traceability(i["lot_number"]),
    "get_affected_population":     lambda i: _get_affected_population(i["station"], i.get("hours_back", 8)),
    "get_engine_location":         lambda i: _get_engine_location(i["serial_number"]),
    "get_shipment_records":        lambda i: _get_shipment_records(i["serial_number"]),
    "get_process_parameters":      lambda i: _get_process_parameters(i["serial_number"], i["station"]),
    "get_tooling_history":         lambda i: _get_tooling_history(i["station"], i.get("serial_number")),
    "get_material_cert":           lambda i: _get_material_cert(i["lot_number"]),
    "get_operator_log":            lambda i: _get_operator_log(i["station"], i.get("serial_number")),
    "get_maintenance_history":     lambda i: _get_maintenance_history(i["station"]),
    "get_engineering_drawing":     lambda i: _get_engineering_drawing(i["component"], i["feature"]),
    "query_failure_knowledge_graph":lambda i: _query_failure_knowledge_graph(i["component"], i["defect_type"]),
    "get_similar_components":      lambda i: _get_similar_components(i["component"], i["feature"]),
    "quarantine_serial_numbers":   lambda i: _quarantine_serial_numbers(i["serial_numbers"], i["reason"], i.get("ncr_number")),
    "place_operation_hold":        lambda i: _place_operation_hold(i["station"], i["machine"], i["reason"]),
    "create_ncr":                  lambda i: _create_ncr(i["defect_description"], i["affected_serial_numbers"], i["severity"], i["discovery_point"], i.get("defect_code")),
    "create_capa":                 lambda i: _create_capa(i["ncr_number"], i["root_cause"], i["corrective_action"], i["verification_plan"], i["owner"], i["due_date_days"], i.get("preventive_action")),
    "trigger_100pct_inspection":   lambda i: _trigger_100pct_inspection(i["serial_numbers"], i["feature"], i["reason"]),
    "disposition_parts":           lambda i: _disposition_parts(i["serial_numbers"], i["ncr_number"], i["disposition"], i["instructions"]),
    "release_hold":                lambda i: _release_hold(i["hold_type"], i["reference"], i["reason"], i["evidence"]),
    "notify_supplier":             lambda i: _notify_supplier(i["supplier"], i["defect_description"], i["lot_numbers"], i["ncr_number"], i["response_due_days"]),
    "notify_customer":             lambda i: _notify_customer(i["customer"], i["message"], i["serial_numbers"], i.get("po_number")),
    "update_control_plan":         lambda i: _update_control_plan(i["component"], i["feature"], i["reason"], i["recommended_changes"]),
    "set_enhanced_monitoring":     lambda i: _set_enhanced_monitoring(i["station"], i["feature"], i["new_usl"], i["n_pieces"], i["reason"]),
    "notify_human":                lambda i: _notify_human(i["recipient"], i["message"], i["recommended_action"], i["urgency"]),
}


# ── Agent loop ────────────────────────────────────────────────────────────────

async def run_quality_agent(station: str, defect_type: str, detail: str,
                             confidence: float, api_key: str):
    """Agentic quality investigation loop. Yields SSE strings."""
    import anthropic as _ant

    client = _ant.Anthropic(api_key=api_key)
    loop   = asyncio.get_event_loop()

    initial = (
        f"QUALITY SIGNAL DETECTED\n\n"
        f"Station  : {station}\n"
        f"Defect   : {defect_type}\n"
        f"Detail   : {detail}\n"
        f"CNN Confidence: {confidence:.0f}%\n\n"
        f"Follow your 7-step reasoning framework. Characterize the defect, scope the "
        f"affected population, contain immediately, find root cause, correct, verify, and learn. "
        f"Show your reasoning at every step."
    )

    messages = [{"role": "user", "content": initial}]

    for _ in range(20):
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
