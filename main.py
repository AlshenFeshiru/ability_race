import time, asyncio, socket, subprocess, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from database import init_db
from security import is_blacklisted, record_fail, keccak256, clean_ip, KECCAK_CTRL
from ws.handler import websocket_endpoint
from config import SERVER_PORT
import uvicorn

ADMIN_LOCKED = os.environ.get("ADMIN_LOCKED","false").lower() == "true"

def _pub_ip() -> str:
    try:
        r = subprocess.run(["curl","-s","--max-time","3","ifconfig.me"],capture_output=True,text=True)
        if r.stdout.strip(): return r.stdout.strip()
    except Exception: pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8",80))
        ip = s.getsockname()[0]; s.close(); return ip
    except Exception: return "?"

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    asyncio.create_task(_cleanup())
    yield

async def _cleanup():
    while True:
        await asyncio.sleep(60)
        try:
            from database import SessionLocal
            from abilities import deactivate_expired
            db = SessionLocal(); deactivate_expired(db); db.close()
        except Exception: pass

app = FastAPI(title="Ability Race", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

_rt: dict[str, list[float]] = {}

@app.middleware("http")
async def guard(request: Request, call_next):
    ip = request.headers.get("X-Forwarded-For","")
    ip = clean_ip(ip.split(",")[0].strip() if ip else (request.client.host if request.client else "0.0.0.0"))
    if is_blacklisted(ip): return JSONResponse(429, content={"detail":"Akses diblokir"})
    now = time.time()
    _rt.setdefault(ip,[])
    _rt[ip] = [t for t in _rt[ip] if now-t < 60]
    _rt[ip].append(now)
    if len(_rt[ip]) > 300: record_fail(ip); return JSONResponse(429, content={"detail":"Rate limit"})
    path = request.url.path.lower()
    for sig in ["../","..\\","%2e%2e","<?php","<script","union select","drop table","eval("]:
        if sig in path: record_fail(ip); return JSONResponse(400, content={"detail":"Request ditolak"})
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "SAMEORIGIN"
    resp.headers["X-AR-Integrity"] = keccak256(path.encode() + KECCAK_CTRL)[:12]
    return resp

from api.auth import router as auth_router
from api.competition import router as comp_router
from api.leaderboard import router as lb_router
from api.admin import router as admin_router
from api.viewer import router as viewer_router

app.include_router(auth_router, prefix="/api/auth")
app.include_router(comp_router, prefix="/api/competition")
app.include_router(lb_router,  prefix="/api/leaderboard")
app.include_router(viewer_router, prefix="/api/viewer")

if not ADMIN_LOCKED:
    app.include_router(admin_router, prefix="/admin")
else:
    @app.api_route("/admin/{path:path}", methods=["GET","POST","PUT","DELETE","PATCH"])
    async def locked(_: Request): return JSONResponse(403, content={"detail":"Panel dikunci permanen"})

@app.websocket("/ws/{uid}/{ticket}")
async def ws(websocket: WebSocket, uid: str, ticket: str, field_id: int = 0):
    await websocket_endpoint(websocket, uid, ticket, field_id if 1 <= field_id <= 8 else None)

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index(): return FileResponse("static/index.html")

@app.get("/viewer")
def viewer(): return FileResponse("static/viewer.html")

@app.get("/health")
def health(): return {"ok": True}

if __name__ == "__main__":
    ip = _pub_ip()
    print(f"\nAbility Race | port {SERVER_PORT} | {ip}")
    uvicorn.run("main:app", host="0.0.0.0", port=SERVER_PORT, reload=False, workers=1, log_level="warning", access_log=False)
