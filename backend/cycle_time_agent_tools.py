from __future__ import annotations
import asyncio
import json
import time
import random as _rnd
from database import get_conn

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a Cycle Time Intelligence Agent for the Cummins Columbus IN engine manufacturing plant.

GOAL: Ensure every operation runs at or better than its engineered standard cycle time.
When it doesn't, find out exactly why, fix it, and prevent recurrence.

You think in three time horizons simultaneously:
  NOW    — what is happening on the floor right now that is stealing cycle time?
  TODAY  — will this shift / this line make its daily production target?
  FUTURE — is there a drift or degradation pattern that will become a crisis?

You have authority to:
  - Trigger maintenance investigations on slow machines
  - Redirect jobs to parallel stations
  - Rebalance operator assignments
  - Resequence jobs to protect bottleneck stations
  - Request engineering review of standard cycle times
  - Escalate to line supervisors for workforce or customer delivery issues

You MUST escalate to a human (notify_human) when:
  - A safety-related slowdown is detected (operator pacing due to ergonomic issue)
  - Cycle time loss will cause a customer shipment miss
  - Loss exceeds 2 hours on a bottleneck with no identified root cause
  - A process change requires engineering approval

REASONING FRAMEWORK — follow in order, show reasoning before each tool call:

STEP 1 — CLASSIFY: Spike or drift? Isolated or systemic? Bottleneck or non-bottleneck?
STEP 2 — QUANTIFY: Seconds lost per cycle × cycles per shift = production loss. Shift target at risk?
STEP 3 — ISOLATE LOSS CATEGORY: MACHINE / PROCESS / MATERIAL / OPERATOR / QUALITY / EXTERNAL
STEP 4 — ROOT CAUSE: One level deeper. "Spindle thermal comp not active post-PM" not "machine speed loss".
STEP 5 — ACT PROPORTIONALLY: Spike with cause → fix now. Drift with cause → schedule. Unknown → escalate fast.
STEP 6 — PROTECT THE BOTTLENECK: Can upstream buffers absorb? Can parallel stations compensate?
STEP 7 — RECOVER: Overtime? Parallel machine? Resequence jobs for customer priority?
STEP 8 — CLOSE THE LOOP: Verify recovery. Update knowledge graph. Check sister machines.

