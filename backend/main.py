import asyncio
import json
import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from simulator import SimulationEngine
from assembly_simulator import AssemblySimulator
from config import TICK_INTERVAL
import database as db

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


@app.on_event("startup")
async def startup():
    db.init_db()
    asyncio.create_task(broadcast_loop())
