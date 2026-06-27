import asyncio
import json
import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from simulator import SimulationEngine
from assembly_simulator import AssemblySimulator
from config import TICK_INTERVAL
import database as db
import anthropic
from pm_agent_tools import run_pm_agent, init_pm_tables
from quality_agent_tools import run_quality_agent, init_quality_tables
from cycle_time_agent_tools import run_cycle_time_agent, init_ct_tables

app = FastAPI(title="CumminsIQ API")

# In production set ALLOWED_ORIGINS="https://your-app.vercel.app" (comma-separated)
_raw = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173")
ALLOWED_ORIGINS = [o.strip() for o in _raw.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine   = SimulationEngine()
assembly = AssemblySimulator()

exec_clients:     list[WebSocket] = []
assembly_clients: list[WebSocket] = []


# ── HTTP endpoints ────────────────────────────────────────────────────────────

@app.get("/api/state")
def get_state():
    return engine.get_snapshot()

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": int(time.time())}


# ── History / persistence endpoints ─────────────────────────────────────────

@app.get("/api/work-orders")
def get_work_orders(limit: int = Query(100, le=500)):
    return db.get_work_orders(limit)

@app.get("/api/station-history/{code}")
def get_station_history(code: str, hours: int = Query(2, le=48)):
    return db.get_station_history(code, hours)

@app.get("/api/line-metrics")
def get_line_metrics(hours: int = Query(8, le=48)):
    return db.get_line_metrics(hours)

@app.get("/api/agent-events")
def get_agent_events(limit: int = Query(100, le=500)):
    return db.get_agent_events(limit)

@app.post("/api/analyze")
async def analyze_anomaly(data: dict):
    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        async def err():
            yield f"data: {json.dumps({'error': 'No API key provided. Set your key using the top-right button.'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    station   = data.get("station", {})
    history   = data.get("history", [])
    agent_type = data.get("agent_type", "equipment")

    code   = station.get("code", "?")
    temp   = station.get("machine_temp", 0)
    vib    = station.get("vibration", 0)
    tool   = station.get("tool_life_pct", 100)
    act_ct = station.get("actual_ct", 0)
    tgt_ct = station.get("target_ct", 1)
    status = station.get("status", "running")
    pct_over = round((act_ct / tgt_ct - 1) * 100, 1) if tgt_ct else 0

    if history:
        h_temps = [h.get("machine_temp", temp) for h in history[-10:]]
        h_vibs  = [h.get("vibration", vib)  for h in history[-10:]]
        trend_temp = round(h_temps[-1] - h_temps[0], 2) if len(h_temps) > 1 else 0
        trend_vib  = round(h_vibs[-1]  - h_vibs[0],  3) if len(h_vibs)  > 1 else 0
        history_summary = (
            f"Temperature trend (last {len(h_temps)} readings): "
            f"{h_temps[0]}°C → {h_temps[-1]}°C (Δ{trend_temp:+.2f}°C)\n"
            f"Vibration trend: {h_vibs[0]:.3f}g → {h_vibs[-1]:.3f}g (Δ{trend_vib:+.3f}g)"
        )
    else:
        history_summary = "No historical trend data available (station just flagged)."

    system_prompt = (
        "You are an AI agent embedded in a Cummins engine assembly line monitoring system. "
        "You receive real-time sensor telemetry and must reason like an experienced plant engineer "
        "combined with an AI diagnostician. You draw inferences — not just threshold checks. "
        "You look at trends, combinations of signals, and context to reach conclusions a simple rule cannot. "
        "Be specific, concise, and actionable. Use precise engineering language. "
        "Structure your response with: Root Cause Assessment, Risk if Unaddressed, Recommended Actions."
    )

    user_prompt = (
        f"Analyze this live anomaly at station {code} on the Cummins engine assembly line.\n\n"
        f"STATUS: {status.upper()}\n\n"
        f"CURRENT SENSOR READINGS:\n"
        f"  Machine Temperature : {temp:.1f}°C  (warn >87°C | critical >91°C)\n"
        f"  Vibration           : {vib:.3f}g RMS (warn >0.68g | critical >0.82g)\n"
        f"  Tool Life           : {tool:.0f}%   (warn <18% | critical <8%)\n"
        f"  Cycle Time          : {act_ct}s actual vs {tgt_ct}s target ({pct_over:+.1f}%)\n\n"
        f"SENSOR TREND (recent history):\n{history_summary}\n\n"
        f"DISPATCHING AGENT: {agent_type}\n\n"
        "Based on the combination of these readings and their trends — not just threshold breaches — "
        "what is actually happening at this station? What should the plant engineer do right now?"
    )

    client = anthropic.Anthropic(api_key=api_key)

    async def stream_claude():
        try:
            with client.messages.stream(
                model="claude-sonnet-4-6",
                max_tokens=600,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                for text in stream.text_stream:
                    yield f"data: {json.dumps({'text': text})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(stream_claude(), media_type="text/event-stream")


@app.get("/api/tables")
def list_tables():
    conn = db.get_conn()
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()]
    result = {}
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        result[t] = count
    return {"tables": tables, "row_counts": result}


@app.get("/api/tables/{table_name}")
def get_table(table_name: str, limit: int = Query(100, le=500)):
    conn = db.get_conn()
    valid = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if table_name not in valid:
        return {"error": f"Table '{table_name}' not found", "available": valid}
    rows = conn.execute(f"SELECT * FROM {table_name} LIMIT ?", (limit,)).fetchall()
    cols = [d[0] for d in conn.execute(f"SELECT * FROM {table_name} LIMIT 0").description or []]
    return {"table": table_name, "count": len(rows), "columns": cols,
            "rows": [dict(zip(cols, r)) for r in rows]}


@app.get("/api/db-stats")
def db_stats():
    conn = db.get_conn()
    return {
        "work_orders":      conn.execute("SELECT COUNT(*) FROM work_orders").fetchone()[0],
        "station_readings": conn.execute("SELECT COUNT(*) FROM station_readings").fetchone()[0],
        "agent_events":     conn.execute("SELECT COUNT(*) FROM agent_events").fetchone()[0],
        "line_metrics":     conn.execute("SELECT COUNT(*) FROM line_metrics").fetchone()[0],
    }


# ── WebSocket endpoints ───────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_exec(websocket: WebSocket):
    await websocket.accept()
    exec_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps(engine.get_snapshot()))
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in exec_clients:
            exec_clients.remove(websocket)