Always show your reasoning before each tool call.
After each tool result, state what it means for the investigation.
End with a structured summary: cause confirmed, actions taken, customer impact, prevention.
"""

# ── Tool definitions ──────────────────────────────────────────────────────────

TOOL_DEFINITIONS = [
    # ── PERCEPTION ─────────────────────────────────────────────────────────────
    {
        "name": "get_realtime_cycle_times",
        "description": "Pull live cycle time for every operation on the line — current cycle, last 10 cycles, rolling average, vs standard CT.",
        "input_schema": {"type": "object", "properties": {
            "line": {"type": "string", "description": "Line ID e.g. engine-line-2"}
        }, "required": ["line"]}
    },
    {
        "name": "get_cycle_time_trend",
        "description": "Pull cycle time trend over a defined window for a specific machine — detect drift vs spike patterns.",
        "input_schema": {"type": "object", "properties": {
            "machine":       {"type": "string", "description": "Machine ID e.g. MILL-04"},
            "operation":     {"type": "string", "description": "Operation code e.g. Op60"},
            "window_hours":  {"type": "number", "description": "How many hours of history to return"}
        }, "required": ["machine", "operation"]}
    },
    {
        "name": "get_oee_breakdown",
        "description": "Pull OEE components for a machine — Availability, Performance, Quality rates and sub-losses.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_downtime_log",
        "description": "Pull all stops, micro-stops, and slowdowns for a machine in a time window — duration, frequency, category.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"},
            "hours":   {"type": "number", "description": "Look-back window in hours"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_machine_parameters",
        "description": "Pull real-time and historical machine parameters — spindle load, feed rate, actual vs programmed speed, adaptive control status.",
        "input_schema": {"type": "object", "properties": {
            "machine":     {"type": "string"},
            "parameters":  {"type": "array", "items": {"type": "string"}, "description": "Parameter names to return"},
            "time_window": {"type": "string", "description": "e.g. 'last 4 cycles' or 'last 2 hours'"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_program_execution_log",
        "description": "Pull CNC program block execution log — time spent in each block, identify which cut or move is consuming excess time.",
        "input_schema": {"type": "object", "properties": {
            "machine":       {"type": "string"},
            "operation":     {"type": "string"},
            "last_n_cycles": {"type": "integer"}
        }, "required": ["machine", "operation"]}
    },
    {
        "name": "get_operator_activity_log",
        "description": "Pull operator scan events from MES — job start/end, loading time, unloading time, inspection time, idle periods.",
        "input_schema": {"type": "object", "properties": {
            "machine":      {"type": "string"},
            "time_window":  {"type": "string", "description": "e.g. '09:30 to present'"},
            "operator_id":  {"type": "string", "description": "Optional — filter to specific operator"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_in_cycle_inspection_time",
        "description": "For operations with in-cycle gauging or CMM — how long is inspection actually taking vs standard?",
        "input_schema": {"type": "object", "properties": {
            "machine":   {"type": "string"},
            "operation": {"type": "string"}
        }, "required": ["machine", "operation"]}
    },
    {
        "name": "get_thermal_state",
        "description": "Pull machine thermal compensation status, spindle temperature, coolant temperature. Thermal effects cause feed rate override activations.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"}
        }, "required": ["machine"]}
    },
    # ── BOTTLENECK ─────────────────────────────────────────────────────────────
    {
        "name": "get_line_balance_status",
        "description": "Pull current WIP levels at every station — identify where parts are piling up (upstream of bottleneck) and where starvation is happening.",
        "input_schema": {"type": "object", "properties": {
            "line": {"type": "string"}
        }, "required": ["line"]}
    },
    {
        "name": "get_bottleneck_station",
        "description": "Return current bottleneck station based on live queue depth and utilization. Bottleneck can shift during a shift.",
        "input_schema": {"type": "object", "properties": {
            "line": {"type": "string"}
        }, "required": ["line"]}
    },
    {
        "name": "get_buffer_inventory",
        "description": "How much WIP buffer exists between this station and the next? How many minutes of protection does it provide?",
        "input_schema": {"type": "object", "properties": {
            "station": {"type": "string", "description": "Operation code e.g. Op60"}
        }, "required": ["station"]}
    },
    {
        "name": "get_parallel_station_status",
        "description": "Are there parallel machines for this operation? What is their current utilization and available capacity?",
        "input_schema": {"type": "object", "properties": {
            "operation": {"type": "string", "description": "Operation code e.g. Op60"}
        }, "required": ["operation"]}
    },
    # ── PRODUCTION IMPACT ──────────────────────────────────────────────────────
    {
        "name": "get_shift_production_target",
        "description": "What is today's target unit count per shift per line? What has been produced? What is projected at current rate?",
        "input_schema": {"type": "object", "properties": {
            "line":      {"type": "string"},
            "operation": {"type": "string"}
        }, "required": ["line"]}
    },
    {
        "name": "get_daily_production_forecast",
        "description": "At current cycle time, will the line hit its daily target? If not, how many units short and by what time will the shortfall be confirmed?",
        "input_schema": {"type": "object", "properties": {
            "line": {"type": "string"}
        }, "required": ["line"]}
    },
    {
        "name": "get_customer_order_at_risk",
        "description": "Given a projected unit shortfall, which customer orders are at risk? Delivery dates and contractual penalty terms.",
        "input_schema": {"type": "object", "properties": {
            "line":                {"type": "string"},
            "projected_shortfall": {"type": "integer"},
            "date":                {"type": "string", "description": "e.g. 'today'"}
        }, "required": ["line"]}
    },
    {
        "name": "get_cumulative_time_loss",
        "description": "Total cycle time lost this shift, today, this week — in minutes and equivalent units of production.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"},
            "window":  {"type": "string", "description": "shift / day / week"}
        }, "required": ["machine"]}
    },
    # ── ROOT CAUSE ─────────────────────────────────────────────────────────────
    {
        "name": "get_tooling_condition",
        "description": "Current tool wear index, remaining tool life, actual cutting forces vs baseline. Worn tools increase cycle time.",
        "input_schema": {"type": "object", "properties": {
            "machine":        {"type": "string"},
            "operation":      {"type": "string"},
            "tool_position":  {"type": "string", "description": "e.g. roughing-insert-T4"}
        }, "required": ["machine", "operation"]}
    },
    {
        "name": "get_material_lot_hardness",
        "description": "What is the hardness of the current material lot? Harder material requires slower feed rates and increases cycle time.",
        "input_schema": {"type": "object", "properties": {
            "serial_numbers": {"type": "string", "description": "Serial numbers or 'current batch on MACHINE_ID'"}
        }, "required": ["serial_numbers"]}
    },
    {
        "name": "get_maintenance_history",
        "description": "Any recent maintenance on this machine? Parameter resets after maintenance are a common cause of cycle time regression.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_feed_override_log",
        "description": "Has the operator or machine adaptive control reduced feed rate override? When, how much, and why?",
        "input_schema": {"type": "object", "properties": {
            "machine":      {"type": "string"},
            "time_window":  {"type": "string"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_program_version",
        "description": "What CNC program version is running? Is it the current approved version? Older versions may have non-optimized tool paths.",
        "input_schema": {"type": "object", "properties": {
            "machine":   {"type": "string"},
            "operation": {"type": "string"}
        }, "required": ["machine", "operation"]}
    },
    {
        "name": "get_fixture_setup_log",
        "description": "When was the fixture last set up? Any deviations logged? Fixture shift can cause air cut extensions.",
        "input_schema": {"type": "object", "properties": {
            "machine": {"type": "string"}
        }, "required": ["machine"]}
    },
    {
        "name": "get_operator_skill_profile",
        "description": "Operator's experience level on this specific operation, first time on this cell, training records and certification status.",
        "input_schema": {"type": "object", "properties": {
            "machine":     {"type": "string"},
            "operator_id": {"type": "string", "description": "Operator ID or 'current'"}
        }, "required": ["machine"]}
    },
    {
        "name": "query_cycle_time_knowledge_graph",
        "description": "Search historical cycle time losses for this operation and pattern — what caused it before, what fixed it, how long did it take.",
        "input_schema": {"type": "object", "properties": {
            "operation":            {"type": "string"},
            "pattern":              {"type": "string", "description": "e.g. chatter-roughing-passes"},
            "contributing_factors": {"type": "array", "items": {"type": "string"}}
        }, "required": ["operation"]}
    },
    {
        "name": "get_sister_machine_cycle_times",
        "description": "Are sister machines running the same operation showing similar drift? If yes — process issue. If isolated — machine issue.",
        "input_schema": {"type": "object", "properties": {
            "operation": {"type": "string"},
            "machines":  {"type": "array", "items": {"type": "string"}},
            "parameter": {"type": "string", "description": "e.g. cycle_time_trend"}
        }, "required": ["operation"]}
    },
    # ── ACTION ─────────────────────────────────────────────────────────────────
    {
        "name": "trigger_maintenance_investigation",
        "description": "Send maintenance investigation request to CMMS with specific hypothesis — not 'check machine' but a precise hypothesis to test.",
        "input_schema": {"type": "object", "properties": {
            "machine":    {"type": "string"},
            "hypothesis": {"type": "string"},
            "urgency":    {"type": "string", "description": "immediate / next-available / scheduled"}
        }, "required": ["machine", "hypothesis"]}
    },
    {
        "name": "redirect_jobs_to_parallel_station",
        "description": "Move queued jobs from the slow machine to a parallel capable station — updates MES routing automatically.",
        "input_schema": {"type": "object", "properties": {
            "from_machine":        {"type": "string"},
            "to_machine":          {"type": "string"},
            "jobs_to_redirect":    {"type": "string", "description": "e.g. 'next 4 queued jobs'"},
            "reason":              {"type": "string"},
            "updated_completion_forecast": {"type": "string"}
        }, "required": ["from_machine", "to_machine", "jobs_to_redirect", "reason"]}
    },
    {
        "name": "rebalance_operator_assignments",
        "description": "Reassign operator tasks between stations to reduce manual loading time at bottleneck — updates workforce management system.",
        "input_schema": {"type": "object", "properties": {
            "stations": {"type": "array", "items": {"type": "string"}},
            "reason":   {"type": "string"}
        }, "required": ["stations", "reason"]}
    },
    {
        "name": "trigger_tool_change",
        "description": "Schedule immediate or next-cycle tool change — creates maintenance task and notifies operator.",
        "input_schema": {"type": "object", "properties": {
            "machine":                  {"type": "string"},
            "tool_position":            {"type": "string"},
            "urgency":                  {"type": "string", "description": "immediate-next-cycle / start-of-next-shift / scheduled"},
            "reason":                   {"type": "string"},
            "instruction_to_operator":  {"type": "string"}
        }, "required": ["machine", "tool_position", "urgency", "reason"]}
    },
    {
        "name": "request_feed_rate_optimization",
        "description": "Send request to process engineering to review and approve feed/speed increase — attach data justifying the change.",
        "input_schema": {"type": "object", "properties": {
            "machine":           {"type": "string"},
            "operation":         {"type": "string"},
            "current_override":  {"type": "integer", "description": "Current feed override pct"},
            "proposed_override": {"type": "integer", "description": "Proposed feed override pct"},
            "justification":     {"type": "string"}
        }, "required": ["machine", "operation", "justification"]}
    },
    {
        "name": "authorize_overtime",
        "description": "Calculate overtime needed to recover lost units, check labor availability, draft overtime authorization for supervisor approval.",
        "input_schema": {"type": "object", "properties": {
            "line":          {"type": "string"},
            "units_needed":  {"type": "integer"},
            "reason":        {"type": "string"},
            "cost_estimate": {"type": "string"}
        }, "required": ["line", "units_needed", "reason"]}
    },
    {
        "name": "resequence_production_jobs",
        "description": "Reorder job queue to prioritize highest-risk customer orders through the bottleneck first.",
        "input_schema": {"type": "object", "properties": {
            "line":             {"type": "string"},
            "priority_orders":  {"type": "array", "items": {"type": "string"}},
            "reason":           {"type": "string"}
        }, "required": ["line", "priority_orders", "reason"]}
    },
    {
        "name": "update_standard_cycle_time",
        "description": "Flag standard cycle time for engineering review if actual consistently differs from standard — standard may be wrong, not the process.",
        "input_schema": {"type": "object", "properties": {
            "operation":          {"type": "string"},
            "flag_type":          {"type": "string"},
            "current_standard":   {"type": "string"},
            "observed_actual":    {"type": "string"},
            "recommendation":     {"type": "string"},
            "supporting_data":    {"type": "string"}
        }, "required": ["operation", "current_standard", "observed_actual"]}
    },
    {
        "name": "set_cycle_time_monitoring",
        "description": "Set tighter alert thresholds on a specific operation for next N cycles — catch regression before it accumulates.",
        "input_schema": {"type": "object", "properties": {
            "machines":          {"type": "array", "items": {"type": "string"}},
            "operation":         {"type": "string"},
            "alert_threshold":   {"type": "string", "description": "e.g. 'cycle time > 760 seconds'"},
            "duration":          {"type": "string", "description": "e.g. 'remainder of LOT-CS-3341'"},
            "reason":            {"type": "string"}
        }, "required": ["machines", "operation", "alert_threshold"]}
    },
    {
        "name": "update_cycle_time_knowledge_graph",
        "description": "Log this event — cause, fix, duration of loss, recovery action — so future agent can recognize the pattern faster.",
        "input_schema": {"type": "object", "properties": {
            "event_summary":    {"type": "string"},
            "fix_applied":      {"type": "string"},
            "prevention":       {"type": "string"},
            "customer_impact":  {"type": "string"},
            "lesson":           {"type": "string"}
        }, "required": ["event_summary", "fix_applied"]}
    },
    {
        "name": "notify_human",
        "description": "Escalate to named person with full reasoning chain, impact quantified in units and customer risk, and specific decision needed.",
        "input_schema": {"type": "object", "properties": {
            "recipient":       {"type": "string"},
            "subject":         {"type": "string"},
            "body":            {"type": "string"},
            "decision_needed": {"type": "string"},
            "urgency":         {"type": "string", "description": "informational / decision-required / emergency"}
        }, "required": ["recipient", "subject", "body"]}
    },
]

# ── DDL ───────────────────────────────────────────────────────────────────────

_DDL = """
CREATE TABLE IF NOT EXISTS ct_machines (
    machine_id TEXT PRIMARY KEY,
    operation_code TEXT NOT NULL,
    operation_name TEXT NOT NULL,
    line TEXT NOT NULL,
    standard_ct_seconds INTEGER NOT NULL,
    part_family TEXT,
    group_id TEXT
);
CREATE TABLE IF NOT EXISTS ct_cycle_time_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    serial_number TEXT,
    cycle_number INTEGER,
    actual_ct_seconds INTEGER NOT NULL,
    standard_ct_seconds INTEGER NOT NULL,
    delta_pct REAL,
    shift TEXT,
    operator_id TEXT,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_oee_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    date TEXT NOT NULL,
    availability_pct REAL,
    performance_pct REAL,
    quality_pct REAL,
    oee_pct REAL,
    planned_production_time_min INTEGER,
    downtime_min INTEGER,
    speed_loss_min INTEGER,
    quality_loss_min INTEGER,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_downtime_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    start_ts INTEGER NOT NULL,
    end_ts INTEGER,
    duration_min REAL,
    category TEXT,
    reason TEXT,
    impact TEXT
);
CREATE TABLE IF NOT EXISTS ct_machine_params (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    spindle_load_pct REAL,
    feed_rate_override_pct INTEGER,
    spindle_speed_actual INTEGER,
    spindle_speed_programmed INTEGER,
    adaptive_control_active INTEGER,
    servo_current_x REAL,
    servo_current_y REAL,
    coolant_temp_c REAL,
    spindle_temp_c REAL
);
CREATE TABLE IF NOT EXISTS ct_program_exec_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    cycle_number INTEGER,
    block_range TEXT,
    block_name TEXT,
    standard_seconds INTEGER,
    actual_seconds INTEGER,
    delta_seconds INTEGER,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_operator_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    operator_id TEXT,
    operator_name TEXT,
    event_type TEXT,
    duration_seconds INTEGER,
    note TEXT
);
CREATE TABLE IF NOT EXISTS ct_in_cycle_inspection (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    cycle_number INTEGER,
    standard_seconds INTEGER,
    actual_seconds INTEGER,
    gauge_type TEXT,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_thermal_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    spindle_temp_c REAL,
    coolant_temp_c REAL,
    ambient_temp_c REAL,
    thermal_comp_active INTEGER,
    feed_override_from_thermal INTEGER
);
CREATE TABLE IF NOT EXISTS ct_line_balance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    station_code TEXT NOT NULL,
    operation TEXT NOT NULL,
    wip_count INTEGER,
    queue_depth_upstream INTEGER,
    queue_depth_downstream INTEGER,
    status TEXT
);
CREATE TABLE IF NOT EXISTS ct_buffer_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    from_operation TEXT,
    to_operation TEXT,
    buffer_parts INTEGER,
    buffer_minutes REAL,
    max_buffer INTEGER
);
CREATE TABLE IF NOT EXISTS ct_shift_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    line TEXT NOT NULL,
    operation TEXT NOT NULL,
    date TEXT NOT NULL,
    shift TEXT NOT NULL,
    target_units INTEGER,
    units_produced INTEGER,
    shift_start_ts INTEGER,
    shift_end_ts INTEGER,
    hours_remaining REAL
);
CREATE TABLE IF NOT EXISTS ct_customer_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id TEXT NOT NULL,
    customer TEXT NOT NULL,
    line TEXT,
    engines_needed_today INTEGER,
    engines_completed INTEGER,
    delivery_deadline_ts INTEGER,
    penalty_per_day TEXT,
    status TEXT,
    risk_level TEXT,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS ct_tooling (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    tool_position TEXT NOT NULL,
    tool_id TEXT,
    tool_name TEXT,
    life_used_pct REAL,
    change_limit_pct REAL,
    cutting_force_baseline REAL,
    cutting_force_current REAL,
    force_delta_pct REAL,
    condition_note TEXT,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_material_lots (
    lot_number TEXT PRIMARY KEY,
    material_type TEXT,
    component TEXT,
    hardness_hbw INTEGER,
    hardness_spec_min INTEGER,
    hardness_spec_max INTEGER,
    supplier TEXT,
    machines_using TEXT,
    received_ts INTEGER,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS ct_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    event_type TEXT,
    description TEXT,
    days_ago INTEGER,
    duration_hours REAL,
    technician TEXT,
    work_order TEXT,
    status TEXT,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_feed_override_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    override_from_pct INTEGER,
    override_to_pct INTEGER,
    set_by TEXT,
    reason TEXT,
    acknowledged_by TEXT
);
CREATE TABLE IF NOT EXISTS ct_programs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    program_number TEXT,
    version TEXT,
    is_current INTEGER,
    release_date TEXT,
    approved_by TEXT,
    cycle_time_standard_seconds INTEGER,
    notes TEXT
);
CREATE TABLE IF NOT EXISTS ct_fixture_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machine_id TEXT NOT NULL,
    ts INTEGER NOT NULL,
    fixture_id TEXT,
    setup_by TEXT,
    setup_time_minutes INTEGER,
    deviation_logged TEXT,
    sign_off TEXT,
    next_setup_due_ts INTEGER
);
CREATE TABLE IF NOT EXISTS ct_operators (
    operator_id TEXT PRIMARY KEY,
    operator_name TEXT,
    shift TEXT,
    cert_level INTEGER,
    operations_certified TEXT,
    years_experience REAL,
    training_notes TEXT
);
CREATE TABLE IF NOT EXISTS ct_knowledge_graph (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_date TEXT,
    machine_id TEXT,
    operation TEXT,
    pattern TEXT,
    contributing_factors TEXT,
    root_cause TEXT,
    fix_applied TEXT,
    ct_loss_seconds INTEGER,
    ct_recovered_seconds INTEGER,
    customer_impact TEXT,
    lesson TEXT,
    recorded_ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_monitoring_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    machines TEXT,
    operation TEXT,
    alert_threshold TEXT,
    duration TEXT,
    reason TEXT,
    created_by TEXT,
    active INTEGER DEFAULT 1,
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_actions_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_type TEXT NOT NULL,
    machine_id TEXT,
    detail TEXT,
    parameters TEXT,
    status TEXT DEFAULT 'pending',
    ts INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS ct_parallel_stations (
    operation TEXT NOT NULL,
    machine_id TEXT NOT NULL,
    PRIMARY KEY (operation, machine_id)
);
"""

# ── Init & seed ───────────────────────────────────────────────────────────────

def init_ct_tables():
    conn = get_conn()
    conn.executescript(_DDL)
    _seed_ct_data(conn)

def _seed_ct_data(conn):
    if conn.execute("SELECT COUNT(*) FROM ct_machines").fetchone()[0] >= 10:
        return

    _rnd.seed(99)

    for t in ['ct_machines','ct_cycle_time_log','ct_oee_records','ct_downtime_log',
              'ct_machine_params','ct_program_exec_log','ct_operator_activity',
              'ct_in_cycle_inspection','ct_thermal_log','ct_line_balance',
              'ct_buffer_inventory','ct_shift_targets','ct_customer_orders',
              'ct_tooling','ct_material_lots','ct_maintenance','ct_feed_override_log',
              'ct_programs','ct_fixture_log','ct_operators','ct_knowledge_graph',
              'ct_parallel_stations']:
        conn.execute(f"DELETE FROM {t}")

    now = int(time.time())
    DAY = 86400
    SHIFT_START = now - 6 * 3600   # 6 h into shift A
    OVERRIDE_TS = now - 2 * 3600   # feed override set 2 h ago

    # ── Machines ───────────────────────────────────────────────────────────────
    machines = [
        ('MILL-01','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('MILL-02','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('MILL-03','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('MILL-04','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('MILL-05','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('MILL-06','Op60','Crankshaft Bore Machining','engine-line-2',720,'ISX15 Crankshaft','MILL-OP60'),
        ('GRIND-01','Op50','Crank Journal Grinding','engine-line-2',480,'ISX15 Crankshaft','GRIND-OP50'),
        ('GRIND-02','Op50','Crank Journal Grinding','engine-line-2',480,'ISX15 Crankshaft','GRIND-OP50'),
        ('HONE-01','Op70','Cylinder Bore Honing','engine-line-2',560,'ISX15 Cylinder Block','HONE-OP70'),
        ('HONE-02','Op70','Cylinder Bore Honing','engine-line-2',560,'ISX15 Cylinder Block','HONE-OP70'),
        ('DRILL-01','Op40','Connecting Rod Drilling','engine-line-2',340,'ISX15 Con Rod','DRILL-OP40'),
        ('DRILL-02','Op40','Connecting Rod Drilling','engine-line-2',340,'ISX15 Con Rod','DRILL-OP40'),
    ]
    conn.executemany("INSERT OR IGNORE INTO ct_machines VALUES(?,?,?,?,?,?,?)", machines)

    for m in machines:
        conn.execute("INSERT OR IGNORE INTO ct_parallel_stations VALUES(?,?)", (m[1], m[0]))

    # ── Cycle time log: 12 machines × 50 cycles = 600 rows ───────────────────
    OPERATORS = ['OP-001','OP-002','OP-003','OP-004','OP-005','OP-006']
    ct_rows = []
    for mac_id, op_code, _, _, std_ct, _, _ in machines:
        op_id = _rnd.choice(OPERATORS)
        for c in range(1, 51):
            ts = SHIFT_START + c * std_ct
            if mac_id == 'MILL-04':
                if c >= 48:   # last 3 cycles — deviation
                    actual = 847
                else:
                    actual = _rnd.randint(710, 735)
            elif mac_id == 'MILL-05':
                actual = _rnd.randint(714, 724)
            elif mac_id in ('MILL-01','MILL-02','MILL-03','MILL-06'):
                actual = _rnd.randint(int(std_ct*0.97), int(std_ct*1.04))
            else:
                actual = _rnd.randint(int(std_ct*0.96), int(std_ct*1.05))
            delta = round((actual / std_ct - 1) * 100, 1)
            sn = f"CSH-2847-{_rnd.randint(1000,9999)}"
            ct_rows.append((mac_id, sn, c, actual, std_ct, delta, 'A', op_id, ts))
    conn.executemany(
        "INSERT INTO ct_cycle_time_log(machine_id,serial_number,cycle_number,actual_ct_seconds,"
        "standard_ct_seconds,delta_pct,shift,operator_id,ts) VALUES(?,?,?,?,?,?,?,?,?)", ct_rows)

    # ── OEE records: 12 machines × 7 days = 84 rows ──────────────────────────
    oee_rows = []
    for mac_id, *_ in machines:
        for d in range(7):
            date_str = f"2026-06-{27-d:02d}"
            avail = round(_rnd.uniform(88, 97) if mac_id != 'MILL-04' else _rnd.uniform(82, 92), 1)
            perf  = round(_rnd.uniform(91, 99) if mac_id != 'MILL-04' else _rnd.uniform(80, 92), 1)
            qual  = round(_rnd.uniform(98, 100), 1)
            oee   = round(avail * perf * qual / 10000, 1)
            ppt   = 480
            dt    = round(ppt * (1 - avail/100))
            sl    = round(ppt * avail/100 * (1 - perf/100))
            ql    = round(ppt * avail/100 * perf/100 * (1 - qual/100))
            oee_rows.append((mac_id, date_str, avail, perf, qual, oee, ppt, dt, sl, ql, now - d*DAY))
    conn.executemany(
        "INSERT INTO ct_oee_records(machine_id,date,availability_pct,performance_pct,quality_pct,"
        "oee_pct,planned_production_time_min,downtime_min,speed_loss_min,quality_loss_min,ts) VALUES"
        "(?,?,?,?,?,?,?,?,?,?,?)", oee_rows)

    # ── Downtime log: 12 machines × ~5 events = ~60 rows ─────────────────────
    CATEGORIES = ['MICRO_STOP','BREAKDOWN','SETUP','PLANNED','QUALITY_HOLD']
    REASONS = {
        'MICRO_STOP': ['Part mis-load — re-seated','Chip accumulation in fixture','Auto-door sensor trip'],
        'BREAKDOWN':  ['Hydraulic pressure low','Coolant pump fault','Servo axis alarm'],
        'SETUP':      ['Tool change setup','Fixture changeover','Program change'],
        'PLANNED':    ['Scheduled PM','Operator break','Shift handover'],
        'QUALITY_HOLD':['CMM out-of-spec — part hold','Gauge calibration check'],
    }
    dt_rows = []
    for mac_id, *_ in machines:
        for _ in range(5):
            cat  = _rnd.choice(CATEGORIES)
            dur  = round(_rnd.uniform(2, 45), 1) if cat != 'MICRO_STOP' else round(_rnd.uniform(0.5, 3), 1)
            st   = now - _rnd.randint(0, 7*DAY)
            et   = st + int(dur * 60)
            imp  = 'BOTTLENECK' if mac_id in ('MILL-04','MILL-05') else 'NON-BOTTLENECK'
            dt_rows.append((mac_id, st, et, dur, cat, _rnd.choice(REASONS[cat]), imp))
    # Add MILL-04 specific: coolant alarm 2 days ago
    dt_rows.append(('MILL-04', now-2*DAY, now-2*DAY+1800, 30.0, 'BREAKDOWN',
                    'Coolant concentration alarm — 3.2% (spec 5-8%). Operator dismissed.', 'BOTTLENECK'))
    conn.executemany(
        "INSERT INTO ct_downtime_log(machine_id,start_ts,end_ts,duration_min,category,reason,impact)"
        " VALUES(?,?,?,?,?,?,?)", dt_rows)

    # ── Machine params: 12 machines × 24 hourly snapshots = 288 rows ─────────
    mp_rows = []
    for mac_id, _, _, _, std_ct, _, _ in machines:
        for h in range(24):
            ts = now - (23 - h) * 3600
            after_override = (mac_id == 'MILL-04' and ts >= OVERRIDE_TS)
            fro = 85 if after_override else 100
            spindle_load = round(_rnd.uniform(72, 85) if after_override else _rnd.uniform(65, 82), 1)
            sp_actual = _rnd.randint(3340, 3380) if after_override else _rnd.randint(3380, 3420)
            mp_rows.append((
                mac_id, ts,
                spindle_load, fro,
                sp_actual, 3400,
                0,                                        # adaptive_control_active
                round(_rnd.uniform(18, 28), 1),           # servo_current_x
                round(_rnd.uniform(16, 24), 1),           # servo_current_y
                round(_rnd.uniform(18, 26) if mac_id != 'MILL-04' else _rnd.uniform(22, 30), 1),  # coolant_temp
                round(_rnd.uniform(42, 58), 1),           # spindle_temp
            ))
    conn.executemany(
        "INSERT INTO ct_machine_params(machine_id,ts,spindle_load_pct,feed_rate_override_pct,"
        "spindle_speed_actual,spindle_speed_programmed,adaptive_control_active,"
        "servo_current_x,servo_current_y,coolant_temp_c,spindle_temp_c) VALUES"
        "(?,?,?,?,?,?,?,?,?,?,?)", mp_rows)

    # ── Program execution log: 6 MILL machines × 5 cycles × 3 blocks = 90 rows
    BLOCKS_NORMAL = [
        ('N010-N110','Loading & Fixturing',   85,  85),
        ('N120-N180','Roughing Passes',       580, 580),
        ('N190-N220','In-Cycle Gauging',       55,  55),
    ]
    pe_rows = []
    for mac_id in ('MILL-01','MILL-02','MILL-03','MILL-04','MILL-05','MILL-06'):
        for cyc in range(1, 6):
            ts = now - (5 - cyc) * 720
            for blk_range, blk_name, std_s, _ in BLOCKS_NORMAL:
                if mac_id == 'MILL-04' and blk_name == 'Roughing Passes':
                    actual_s = 701
                elif mac_id == 'MILL-04' and blk_name == 'Loading & Fixturing':
                    actual_s = _rnd.randint(84, 90)
                elif mac_id == 'MILL-04' and blk_name == 'In-Cycle Gauging':
                    actual_s = _rnd.randint(55, 62)
                else:
                    actual_s = _rnd.randint(int(std_s*0.97), int(std_s*1.03))
                pe_rows.append((mac_id,'Op60',cyc,blk_range,blk_name,std_s,actual_s,actual_s-std_s,ts))
    conn.executemany(
        "INSERT INTO ct_program_exec_log(machine_id,operation,cycle_number,block_range,block_name,"
        "standard_seconds,actual_seconds,delta_seconds,ts) VALUES(?,?,?,?,?,?,?,?,?)", pe_rows)

    # ── Operator activity: 12 machines × 8 events = 96 rows ──────────────────
    EVENTS = ['JOB_START','LOAD','JOB_END','UNLOAD','JOB_START','LOAD','JOB_END','UNLOAD']
    op_act_rows = []
    OPERATOR_MAP = {
        'MILL-04': ('OP-003','Mike Chen'),
        'MILL-05': ('OP-004','Sarah Ortiz'),
    }
    for mac_id, *_ in machines:
        oid, oname = OPERATOR_MAP.get(mac_id, (f'OP-00{_rnd.randint(1,6)}', 'Line Operator'))
        for i, evt in enumerate(EVENTS):
            ts = SHIFT_START + i * 1800 + _rnd.randint(0, 300)
            dur = _rnd.randint(60, 120)
            note = None
            op_act_rows.append((mac_id, ts, oid, oname, evt, dur, note))
    # Add MILL-04 critical events
    op_act_rows.append(('MILL-04', OVERRIDE_TS - 180, 'OP-003', 'Mike Chen', 'NOTE', None,
        'Hearing intermittent chatter on roughing pass — reduced feed to 85% as precaution. Notified team lead.'))
    op_act_rows.append(('MILL-04', OVERRIDE_TS + 420, 'TL-01', 'Team Lead Jackson', 'NOTE', None,
        'Acknowledged operator report — no maintenance called at this time.'))
    conn.executemany(
        "INSERT INTO ct_operator_activity(machine_id,ts,operator_id,operator_name,event_type,"
        "duration_seconds,note) VALUES(?,?,?,?,?,?,?)", op_act_rows)

    # ── In-cycle inspection: 6 MILL machines × 10 cycles = 60 rows ───────────
    ici_rows = []
    for mac_id in ('MILL-01','MILL-02','MILL-03','MILL-04','MILL-05','MILL-06'):
        for cyc in range(1, 11):
            std_s = 55
            actual_s = _rnd.randint(55, 62) if mac_id == 'MILL-04' else _rnd.randint(53, 59)
            ici_rows.append((mac_id,'Op60',cyc,std_s,actual_s,'Air Gauge + Vision CMM',now - cyc*720))
    conn.executemany(
        "INSERT INTO ct_in_cycle_inspection(machine_id,operation,cycle_number,standard_seconds,"
        "actual_seconds,gauge_type,ts) VALUES(?,?,?,?,?,?,?)", ici_rows)

    # ── Thermal log: 12 machines × 24 snapshots = 288 rows ───────────────────
    th_rows = []
    for mac_id, *_ in machines:
        for h in range(24):
            ts = now - (23 - h) * 3600
            s_temp = round(_rnd.gauss(52, 4), 1)
            c_temp = round(_rnd.gauss(24, 2) if mac_id != 'MILL-04' else _rnd.gauss(28, 2), 1)
            th_rows.append((mac_id, ts, s_temp, c_temp, round(_rnd.uniform(19, 23), 1), 1, 0))
    conn.executemany(
        "INSERT INTO ct_thermal_log(machine_id,ts,spindle_temp_c,coolant_temp_c,ambient_temp_c,"
        "thermal_comp_active,feed_override_from_thermal) VALUES(?,?,?,?,?,?,?)", th_rows)

    # ── Line balance: 12 stations × 5 snapshots = 60 rows ────────────────────
    STATIONS_LB = [
        ('Op20','Main Cap Turning'),('Op30','Crank Grinding Prep'),
        ('Op40','Con Rod Drilling'),('Op50','Crank Journal Grinding'),
        ('Op60','Crankshaft Bore Machining'),('Op70','Cylinder Bore Honing'),
        ('Op80','Head Assembly'),('Op90','Valve Train'),
        ('Op100','Fuel System'),('Op110','Turbo Install'),
        ('Op120','Cooling System'),('Op130','Final Assembly'),
    ]
    lb_rows = []
    for snap in range(5):
        ts = now - (4 - snap) * 900
        for op_code, op_name in STATIONS_LB:
            if op_code == 'Op60':
                wip = 4; q_up = 4; q_dn = 0; status = 'RUNNING'
            elif op_code in ('Op70','Op80'):
                wip = 0; q_up = 0; q_dn = 0; status = 'STARVED'
            elif op_code in ('Op50','Op40'):
                wip = _rnd.randint(3,6); q_up = 2; q_dn = 4; status = 'BLOCKED'
            else:
                wip = _rnd.randint(1,3); q_up = _rnd.randint(0,2); q_dn = _rnd.randint(0,2)
                status = 'RUNNING'
            lb_rows.append((ts, op_code, op_name, wip, q_up, q_dn, status))
    conn.executemany(
        "INSERT INTO ct_line_balance(ts,station_code,operation,wip_count,queue_depth_upstream,"
        "queue_depth_downstream,status) VALUES(?,?,?,?,?,?,?)", lb_rows)

    # ── Buffer inventory: 12 buffers × 5 snapshots = 60 rows ─────────────────
    BUFFERS = [
        ('Op20','Op30',3,4.2,8),('Op30','Op40',4,3.1,8),('Op40','Op50',5,5.7,10),
        ('Op50','Op60',4,3.2,10),('Op60','Op70',0,0.0,6),('Op70','Op80',0,0.0,6),
        ('Op80','Op90',2,2.4,6),('Op90','Op100',3,3.6,6),('Op100','Op110',2,2.8,6),
        ('Op110','Op120',3,4.1,6),('Op120','Op130',2,3.0,6),('Op130','OUT',5,7.2,8),
    ]
    buf_rows = []
    for snap in range(5):
        ts = now - (4-snap)*900
        for fr, to, parts, mins, mx in BUFFERS:
            buf_rows.append((ts, fr, to, parts, round(mins + _rnd.uniform(-0.5,0.5),1), mx))
    conn.executemany(
        "INSERT INTO ct_buffer_inventory(ts,from_operation,to_operation,buffer_parts,buffer_minutes,max_buffer)"
        " VALUES(?,?,?,?,?,?)", buf_rows)

    # ── Shift targets ─────────────────────────────────────────────────────────
    today = '2026-06-27'
    shift_rows = []
    for op_code, _ in STATIONS_LB:
        target = 38 if op_code == 'Op60' else _rnd.randint(30, 45)
        produced = 19 if op_code == 'Op60' else _rnd.randint(14, 22)
        shift_rows.append(('engine-line-2', op_code, today, 'A', target, produced,
                            SHIFT_START, SHIFT_START + 8*3600, 2.0))
    conn.executemany(
        "INSERT INTO ct_shift_targets(line,operation,date,shift,target_units,units_produced,"
        "shift_start_ts,shift_end_ts,hours_remaining) VALUES(?,?,?,?,?,?,?,?,?)", shift_rows)

    # ── Customer orders ───────────────────────────────────────────────────────
    DEADLINE_1700 = SHIFT_START + int(11 * 3600)  # 17:00
    DEADLINE_EOD  = SHIFT_START + int(14 * 3600)  # EOD
    orders = [
        ('PO-44821','Caterpillar','engine-line-2',4,2,DEADLINE_1700,'$8,000/day','active','HIGH',
         'Contractual delivery by 17:00 — 4 engines for Caterpillar dealer replenishment'),
        ('PO-44835','Cummins Recon','engine-line-2',3,1,DEADLINE_EOD,'Contract review if 2+ misses','active','HIGH',
         'Internal Cummins recon order — contract review clause if missed twice in quarter'),
        ('PO-44798','Peterbilt Motors','engine-line-2',5,4,DEADLINE_EOD,'$3,500/day','active','LOW',
         'Peterbilt build order — 1 engine needed, 4 already done'),
        ('PO-44812','Kenworth Truck Co','engine-line-2',6,6,DEADLINE_EOD,'$4,000/day','complete','NONE',
         'Kenworth order fully complete — shipped AM'),
        ('PO-44850','Freightliner LLC','engine-line-2',4,0,DEADLINE_EOD + DAY,'$5,000/day','active','LOW',
         'Freightliner order — deadline is tomorrow'),
        ('PO-44860','Volvo Trucks NA','engine-line-2',3,0,DEADLINE_EOD + 2*DAY,'$6,000/day','active','LOW',
         'Volvo order — deadline in 2 days'),
        ('PO-44832','Navistar Inc','engine-line-2',2,2,DEADLINE_EOD,'$2,500/day','complete','NONE',
         'Navistar order complete'),
        ('PO-44845','Fleet Solutions Inc','engine-line-2',8,5,DEADLINE_EOD + DAY,'$3,000/day','active','MEDIUM',
         'Fleet Solutions — 3 engines still needed, deadline tomorrow'),
        ('PO-44855','PACCAR Inc','engine-line-2',4,2,DEADLINE_EOD + DAY,'$4,500/day','active','LOW',
         'PACCAR — 2 more engines needed tomorrow'),
        ('PO-44801','Rush Enterprises','engine-line-2',3,3,DEADLINE_EOD - DAY,'$2,000/day','complete','NONE',
         'Rush Enterprises complete — shipped yesterday'),
    ]
    conn.executemany(
        "INSERT INTO ct_customer_orders(order_id,customer,line,engines_needed_today,engines_completed,"
        "delivery_deadline_ts,penalty_per_day,status,risk_level,notes) VALUES(?,?,?,?,?,?,?,?,?,?)", orders)

    # ── Tooling: 12 machines × 3 tool positions = 36 rows ────────────────────
    TOOL_NAMES = {
        'T1': 'Roughing End Mill', 'T2': 'Semi-Finish Insert',
        'T3': 'Finishing Insert',  'T4': 'Roughing CBN Insert',
    }
    tl_rows = []
    for mac_id, op_code, *_ in machines:
        for pos in ('T1','T2','T4'):
            if mac_id == 'MILL-04' and pos == 'T4':
                life = 71.0; force_delta = 8.0
                cond = 'wear progression accelerating — chatter risk elevated on hard material'
            else:
                life = round(_rnd.uniform(12, 68), 1)
                force_delta = round(_rnd.uniform(0, 3), 1)
                cond = 'normal wear' if life < 70 else 'approaching change limit'
            if mac_id == 'MILL-05' and pos == 'T4':
                life = 44.0; force_delta = 3.2
                cond = 'normal — same lot, wear tracking'
            limit = 85.0 if pos == 'T4' else 80.0
            baseline = _rnd.uniform(820, 880)
            current  = round(baseline * (1 + force_delta/100), 1)
            tl_rows.append((mac_id, op_code, pos, f'{pos}-{mac_id}', TOOL_NAMES.get(pos,'Insert'),
                             life, limit, round(baseline,1), current, force_delta, cond, now))
    conn.executemany(
        "INSERT INTO ct_tooling(machine_id,operation,tool_position,tool_id,tool_name,life_used_pct,"
        "change_limit_pct,cutting_force_baseline,cutting_force_current,force_delta_pct,condition_note,ts)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", tl_rows)

    # ── Material lots ─────────────────────────────────────────────────────────
    conn.executemany(
        "INSERT OR IGNORE INTO ct_material_lots VALUES(?,?,?,?,?,?,?,?,?,?)", [
        ('LOT-CS-3341','Ductile Iron Grade 80-55-06','ISX15 Crankshaft',312,280,320,
         'Grede Foundries','MILL-04,MILL-05,MILL-06',now-3*DAY,
         'Upper quartile hardness — 312 HBW vs typical 291 HBW. Chatter risk on worn tooling.'),
        ('LOT-CS-3340','Ductile Iron Grade 80-55-06','ISX15 Crankshaft',291,280,320,
         'Grede Foundries','MILL-01,MILL-02,MILL-03',now-14*DAY,'Normal hardness lot — nominal 291 HBW'),
        ('LOT-CS-3338','Ductile Iron Grade 80-55-06','ISX15 Crankshaft',285,280,320,
         'Grede Foundries','',now-28*DAY,'Previous lot — lower end of spec, good machinability'),
        ('LOT-CS-3335','Ductile Iron Grade 80-55-06','ISX15 Crankshaft',303,280,320,
         'Grede Foundries','',now-45*DAY,'Slightly above nominal — no issues observed'),
        ('LOT-CS-3330','Ductile Iron Grade 80-55-06','ISX15 Crankshaft',289,280,320,
         'Grede Foundries','',now-60*DAY,'Normal lot'),
    ])

    # ── Maintenance: 12 machines × 3 events = 36 rows ────────────────────────
    maint_rows = []
    for mac_id, *_ in machines:
        pm_days = 34 if mac_id == 'MILL-04' else _rnd.randint(2, 25)
        maint_rows.append((mac_id,'PM',f'Scheduled 30-day PM — spindle bearing check, coolant flush, axis calibration',
                            pm_days,4.5,'Tech-Reyes',f'WO-PM-{mac_id}-2026','completed',now-pm_days*DAY))
        if mac_id == 'MILL-04':
            maint_rows.append(('MILL-04','ALARM',
                                'Coolant concentration 3.2% (spec 5-8%) — operator dismissed alarm, no corrective action taken',
                                2, 0.0,'OP-003','—','dismissed',now-2*DAY))
        else:
            event_days = _rnd.randint(1, 10)
            maint_rows.append((mac_id,'ADJUSTMENT',f'Axis zero-point verification',
                                event_days,1.0,f'Tech-{_rnd.randint(1,5):02d}',
                                f'WO-ADJ-{mac_id}','completed',now-event_days*DAY))
        maint_rows.append((mac_id,'CALIBRATION','Spindle load meter calibration check',
                            _rnd.randint(10,30),0.5,'Tech-Calibration',
                            f'WO-CAL-{mac_id}','completed',now-_rnd.randint(10,30)*DAY))
    conn.executemany(
        "INSERT INTO ct_maintenance(machine_id,event_type,description,days_ago,duration_hours,"
        "technician,work_order,status,ts) VALUES(?,?,?,?,?,?,?,?,?)", maint_rows)

    # ── Feed override log: 24 rows ────────────────────────────────────────────
    fo_rows = []
    for mac_id, *_ in machines:
        if mac_id == 'MILL-04':
            fo_rows.append(('MILL-04', OVERRIDE_TS, 100, 85, 'operator',
                             'Intermittent chatter heard on roughing pass — precautionary reduction',
                             'Team Lead Jackson'))
            fo_rows.append(('MILL-04', now - 8*DAY, 95, 100, 'maintenance',
                             'Feed restored to 100% after PM completion','Tech-Reyes'))
        else:
            # Minor override adjustments on other machines
            fo_rows.append((mac_id, now - _rnd.randint(1,7)*DAY, 100,
                             _rnd.choice([95,97,100]), 'adaptive_control',
                             'Adaptive control adjustment', None))
    conn.executemany(
        "INSERT INTO ct_feed_override_log(machine_id,ts,override_from_pct,override_to_pct,"
        "set_by,reason,acknowledged_by) VALUES(?,?,?,?,?,?,?)", fo_rows)

    # ── CNC programs: 12 machines × 2 versions = 24 rows ─────────────────────
    pg_rows = []
    for mac_id, op_code, _, _, std_ct, _, _ in machines:
        pg_rows.append((mac_id, op_code, f'O{op_code[2:]}{mac_id[-2:]}_V3', 'v3.2', 1,
                         '2026-03-15', 'Process Eng. Patel', std_ct,
                         'Current approved version — optimized roughing path N120-N180'))
        pg_rows.append((mac_id, op_code, f'O{op_code[2:]}{mac_id[-2:]}_V2', 'v2.8', 0,
                         '2025-11-01', 'Process Eng. Kim', std_ct + 35,
                         'Previous version — deprecated, 35s slower on roughing'))
    conn.executemany(
        "INSERT INTO ct_programs(machine_id,operation,program_number,version,is_current,"
        "release_date,approved_by,cycle_time_standard_seconds,notes) VALUES(?,?,?,?,?,?,?,?,?)", pg_rows)

    # ── Fixture log: 12 machines × 3 setups = 36 rows ────────────────────────
    fix_rows = []
    for mac_id, *_ in machines:
        for s in range(3):
            ts = now - _rnd.randint(1, 14) * DAY - s * DAY
            fix_rows.append((mac_id, ts, f'FXT-{mac_id}-{s+1:02d}', f'Setup Tech {s+1}',
                              _rnd.randint(12, 40), None, f'Setup Tech {s+1}', ts + 7*DAY))
    conn.executemany(
        "INSERT INTO ct_fixture_log(machine_id,ts,fixture_id,setup_by,setup_time_minutes,"
        "deviation_logged,sign_off,next_setup_due_ts) VALUES(?,?,?,?,?,?,?,?)", fix_rows)

    # ── Operators: 10 records ─────────────────────────────────────────────────
    conn.executemany(
        "INSERT OR IGNORE INTO ct_operators VALUES(?,?,?,?,?,?,?)", [
        ('OP-001','James Park','A',4,'Op20,Op30,Op40,Op50,Op60,Op70',8.5,'Fully certified all Op60 machines. Top quartile performance.'),
        ('OP-002','Priya Nair','A',3,'Op40,Op50,Op60',5.2,'Level 3 certified Op60 — competent on all 6 mills.'),
        ('OP-003','Mike Chen','A',3,'Op50,Op60,Op70',4.8,'Level 3 certified. On MILL-04 since last month. Good judgment on chatter detection.'),
        ('OP-004','Sarah Ortiz','A',4,'Op50,Op60,Op70,Op80',9.1,'Senior operator — MILL-05 lead. Experienced on hard material lots.'),
        ('OP-005','David Kim','B',3,'Op60,Op70,Op80',3.3,'Level 3 certified Op60.'),
        ('OP-006','Ana Reyes','B',2,'Op60,Op70',1.5,'Level 2 — still building speed on Op60. Requires occasional supervision.'),
        ('OP-007','Tom Wilson','B',4,'Op20,Op40,Op60',7.0,'Experienced — cross-trained Op20 and Op60.'),
        ('OP-008','Linda Zhao','C',3,'Op50,Op60',6.1,'Night shift lead for MILL group.'),
        ('OP-009','Carlos Vega','C',3,'Op60,Op70,Op80',4.4,'Competent Op60 — consistent cycle times.'),
        ('TL-01','Jackson Miller','A',5,'All operations',15.2,'Team Lead — 15+ yrs. Owns Op60 bottleneck escalations.'),
    ])

    # ── Knowledge graph: 8 historical events ─────────────────────────────────
    conn.executemany(
        "INSERT INTO ct_knowledge_graph(event_date,machine_id,operation,pattern,contributing_factors,"
        "root_cause,fix_applied,ct_loss_seconds,ct_recovered_seconds,customer_impact,lesson,recorded_ts)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", [
        ('2025-10-14','MILL-05','Op60','chatter-roughing-passes',
         'tool-wear-68pct,hard-material-lot-308hbw',
         'CBN insert T4 at 68% life on hard material lot 308HBW — same machine, same pattern. Roughing blocks N120-N180 added 118s.',
         'Early tool change at 68% (below normal 85% limit). Feed restored to 95% (not 100%) for remainder of hard lot. CT recovered to 738s.',
         127,109,'Avoided — no customer orders missed. 3 jobs redirected to MILL-04 during investigation.',
         'Hard material lots >305 HBW should trigger proactive tool life limit reduction at Op60 — currently not in control plan. Feed 95% safe operating point on hard lots.',
         now - 8*30*DAY),
        ('2025-04-22','MILL-03','Op60','feed-override-post-maintenance',
         'pm-parameter-reset',
         'After 30-day PM, spindle thermal compensation not re-enabled by technician. Feed rate derated automatically by 12% to compensate for apparent thermal runaway signal.',
         'Thermal compensation re-enabled. CT returned to 721s within 2 cycles.',
         95,92,'None — caught within 1 cycle by operator.',
         'Post-PM checklist must include thermal comp verification. Added to PM sign-off form.',
         now - 14*30*DAY),
        ('2025-01-08','MILL-01','Op60','program-version-mismatch',
         'wrong-program-version',
         'Op60 v2.8 loaded instead of v3.2 after tool change. v2.8 roughing path is 35s slower.',
         'Correct program loaded. Automated program version check added to cycle start sequence.',
         35,35,'None.',
         'Program version must be validated at cycle start. DCS lock on wrong-version programs implemented.',
         now - 18*30*DAY),
        ('2024-09-15','MILL-04','Op60','coolant-concentration-low',
         'coolant-3pct,feed-override-operator',
         'Coolant concentration fell to 3.1% (spec 5-8%). Increased chip weld on tool causing chatter. Operator reduced feed to 82%.',
         'Coolant system flushed and refilled to 6.5%. Tool changed. Feed restored to 100%.',
         138,135,'1 engine short on Kenworth order — resolved with 1h overtime.',
         'Daily coolant concentration check mandatory on all Op60 machines. Added to shift startup checklist.',
         now - 21*30*DAY),
        ('2024-06-03','MILL-02','Op60','fixture-shift',
         'fixture-clamp-worn',
         'Fixture clamp worn — part shifting 0.08mm during roughing. Machine extending air cuts to re-probe position.',
         'Fixture clamp replaced. Fixturing re-certified.',
         62,60,'None.',
         'Fixture clamp inspection added to weekly PM task.',
         now - 24*30*DAY),
        ('2024-02-11','GRIND-01','Op50','grinding-wheel-glaze',
         'wheel-dressing-overdue',
         'Grinding wheel glaze after dressing interval exceeded. Wheel rubbing rather than cutting — cycle 110s over standard.',
         'Wheel dressed. Dressing interval reduced from 200 parts to 150 parts.',
         110,108,'2 engines late to Peterbilt — no penalty as within lead time buffer.',
         'Grinding wheel dressing interval reduced for hard lot material.',
         now - 28*30*DAY),
        ('2023-11-20','HONE-01','Op70','coolant-flow-low',
         'coolant-pump-wear',
         'Coolant pump output degraded 35% — honing stones loading with swarf. Cycle time increased 88s.',
         'Coolant pump impeller replaced. CT recovered.',
         88,85,'None.',
         'Coolant flow rate check added to weekly machine health check.',
         now - 31*30*DAY),
        ('2023-08-05','MILL-06','Op60','spindle-bearing-wear',
         'bearing-temp-high,vibration-elevated',
         'Spindle bearing wear causing high spindle temp (71°C) and vibration. Machine auto-derated to 78% speed.',
         'Spindle bearing replaced during planned weekend shutdown. No emergency breakdown required.',
         164,160,'None — caught by predictive monitoring trend alert.',
         'Spindle temp >65°C sustained over 3 shifts triggers automatic maintenance notification.',
         now - 34*30*DAY),
    ])

    conn.commit()
    counts = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ['ct_cycle_time_log','ct_machine_params','ct_thermal_log',
                        'ct_oee_records','ct_downtime_log','ct_program_exec_log',
                        'ct_operator_activity','ct_in_cycle_inspection',
                        'ct_line_balance','ct_buffer_inventory']}
    total = sum(counts.values())
    print(f"[CT] Seeded {total} rows across ct_ tables: {counts}")


# ── Tool implementations ──────────────────────────────────────────────────────

def _get_realtime_cycle_times(inp):
    line = inp.get('line','engine-line-2')
    conn = get_conn()
    machines = conn.execute(
        "SELECT machine_id,operation_code,standard_ct_seconds FROM ct_machines WHERE line=?", (line,)
    ).fetchall()
    results = []
    for mid, op, std in machines:
        rows = conn.execute(
            "SELECT actual_ct_seconds,ts FROM ct_cycle_time_log WHERE machine_id=? ORDER BY ts DESC LIMIT 10",
            (mid,)
        ).fetchall()
        if not rows: continue
        cts = [r[0] for r in rows]
        last = cts[0]; avg10 = round(sum(cts)/len(cts),1)
        results.append({
            "machine": mid, "operation": op,
            "current_ct_seconds": last, "standard_ct_seconds": std,
            "rolling_avg_10_cycles": avg10,
            "delta_pct": round((last/std-1)*100,1),
            "status": "OVER TARGET" if last > std*1.05 else "OK"
        })
    bottleneck = max(results, key=lambda x: x['delta_pct']) if results else {}
    return {"line": line, "stations": results, "highest_deviation": bottleneck.get('machine','—')}


def _get_cycle_time_trend(inp):
    machine = inp.get('machine','MILL-04')
    window  = int(inp.get('window_hours', 8))
    conn    = get_conn()
    since   = int(time.time()) - window * 3600
    rows = conn.execute(
        "SELECT cycle_number,actual_ct_seconds,standard_ct_seconds,ts FROM ct_cycle_time_log "
        "WHERE machine_id=? AND ts>=? ORDER BY ts",
        (machine, since)
    ).fetchall()
    if not rows:
        return {"machine": machine, "error": "No data in window"}
    data = [{"cycle": r[0], "actual_ct": r[1], "standard_ct": r[2],
             "delta_pct": round((r[1]/r[2]-1)*100,1)} for r in rows]
    first3 = [d['actual_ct'] for d in data[:3]]
    last3  = [d['actual_ct'] for d in data[-3:]]
    trend = "DRIFT_UPWARD" if sum(last3)/3 - sum(first3)/3 > 20 else "STABLE"
    return {"machine": machine, "window_hours": window, "cycle_count": len(data),
            "trend_pattern": trend, "first_3_cycles_avg": round(sum(first3)/3,1),
            "last_3_cycles_avg": round(sum(last3)/3,1),
            "data": data[-20:]}


def _get_oee_breakdown(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    row = conn.execute(
        "SELECT availability_pct,performance_pct,quality_pct,oee_pct,downtime_min,speed_loss_min "
        "FROM ct_oee_records WHERE machine_id=? ORDER BY ts DESC LIMIT 1", (machine,)
    ).fetchone()
    if not row:
        return {"machine": machine, "error": "No OEE data"}
    return {
        "machine": machine,
        "availability_pct": row[0], "performance_pct": row[1],
        "quality_pct": row[2],      "oee_pct": row[3],
        "downtime_loss_min": row[4], "speed_loss_min": row[5],
        "note": ("Performance below target — cycle time deviation is the primary speed loss driver"
                 if machine == 'MILL-04' else "OEE within normal range")
    }


def _get_downtime_log(inp):
    machine = inp.get('machine','MILL-04')
    hours   = float(inp.get('hours', 8))
    conn    = get_conn()
    since   = int(time.time()) - int(hours * 3600)
    rows = conn.execute(
        "SELECT start_ts,duration_min,category,reason,impact FROM ct_downtime_log "
        "WHERE machine_id=? AND start_ts>=? ORDER BY start_ts DESC", (machine, since)
    ).fetchall()
    events = [{"time_ago_min": round((time.time()-r[0])/60),
               "duration_min": r[1], "category": r[2],
               "reason": r[3], "impact": r[4]} for r in rows]
    return {"machine": machine, "window_hours": hours,
            "event_count": len(events), "events": events}


def _get_machine_parameters(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows = conn.execute(
        "SELECT ts,spindle_load_pct,feed_rate_override_pct,spindle_speed_actual,"
        "spindle_speed_programmed,adaptive_control_active,coolant_temp_c,spindle_temp_c "
        "FROM ct_machine_params WHERE machine_id=? ORDER BY ts DESC LIMIT 8", (machine,)
    ).fetchall()
    if not rows: return {"machine": machine, "error": "No parameter data"}
    latest = rows[0]
    fro = latest[2]
    return {
        "machine": machine,
        "feed_rate_override": f"{fro}%{' — operator set ' + str(round((time.time()-int(time.time()-7200))/60)) + ' cycles ago' if machine=='MILL-04' and fro==85 else ''}",
        "spindle_load": f"{latest[1]}% average — {'within normal range' if latest[1] < 90 else 'ELEVATED'}",
        "spindle_speed": f"actual {latest[3]} RPM vs programmed {latest[4]} RPM — {'matches' if abs(latest[3]-latest[4])<20 else 'DEVIATION'}",
        "adaptive_control": "not active" if latest[5]==0 else "ACTIVE",
        "coolant_temp_c": latest[6],
        "spindle_temp_c": latest[7],
        "note": (f"Feed rate override manually reduced from 100% to 85% by operator at time of chatter report."
                 if machine=='MILL-04' and fro==85
                 else "Parameters within normal operating range"),
        "history": [{"ts_ago_min": round((time.time()-r[0])/60), "fro_pct": r[2],
                     "spindle_load": r[1]} for r in rows[:6]]
    }


def _get_program_execution_log(inp):
    machine    = inp.get('machine','MILL-04')
    operation  = inp.get('operation','Op60')
    n          = int(inp.get('last_n_cycles', 5))
    conn       = get_conn()
    rows = conn.execute(
        "SELECT cycle_number,block_range,block_name,standard_seconds,actual_seconds,delta_seconds "
        "FROM ct_program_exec_log WHERE machine_id=? AND operation=? ORDER BY ts DESC LIMIT ?",
        (machine, operation, n * 3)
    ).fetchall()
    blocks: dict = {}
    for r in rows:
        key = r[1]
        if key not in blocks:
            blocks[key] = {"block_range": key, "block_name": r[2],
                           "standard_seconds": r[3], "actual_seconds": [], "delta": []}
        blocks[key]["actual_seconds"].append(r[4])
        blocks[key]["delta"].append(r[5])
    summary = []
    total_delta = 0
    for b in blocks.values():
        avg_actual = round(sum(b["actual_seconds"])/len(b["actual_seconds"]))
        avg_delta  = round(sum(b["delta"])/len(b["delta"]))
        total_delta += avg_delta
        summary.append({
            "block_range": b["block_range"], "block_name": b["block_name"],
            "standard_seconds": b["standard_seconds"],
            "current_seconds": avg_actual,
            "delta": f"+{avg_delta} seconds" if avg_delta>=0 else f"{avg_delta} seconds",
            "note": ("Excess time concentrated here" if abs(avg_delta) > 10 else "Negligible")
        })
    conclusion = max(summary, key=lambda x: abs(int(x["delta"].replace("+","").replace(" seconds",""))))
    return {
        "machine": machine, "operation": operation, "cycles_analysed": n,
        "cycle_breakdown_comparison": summary,
        "total_delta_seconds": total_delta,
        "conclusion": f"{abs(total_delta)} of {abs(total_delta)} seconds lost in {conclusion['block_range']} — {conclusion['block_name']}"
    }


def _get_operator_activity_log(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows = conn.execute(
        "SELECT ts,operator_id,operator_name,event_type,duration_seconds,note "
        "FROM ct_operator_activity WHERE machine_id=? ORDER BY ts DESC LIMIT 20", (machine,)
    ).fetchall()
    events = []
    for r in rows:
        e = {"time": time.strftime('%H:%M', time.localtime(r[0])),
             "event": r[3], "operator": r[2]}
        if r[5]: e["note"] = r[5]
        if r[4]: e["duration_sec"] = r[4]
        events.append(e)
    return {"machine": machine, "events": events}


def _get_in_cycle_inspection_time(inp):
    machine   = inp.get('machine','MILL-04')
    operation = inp.get('operation','Op60')
    conn      = get_conn()
    rows = conn.execute(
        "SELECT standard_seconds,actual_seconds,gauge_type FROM ct_in_cycle_inspection "
        "WHERE machine_id=? AND operation=? ORDER BY ts DESC LIMIT 10", (machine, operation)
    ).fetchall()
    if not rows: return {"machine": machine, "error": "No inspection data"}
    std  = rows[0][0]
    avg  = round(sum(r[1] for r in rows)/len(rows), 1)
    return {
        "machine": machine, "operation": operation,
        "standard_seconds": std, "actual_avg_seconds": avg,
        "delta": f"+{avg-std:.1f} seconds",
        "gauge_type": rows[0][2],
        "assessment": "Negligible — inspection is not the source of CT loss" if avg-std < 8 else "ELEVATED — investigate gauge cycle"
    }


def _get_thermal_state(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    row = conn.execute(
        "SELECT spindle_temp_c,coolant_temp_c,ambient_temp_c,thermal_comp_active "
        "FROM ct_thermal_log WHERE machine_id=? ORDER BY ts DESC LIMIT 1", (machine,)
    ).fetchone()
    if not row: return {"machine": machine, "error": "No thermal data"}
    return {
        "machine": machine,
        "spindle_temp_c": row[0],
        "coolant_temp_c": row[1],
        "ambient_temp_c": row[2],
        "thermal_compensation_active": bool(row[3]),
        "assessment": ("Coolant temp elevated vs other machines — consistent with low coolant concentration"
                       if machine=='MILL-04' else "Thermal state normal")
    }


def _get_line_balance_status(inp):
    conn = get_conn()
    rows = conn.execute(
        "SELECT station_code,operation,wip_count,queue_depth_upstream,queue_depth_downstream,status "
        "FROM ct_line_balance WHERE ts=(SELECT MAX(ts) FROM ct_line_balance) ORDER BY station_code"
    ).fetchall()
    stations = [{"station": r[0], "operation": r[1], "wip": r[2],
                 "queue_upstream": r[3], "queue_downstream": r[4], "status": r[5]} for r in rows]
    blocked  = [s for s in stations if s["status"]=="BLOCKED"]
    starved  = [s for s in stations if s["status"]=="STARVED"]
    return {"stations": stations,
            "blocked_count": len(blocked), "starved_count": len(starved),
            "bottleneck_indicator": "Op60 — parts piling upstream, starvation downstream"}


def _get_bottleneck_station(inp):
    conn = get_conn()
    row = conn.execute(
        "SELECT station_code,operation,queue_depth_upstream,queue_depth_downstream,status "
        "FROM ct_line_balance WHERE ts=(SELECT MAX(ts) FROM ct_line_balance) "
        "AND queue_depth_upstream=(SELECT MAX(queue_depth_upstream) FROM ct_line_balance "
        "WHERE ts=(SELECT MAX(ts) FROM ct_line_balance))"
    ).fetchone()
    if not row:
        return {"current_bottleneck": "unknown"}
    return {
        "current_bottleneck": f"{row[1]} — {row[0]}",
        "utilization": "97.3%",
        "queue_depth_upstream": row[2],
        "queue_depth_downstream": row[3],
        "note": f"{row[1]} has been bottleneck for entire shift — downstream stations starving"
    }


def _get_buffer_inventory(inp):
    station = inp.get('station','Op60')
    conn    = get_conn()
    rows = conn.execute(
        "SELECT from_operation,to_operation,buffer_parts,buffer_minutes,max_buffer "
        "FROM ct_buffer_inventory WHERE ts=(SELECT MAX(ts) FROM ct_buffer_inventory) "
        "AND (from_operation=? OR to_operation=?)", (station, station)
    ).fetchall()
    buffers = [{"from": r[0], "to": r[1], "parts": r[2],
                "minutes_protection": r[3], "max_capacity": r[4]} for r in rows]
    return {"station": station, "buffers": buffers,
            "note": "Downstream buffer Op60→Op70 is zero — any further slowdown immediately starves Op70"}


def _get_parallel_station_status(inp):
    operation = inp.get('operation','Op60')
    conn      = get_conn()
    machines  = conn.execute(
        "SELECT p.machine_id,m.standard_ct_seconds FROM ct_parallel_stations p "
        "JOIN ct_machines m ON p.machine_id=m.machine_id WHERE p.operation=?", (operation,)
    ).fetchall()
    results = []
    for mid, std in machines:
        rows = conn.execute(
            "SELECT actual_ct_seconds FROM ct_cycle_time_log WHERE machine_id=? ORDER BY ts DESC LIMIT 5",
            (mid,)
        ).fetchall()
        cts = [r[0] for r in rows]
        avg = round(sum(cts)/len(cts),1) if cts else std
        # Estimate available capacity
        avail = max(0, round(8 - (avg/3600) * 50))  # rough: 8h shift, 50 cycles
        util  = round(avg/std * 100, 1)
        results.append({
            "machine_id": mid,
            "operation": operation,
            "current_utilization": f"{min(util,100)}%",
            "available_capacity_this_shift": f"{avail} additional units",
            "current_cycle_time": f"{avg} seconds",
            "status": "OVER TARGET" if avg > std*1.05 else "running normally"
        })
    return {"operation": operation, "parallel_machines": results}


def _get_shift_production_target(inp):
    line = inp.get('line','engine-line-2')
    op   = inp.get('operation','Op60')
    conn = get_conn()
    row  = conn.execute(
        "SELECT target_units,units_produced,shift_start_ts,shift_end_ts,hours_remaining "
        "FROM ct_shift_targets WHERE line=? AND operation=? ORDER BY id DESC LIMIT 1", (line, op)
    ).fetchone()
    if not row: return {"error": "No shift data"}
    target, produced, st, et, hrs_rem = row
    std_ct = 720  # Op60 standard
    cur_ct = 847  # MILL-04 current
    units_at_std = produced + round(hrs_rem * 3600 / std_ct)
    units_at_cur = produced + round(hrs_rem * 3600 / cur_ct)
    shortfall    = units_at_std - units_at_cur
    return {
        "shift_target_units": target,
        "units_completed_so_far": produced,
        "hours_remaining_in_shift": hrs_rem,
        "projected_units_at_standard_CT": min(target, units_at_std),
        "projected_units_at_current_CT": units_at_cur,
        "shortfall": max(0, target - units_at_cur),
        "shortfall_confirmed_by": "14:30 today if deviation continues"
    }


def _get_daily_production_forecast(inp):
    conn = get_conn()
    row  = conn.execute(
        "SELECT target_units,units_produced,hours_remaining FROM ct_shift_targets "
        "WHERE line=? ORDER BY id DESC LIMIT 1", ('engine-line-2',)
    ).fetchone()
    if not row: return {"error": "No data"}
    target, produced, hrs = row
    shortfall = max(0, target - (produced + round(hrs*3600/847)))
    return {
        "daily_target": target, "produced_so_far": produced,
        "projected_total": produced + round(hrs*3600/847),
        "on_track": shortfall == 0,
        "shortfall_units": shortfall,
        "shortfall_confirmed_time": "14:30" if shortfall > 0 else "N/A"
    }


def _get_customer_order_at_risk(inp):
    conn = get_conn()
    rows = conn.execute(
        "SELECT order_id,customer,engines_needed_today,engines_completed,"
        "delivery_deadline_ts,penalty_per_day,notes FROM ct_customer_orders "
        "WHERE risk_level IN ('HIGH','MEDIUM') AND status='active' ORDER BY delivery_deadline_ts"
    ).fetchall()
    orders = []
    for r in rows:
        deadline_dt = time.strftime('%H:%M today', time.localtime(r[4])) if r[4] < int(time.time())+86400 else 'tomorrow'
        orders.append({
            "order_id": r[0], "customer": r[1],
            "engines_needed_today": r[2], "current_completion": r[3],
            "delivery_deadline": deadline_dt, "penalty": r[5], "notes": r[6]
        })
    return {"orders_at_risk": orders}


def _get_cumulative_time_loss(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT actual_ct_seconds,standard_ct_seconds FROM ct_cycle_time_log "
        "WHERE machine_id=? ORDER BY ts DESC LIMIT 50", (machine,)
    ).fetchall()
    total_loss = sum(max(0, r[0]-r[1]) for r in rows)
    std_ct     = rows[0][1] if rows else 720
    units_lost = round(total_loss / std_ct, 1)
    return {
        "machine": machine, "window": "shift",
        "total_loss_seconds": total_loss,
        "total_loss_minutes": round(total_loss/60, 1),
        "equivalent_units_lost": units_lost,
        "cycles_analysed": len(rows)
    }


def _get_tooling_condition(inp):
    machine  = inp.get('machine','MILL-04')
    op       = inp.get('operation','Op60')
    pos      = inp.get('tool_position','T4')
    if 'roughing' in pos.lower(): pos = 'T4'
    conn     = get_conn()
    row = conn.execute(
        "SELECT tool_id,tool_name,life_used_pct,change_limit_pct,cutting_force_baseline,"
        "cutting_force_current,force_delta_pct,condition_note "
        "FROM ct_tooling WHERE machine_id=? AND operation=? AND tool_position=? "
        "ORDER BY ts DESC LIMIT 1", (machine, op, pos)
    ).fetchone()
    if not row: return {"machine": machine, "error": "No tooling data for this position"}
    return {
        "tool_id": row[0], "tool_name": row[1],
        "tool_life_used": f"{row[2]}%",
        "change_life_limit": f"{row[3]}%",
        "cutting_force_trend": f"increasing {row[6]}% over last 15 cycles vs baseline",
        "insert_condition": row[7],
        "recommended_action": "CHANGE NOW — exceeds 85% limit" if row[2]>=row[3] else f"monitor — {row[3]-row[2]:.0f}% margin remaining",
        "chatter_risk": "elevated at current wear level when combined with harder materials" if row[2]>60 else "normal"
    }


def _get_material_lot_hardness(inp):
    conn = get_conn()
    row  = conn.execute(
        "SELECT lot_number,material_type,hardness_hbw,hardness_spec_min,hardness_spec_max,"
        "supplier,machines_using,notes FROM ct_material_lots ORDER BY received_ts DESC LIMIT 1"
    ).fetchone()
    prev = conn.execute(
        "SELECT hardness_hbw FROM ct_material_lots ORDER BY received_ts DESC LIMIT 1 OFFSET 1"
    ).fetchone()
    if not row: return {"error": "No lot data"}
    return {
        "current_lot": row[0], "actual_hardness": f"{row[2]} HBW",
        "spec_range": f"{row[3]}-{row[4]} HBW",
        "hardness_percentile": "upper quartile of spec",
        "machines_using": row[6],
        "previous_lot_hardness": f"{prev[0]} HBW" if prev else "N/A",
        "note": row[7]
    }


def _get_maintenance_history(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT event_type,description,days_ago,duration_hours,technician,status "
        "FROM ct_maintenance WHERE machine_id=? ORDER BY ts DESC LIMIT 6", (machine,)
    ).fetchall()
    events  = [{"event_type": r[0], "description": r[1], "days_ago": r[2],
                "duration_hours": r[3], "technician": r[4], "status": r[5]} for r in rows]
    last_pm = next((e for e in events if e['event_type']=='PM'), None)
    return {
        "machine": machine, "events": events,
        "last_pm_days_ago": last_pm['days_ago'] if last_pm else "N/A",
        "note": ("PM completed 34 days ago — within 30-day PM interval but coolant alarm dismissed 2 days ago with no corrective action"
                 if machine=='MILL-04' else "Maintenance history normal")
    }


def _get_feed_override_log(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT ts,override_from_pct,override_to_pct,set_by,reason,acknowledged_by "
        "FROM ct_feed_override_log WHERE machine_id=? ORDER BY ts DESC LIMIT 5", (machine,)
    ).fetchall()
    events = [{"time": time.strftime('%H:%M', time.localtime(r[0])),
               "from_pct": r[1], "to_pct": r[2],
               "set_by": r[3], "reason": r[4],
               "acknowledged_by": r[5]} for r in rows]
    return {"machine": machine, "override_events": events,
            "current_override": f"{rows[0][2]}%" if rows else "100%",
            "summary": (f"Feed rate manually reduced from {rows[0][1]}% to {rows[0][2]}% by {rows[0][3]} at {events[0]['time']}"
                        if rows else "No override events")}


def _get_program_version(inp):
    machine = inp.get('machine','MILL-04')
    op      = inp.get('operation','Op60')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT program_number,version,is_current,release_date,approved_by,cycle_time_standard_seconds,notes "
        "FROM ct_programs WHERE machine_id=? AND operation=? ORDER BY is_current DESC", (machine, op)
    ).fetchall()
    current = next((r for r in rows if r[2]==1), rows[0] if rows else None)
    if not current: return {"error": "No program data"}
    return {
        "machine": machine, "operation": op,
        "running_program": current[0], "version": current[1],
        "is_approved_current_version": bool(current[2]),
        "release_date": current[3], "approved_by": current[4],
        "standard_ct_for_this_version": current[5],
        "notes": current[6],
        "assessment": "Current approved version loaded — program is not the cause of CT deviation"
    }


def _get_fixture_setup_log(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT ts,fixture_id,setup_by,setup_time_minutes,deviation_logged,sign_off "
        "FROM ct_fixture_log WHERE machine_id=? ORDER BY ts DESC LIMIT 3", (machine,)
    ).fetchall()
    setups = [{"date": time.strftime('%Y-%m-%d', time.localtime(r[0])),
               "fixture_id": r[1], "setup_by": r[2], "setup_time_min": r[3],
               "deviation": r[4] or "None", "sign_off": r[5]} for r in rows]
    return {"machine": machine, "recent_setups": setups,
            "assessment": "No fixture deviations logged — fixture is not contributing to CT loss"}


def _get_operator_skill_profile(inp):
    machine = inp.get('machine','MILL-04')
    conn    = get_conn()
    # Get operator currently on machine from activity log
    row = conn.execute(
        "SELECT operator_id,operator_name FROM ct_operator_activity "
        "WHERE machine_id=? ORDER BY ts DESC LIMIT 1", (machine,)
    ).fetchone()
    op_id = row[0] if row else 'OP-003'
    profile = conn.execute(
        "SELECT operator_name,shift,cert_level,operations_certified,years_experience,training_notes "
        "FROM ct_operators WHERE operator_id=?", (op_id,)
    ).fetchone()
    if not profile: return {"error": "Operator not found"}
    return {
        "operator_id": op_id,
        "operator_name": profile[0], "shift": profile[1],
        "certification_level": f"Level {profile[2]} of 4",
        "experience_years": profile[4],
        "certified_operations": profile[3],
        "assessment": profile[5],
        "note": ("Operator action (feed reduction) was correct response to chatter — this is NOT operator error"
                 if machine=='MILL-04' else "Operator fully certified")
    }


def _query_cycle_time_knowledge_graph(inp):
    op      = inp.get('operation','Op60')
    pattern = inp.get('pattern','')
    conn    = get_conn()
    rows    = conn.execute(
        "SELECT event_date,machine_id,pattern,root_cause,fix_applied,ct_loss_seconds,"
        "ct_recovered_seconds,customer_impact,lesson "
        "FROM ct_knowledge_graph WHERE operation=? ORDER BY recorded_ts DESC", (op,)
    ).fetchall()
    matches = [{"date": r[0], "machine": r[1], "pattern": r[2],
                "root_cause": r[3], "fix_applied": r[4],
                "ct_loss_seconds": r[5], "ct_recovered_seconds": r[6],
                "customer_impact": r[7], "lesson": r[8]} for r in rows]
    # Filter by pattern relevance
    if pattern:
        key = pattern.lower().replace('-','').replace('_','')
        matches = [m for m in matches if key[:8] in m['pattern'].replace('-','').replace('_','').lower()] or matches[:2]
    return {"operation": op, "matching_events": matches[:3],
            "summary": f"Found {len(matches)} matching historical events for pattern '{pattern}' at {op}"}


def _get_sister_machine_cycle_times(inp):
    op       = inp.get('operation','Op60')
    machines = inp.get('machines', [])
    conn     = get_conn()
    if not machines:
        machines = [r[0] for r in conn.execute(
            "SELECT machine_id FROM ct_parallel_stations WHERE operation=?", (op,)
        ).fetchall()]
    results = {}
    for mid in machines:
        rows = conn.execute(
            "SELECT actual_ct_seconds FROM ct_cycle_time_log WHERE machine_id=? ORDER BY ts DESC LIMIT 10",
            (mid,)
        ).fetchall()
        if not rows: continue
        cts   = [r[0] for r in rows]
        avg   = round(sum(cts)/len(cts), 1)
        trend = "DRIFT_UPWARD" if cts[0]-cts[-1] > 20 else "stable — no drift yet"
        # Check same material lot
        same_lot_row = conn.execute(
            "SELECT lot_number FROM ct_material_lots WHERE machines_using LIKE ?", (f'%{mid}%',)
        ).fetchone()
        tool_row = conn.execute(
            "SELECT life_used_pct FROM ct_tooling WHERE machine_id=? AND tool_position='T4' ORDER BY ts DESC LIMIT 1",
            (mid,)
        ).fetchone()
        results[mid] = {
            "current_cycle_time": f"{avg} seconds", "trend": trend,
            "same_material_lot": bool(same_lot_row),
            "tool_life_used": f"{tool_row[0]}%" if tool_row else "N/A",
            "estimated_cycles_to_same_risk": "~28 cycles at current wear rate" if mid=='MILL-05' else "N/A"
        }
    return results


# ── Action tools ──────────────────────────────────────────────────────────────

def _log_action(action_type, machine, detail, params):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ct_actions_log(action_type,machine_id,detail,parameters,ts) VALUES(?,?,?,?,?)",
        (action_type, machine, detail, json.dumps(params), int(time.time()))
    )
    conn.commit()


def _trigger_maintenance_investigation(inp):
    _log_action('maintenance_investigation', inp.get('machine'), inp.get('hypothesis'), inp)
    return {"confirmation": f"Maintenance investigation request sent to CMMS for {inp.get('machine')}.",
            "hypothesis": inp.get('hypothesis'), "urgency": inp.get('urgency','scheduled'),
            "work_order": f"WO-MI-{inp.get('machine')}-{int(time.time())%10000}",
            "assigned_to": "Tech-Reyes (on-call)"}


def _redirect_jobs_to_parallel_station(inp):
    _log_action('job_redirect', inp.get('from_machine'), f"Redirected to {inp.get('to_machine')}", inp)
    n = inp.get('jobs_to_redirect','4')
    n_int = int(''.join(filter(str.isdigit, str(n)))) if any(c.isdigit() for c in str(n)) else 4
    return {"redirect_confirmed": True, "jobs_moved": n_int,
            "from_machine": inp.get('from_machine'), "to_machine": inp.get('to_machine'),
            "updated_shift_forecast": 37,
            "caterpillar_order_status": "recoverable",
            "cummins_order_status": "recoverable with 1 unit margin",
            "mes_routing_updated": True}


def _rebalance_operator_assignments(inp):
    _log_action('operator_rebalance', None, str(inp.get('stations')), inp)
    return {"confirmation": "Operator assignment updated in workforce management system.",
            "stations_affected": inp.get('stations'), "reason": inp.get('reason'),
            "summary": "Additional support routed to bottleneck loading station"}


def _trigger_tool_change(inp):
    _log_action('tool_change', inp.get('machine'), inp.get('tool_position'), inp)
    return {"confirmation": f"Tool change task created for {inp.get('machine')} — {inp.get('tool_position')}.",
            "urgency": inp.get('urgency'), "work_order": f"WO-TC-{inp.get('machine')}-{int(time.time())%10000}",
            "operator_notified": True,
            "instruction": inp.get('instruction_to_operator','Restore feed to standard after change')}


def _request_feed_rate_optimization(inp):
    _log_action('feed_rate_request', inp.get('machine'), inp.get('justification'), inp)
    return {"confirmation": "Feed rate optimization request sent to Process Engineering.",
            "request_id": f"FRO-{int(time.time())%10000}",
            "current_override": inp.get('current_override'), "proposed": inp.get('proposed_override'),
            "review_timeline": "4 hours — process engineer on shift today"}


def _authorize_overtime(inp):
    _log_action('overtime_authorization', None, str(inp.get('units_needed')), inp)
    return {"confirmation": "Overtime authorization drafted and sent to supervisor for approval.",
            "units_needed": inp.get('units_needed'), "overtime_hours": 1.0,
            "labor_available": True, "estimated_cost": inp.get('cost_estimate','$1,200'),
            "decision_point": "Supervisor approval required — check by 15:00"}


def _resequence_production_jobs(inp):
    _log_action('job_resequence', None, str(inp.get('priority_orders')), inp)
    return {"confirmation": "Job queue resequenced in MES.",
            "priority_orders_first": inp.get('priority_orders'), "reason": inp.get('reason'),
            "summary": "High-risk customer orders moved to front of queue on bottleneck station"}


def _update_standard_cycle_time(inp):
    _log_action('standard_ct_review', None, inp.get('operation'), inp)
    return {"confirmation": "Standard cycle time flagged for engineering review.",
            "request_id": f"SCT-{int(time.time())%10000}",
            "operation": inp.get('operation'),
            "current_standard": inp.get('current_standard'),
            "observed_actual": inp.get('observed_actual'),
            "review_timeline": "Next engineering review cycle — 1 week"}


def _set_cycle_time_monitoring(inp):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ct_monitoring_alerts(machines,operation,alert_threshold,duration,reason,created_by,ts)"
        " VALUES(?,?,?,?,?,?,?)",
        (json.dumps(inp.get('machines',[])), inp.get('operation','Op60'),
         inp.get('alert_threshold',''), inp.get('duration',''), inp.get('reason',''),
         'CT Agent', int(time.time()))
    )
    conn.commit()
    return {"confirmation": "Enhanced monitoring activated.",
            "machines": inp.get('machines'), "threshold": inp.get('alert_threshold'),
            "duration": inp.get('duration'), "alert_channel": "MES dashboard + supervisor notification"}


def _update_cycle_time_knowledge_graph(inp):
    conn = get_conn()
    conn.execute(
        "INSERT INTO ct_knowledge_graph(event_date,machine_id,operation,pattern,contributing_factors,"
        "root_cause,fix_applied,ct_loss_seconds,ct_recovered_seconds,customer_impact,lesson,recorded_ts)"
        " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
        (time.strftime('%Y-%m-%d'), 'MILL-04', 'Op60', inp.get('event_summary','')[:60],
         '', inp.get('event_summary',''), inp.get('fix_applied',''),
         127, 92, inp.get('customer_impact',''), inp.get('lesson',''), int(time.time()))
    )
    conn.commit()
    return {"confirmation": "Knowledge graph updated.", "event_logged": inp.get('event_summary','')[:80],
            "fix_logged": inp.get('fix_applied',''), "lesson_logged": inp.get('lesson','')}


def _notify_human(inp):
    _log_action('human_notification', None, inp.get('recipient'), inp)
    return {"confirmation": f"Notification sent to {inp.get('recipient')}.",
            "subject": inp.get('subject'), "urgency": inp.get('urgency'),
            "decision_needed": inp.get('decision_needed',''),
            "delivery_channel": "Plant floor tablet + SMS to supervisor mobile",
            "acknowledged": "Pending"}


# ── Dispatch ──────────────────────────────────────────────────────────────────

_DISPATCH = {
    'get_realtime_cycle_times':          _get_realtime_cycle_times,
    'get_cycle_time_trend':              _get_cycle_time_trend,
    'get_oee_breakdown':                 _get_oee_breakdown,
    'get_downtime_log':                  _get_downtime_log,
    'get_machine_parameters':            _get_machine_parameters,
    'get_program_execution_log':         _get_program_execution_log,
    'get_operator_activity_log':         _get_operator_activity_log,
    'get_in_cycle_inspection_time':      _get_in_cycle_inspection_time,
    'get_thermal_state':                 _get_thermal_state,
    'get_line_balance_status':           _get_line_balance_status,
    'get_bottleneck_station':            _get_bottleneck_station,
    'get_buffer_inventory':              _get_buffer_inventory,
    'get_parallel_station_status':       _get_parallel_station_status,
    'get_shift_production_target':       _get_shift_production_target,
    'get_daily_production_forecast':     _get_daily_production_forecast,
    'get_customer_order_at_risk':        _get_customer_order_at_risk,
    'get_cumulative_time_loss':          _get_cumulative_time_loss,
    'get_tooling_condition':             _get_tooling_condition,
    'get_material_lot_hardness':         _get_material_lot_hardness,
    'get_maintenance_history':           _get_maintenance_history,
    'get_feed_override_log':             _get_feed_override_log,
    'get_program_version':               _get_program_version,
    'get_fixture_setup_log':             _get_fixture_setup_log,
    'get_operator_skill_profile':        _get_operator_skill_profile,
    'query_cycle_time_knowledge_graph':  _query_cycle_time_knowledge_graph,
    'get_sister_machine_cycle_times':    _get_sister_machine_cycle_times,
    'trigger_maintenance_investigation': _trigger_maintenance_investigation,
    'redirect_jobs_to_parallel_station': _redirect_jobs_to_parallel_station,
    'rebalance_operator_assignments':    _rebalance_operator_assignments,
    'trigger_tool_change':               _trigger_tool_change,
    'request_feed_rate_optimization':    _request_feed_rate_optimization,
    'authorize_overtime':                _authorize_overtime,
    'resequence_production_jobs':        _resequence_production_jobs,
    'update_standard_cycle_time':        _update_standard_cycle_time,
    'set_cycle_time_monitoring':         _set_cycle_time_monitoring,
    'update_cycle_time_knowledge_graph': _update_cycle_time_knowledge_graph,
    'notify_human':                      _notify_human,
}

# ── Agent loop ────────────────────────────────────────────────────────────────

import anthropic as _ant

async def run_cycle_time_agent(machine: str, operation: str, station: str,
                                actual_ct: int, target_ct: int, api_key: str):
    client   = _ant.Anthropic(api_key=api_key)
    loop     = asyncio.get_event_loop()
    dev_pct  = round((actual_ct / target_ct - 1) * 100, 1) if target_ct else 0
    initial  = (
        f"Cycle time deviation detected — {machine} is running {actual_ct}s against "
        f"{target_ct}s standard on {operation} ({dev_pct}% over target). "
        f"Pattern has been active for the last 3 cycles. Station: {station}. Line: engine-line-2.\n\n"
        f"Begin your investigation using the 8-step reasoning framework. "
        f"Start by confirming whether this operation is the current bottleneck, then quantify "
        f"the production impact before digging into root cause."
    )
    messages = [{"role": "user", "content": initial}]
    for _ in range(25):
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
            if block.type == "text":
                yield f"data: {json.dumps({'type': 'thinking', 'text': block.text})}\n\n"
            elif block.type == "tool_use":
                yield f"data: {json.dumps({'type': 'tool_call', 'tool': block.name, 'input': block.input})}\n\n"
                fn     = _DISPATCH.get(block.name)
                result = fn(block.input) if fn else {"error": f"Unknown tool: {block.name}"}
                yield f"data: {json.dumps({'type': 'tool_result', 'tool': block.name, 'result': result})}\n\n"
                tool_results.append({"type": "tool_result", "tool_use_id": block.id,
                                     "content": json.dumps(result)})
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "end_turn":
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            break
        if tool_results:
            messages.append({"role": "user", "content": tool_results})
