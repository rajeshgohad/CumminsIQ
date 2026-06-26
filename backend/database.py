import sqlite3
import re
import time
import os
from typing import Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "cumminsiq.db")
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=NORMAL")
    return _conn


def init_db():
    conn = get_conn()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS station_readings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        ts            INTEGER NOT NULL,
        code          TEXT    NOT NULL,
        actual_ct     INTEGER,
        machine_temp  REAL,
        vibration     REAL,
        tool_life_pct REAL,
        status        TEXT,
        parts_count   INTEGER
    );
    CREATE INDEX IF NOT EXISTS idx_sr ON station_readings(code, ts DESC);

    CREATE TABLE IF NOT EXISTS work_orders (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        wo_number   TEXT    UNIQUE NOT NULL,
        station_code TEXT,
        description TEXT,
        priority    TEXT    DEFAULT 'MEDIUM',
        wo_status   TEXT    DEFAULT 'open',
        created_at  INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_wo ON work_orders(created_at DESC);

    CREATE TABLE IF NOT EXISTS agent_events (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id    INTEGER,
        ts          INTEGER NOT NULL,
        from_agent  TEXT    NOT NULL,
        to_agent    TEXT,
        event_type  TEXT,
        message     TEXT,
        severity    TEXT,
        station_code TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_ae ON agent_events(ts DESC);

    CREATE TABLE IF NOT EXISTS line_metrics (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        ts                  INTEGER NOT NULL,
        oee                 REAL,
        production_per_hour INTEGER,
        production_today    INTEGER,
        shift               TEXT,
        bottleneck_station  TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_lm ON line_metrics(ts DESC);
    """)
    conn.commit()
    print(f"[DB] Initialised: {DB_PATH}")


# ── Writes ──────────────────────────────────────────────────────────────────

def save_station_readings(stations: list[dict], ts: int):
    conn = get_conn()
    conn.executemany(
        "INSERT INTO station_readings(ts,code,actual_ct,machine_temp,vibration,tool_life_pct,status,parts_count) "
        "VALUES(?,?,?,?,?,?,?,?)",
        [(ts, s["code"], s["actual_ct"], round(s["machine_temp"], 2),
          round(s["vibration"], 3), round(s["tool_life_pct"], 1),
          s["status"], s["parts_count"]) for s in stations],
    )
    conn.commit()


def save_line_metric(ts: int, oee: float, prod_hr: int, prod_today: int,
                     shift: str, bottleneck: str):
    conn = get_conn()
    conn.execute(
        "INSERT INTO line_metrics(ts,oee,production_per_hour,production_today,shift,bottleneck_station) "
        "VALUES(?,?,?,?,?,?)",
        (ts, round(oee, 2), prod_hr, prod_today, shift, bottleneck),
    )
    conn.commit()


def save_agent_events(events: list[dict], last_saved_id: int) -> int:
    """Persist events with id > last_saved_id. Returns new high-water mark."""
    new_events = [e for e in events if e["id"] > last_saved_id]
    if not new_events:
        return last_saved_id

    conn = get_conn()

    # Persist events
    conn.executemany(
        "INSERT OR IGNORE INTO agent_events"
        "(event_id,ts,from_agent,to_agent,event_type,message,severity,station_code) "
        "VALUES(?,?,?,?,?,?,?,?)",
        [(e["id"], e["timestamp"], e["from_agent"], e.get("to_agent"),
          e["type"], e["message"], e["severity"], e.get("station"))
         for e in new_events],
    )

    # Extract work orders from Maintenance Agent 'act' events
    for e in new_events:
        if e["from_agent"] == "maintenance" and e["type"] == "act":
            wo = re.search(r"WO-\d+", e["message"])
            if wo:
                pri = re.search(r"Priority:\s*(\w+)", e["message"])
                desc = e["message"].split("—")[0].strip()[:200]
                try:
                    conn.execute(
                        "INSERT OR IGNORE INTO work_orders"
                        "(wo_number,station_code,description,priority,created_at) "
                        "VALUES(?,?,?,?,?)",
                        (wo.group(), e.get("station"), desc,
                         pri.group(1) if pri else "MEDIUM", e["timestamp"]),
                    )
                except Exception:
                    pass

    conn.commit()
    return max(e["id"] for e in new_events)


# ── Reads ────────────────────────────────────────────────────────────────────

def get_station_history(code: str, hours: int = 2) -> list[dict]:
    since = int(time.time()) - hours * 3600
    rows = get_conn().execute(
        "SELECT ts,actual_ct,machine_temp,vibration,tool_life_pct,status "
        "FROM station_readings WHERE code=? AND ts>=? ORDER BY ts ASC LIMIT 600",
        (code, since),
    ).fetchall()
    return [dict(r) for r in rows]


def get_work_orders(limit: int = 100) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM work_orders ORDER BY created_at DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_agent_events(limit: int = 100) -> list[dict]:
    rows = get_conn().execute(
        "SELECT * FROM agent_events ORDER BY ts DESC LIMIT ?", (limit,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_line_metrics(hours: int = 8) -> list[dict]:
    since = int(time.time()) - hours * 3600
    rows = get_conn().execute(
        "SELECT ts,oee,production_per_hour,production_today,bottleneck_station "
        "FROM line_metrics WHERE ts>=? ORDER BY ts ASC LIMIT 1200",
        (since,),
    ).fetchall()
    return [dict(r) for r in rows]


def prune_old_data(max_hours: int = 48):
    cutoff = int(time.time()) - max_hours * 3600
    conn = get_conn()
    conn.execute("DELETE FROM station_readings WHERE ts<?", (cutoff,))
    conn.execute("DELETE FROM agent_events WHERE ts<?",     (cutoff,))
    conn.execute("DELETE FROM line_metrics WHERE ts<?",     (cutoff,))
    conn.commit()