@app.websocket("/ws/assembly")
async def websocket_assembly(websocket: WebSocket):
    await websocket.accept()
    assembly_clients.append(websocket)
    try:
        await websocket.send_text(json.dumps(assembly.get_snapshot()))
        while True:
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in assembly_clients:
            assembly_clients.remove(websocket)


# ── Broadcast loop ────────────────────────────────────────────────────────────

async def _safe_send(ws: WebSocket, payload: str) -> bool:
    try:
        await ws.send_text(payload)
        return True
    except Exception:
        return False


async def broadcast_loop():
    while True:
        await asyncio.sleep(TICK_INTERVAL)

        engine.tick()
        exec_snap = json.dumps(engine.get_snapshot())
        dead = [ws for ws in exec_clients if not await _safe_send(ws, exec_snap)]
        for ws in dead:
            exec_clients.remove(ws)

        asm_snap = json.dumps(assembly.tick())
        dead = [ws for ws in assembly_clients if not await _safe_send(ws, asm_snap)]
        for ws in dead:
            assembly_clients.remove(ws)


@app.post("/api/pm-agent")
async def pm_agent_endpoint(data: dict):
    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        async def err():
            yield f"data: {json.dumps({'type': 'error', 'text': 'No API key provided.'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    asset_id        = data.get("asset_id", "STN-01")
    fault_type      = data.get("fault_type", "bearing_wear")
    sensor_readings = data.get("sensor_readings", {})

    return StreamingResponse(
        run_pm_agent(asset_id, fault_type, sensor_readings, api_key),
        media_type="text/event-stream"
    )


@app.post("/api/quality-agent")
async def quality_agent_endpoint(data: dict):
    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        async def err():
            yield f"data: {json.dumps({'type': 'error', 'text': 'No API key provided.'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    station    = data.get("station", "STN-03")
    defect_type = data.get("defect_type", "Ring End Gap")
    detail     = data.get("detail", "Defect detected")
    confidence = float(data.get("confidence", 94))

    return StreamingResponse(
        run_quality_agent(station, defect_type, detail, confidence, api_key),
        media_type="text/event-stream"
    )


@app.post("/api/cycle-time-agent")
async def cycle_time_agent_endpoint(data: dict):
    api_key = data.get("api_key") or os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        async def err():
            yield f"data: {json.dumps({'type': 'error', 'text': 'No API key provided.'})}\n\n"
        return StreamingResponse(err(), media_type="text/event-stream")

    machine   = data.get("machine",   "MILL-04")
    operation = data.get("operation", "Op60")
    station   = data.get("station",   "STN-06")
    actual_ct = int(data.get("actual_ct",  847))
    target_ct = int(data.get("target_ct",  720))

    return StreamingResponse(
        run_cycle_time_agent(machine, operation, station, actual_ct, target_ct, api_key),
        media_type="text/event-stream"
    )


@app.on_event("startup")
async def startup():
    db.init_db()
    init_pm_tables()
    init_quality_tables()
    init_ct_tables()
    asyncio.create_task(broadcast_loop())
