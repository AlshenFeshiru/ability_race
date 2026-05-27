import json
from datetime import datetime, timezone
from fastapi import WebSocket, WebSocketDisconnect
from security import verify_ws_ticket, keccak256, is_blacklisted, record_fail, KECCAK_CTRL
from config import CHAMPIONSHIP_FIELDS

class Manager:
    def __init__(self):
        self.active: dict[str, WebSocket] = {}
        self.field_members: dict[int, set[str]] = {fid: set() for fid in CHAMPIONSHIP_FIELDS}

    async def connect(self, uid: str, fid: int | None, ws: WebSocket):
        await ws.accept()
        self.active[uid] = ws
        if fid and fid in self.field_members: self.field_members[fid].add(uid)

    def disconnect(self, uid: str, fid: int | None):
        self.active.pop(uid, None)
        if fid and fid in self.field_members: self.field_members[fid].discard(uid)

    async def send(self, uid: str, data: dict):
        ws = self.active.get(uid)
        if ws:
            try: await ws.send_json(data)
            except Exception: self.active.pop(uid, None)

    async def broadcast(self, fid: int, data: dict, exclude: str | None = None):
        for uid in set(self.field_members.get(fid, set())):
            if uid != exclude: await self.send(uid, data)

    async def ability_event(self, fid: int, atype: str, payload: dict):
        msg = {"event":"ability_applied","ability":atype,"payload":payload,
               "ts":datetime.now(timezone.utc).isoformat(),
               "integrity":keccak256(json.dumps(payload,sort_keys=True).encode())[:16]}
        await self.broadcast(fid, msg)

manager = Manager()

async def websocket_endpoint(ws: WebSocket, uid: str, ticket: str, fid: int | None):
    ip = ws.client.host if ws.client else "0.0.0.0"
    if is_blacklisted(ip): await ws.close(code=4029, reason="IP diblokir"); return
    if not verify_ws_ticket(uid, ticket):
        record_fail(ip); await ws.close(code=4001, reason="Tiket tidak valid"); return
    await manager.connect(uid, fid, ws)
    try:
        await ws.send_json({"event":"connected","uid":uid,"fid":fid,"field":CHAMPIONSHIP_FIELDS.get(fid,""),"ts":datetime.now(timezone.utc).isoformat()})
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
                if msg.get("type") == "ping": await ws.send_json({"event":"pong"})
            except Exception: pass
    except WebSocketDisconnect: manager.disconnect(uid, fid)
    except Exception: manager.disconnect(uid, fid)
