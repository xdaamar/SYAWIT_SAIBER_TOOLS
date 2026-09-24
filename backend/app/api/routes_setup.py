"""Setup API: status matrix, run/cancel/retry smart setup, doctor, events WS."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from .. import config
from ..core.setup import components as comps
from ..core.setup.doctor import run_doctor
from ..core.setup.orchestrator import runner
from ..core.state import read_setup_status

router = APIRouter(prefix="/api/setup", tags=["setup"])

_subs: list[asyncio.Queue] = []


def _emit(event: str, data: dict) -> None:
    msg = {"event": event, **data}
    for q in list(_subs):
        q.put_nowait(msg)


@router.get("/status")
def status(refresh: bool = True):
    """Component matrix + saved last-run state."""
    components = comps.detect_all() if refresh else None
    saved = read_setup_status()
    return {
        "ready": comps.overall_ready(components) if components else saved.get("ready", False),
        "running": runner.running,
        "components": components or saved.get("components", {}),
        "last_run": saved,
        "disclaimer_accepted": bool(config.load_settings().get("disclaimer_accepted", False)),
    }


class RunBody(BaseModel):
    only: list[str] | None = None


@router.post("/run")
def run(body: RunBody):
    if runner.running:
        raise HTTPException(409, "Setup sudah berjalan")
    ok = runner.start_async(body.only, on_event=_emit)
    if not ok:
        raise HTTPException(409, "Gagal memulai setup")
    return {"started": True}


@router.post("/cancel")
def cancel():
    return {"cancelled": runner.cancel()}


@router.post("/retry/{name}")
def retry(name: str):
    if name not in comps.COMPONENT_MAP:
        raise HTTPException(404, f"komponen tidak dikenal: {name}")
    if runner.running:
        raise HTTPException(409, "Setup sedang berjalan")
    runner.start_async([name], on_event=_emit)
    return {"started": True, "component": name}


@router.get("/doctor")
def doctor(component: str | None = None):
    return run_doctor(component)


@router.websocket("/events")
async def events(ws: WebSocket):
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue()
    _subs.append(q)
    loop = asyncio.get_running_loop()
    try:
        while True:
            msg = await q.get()
            await ws.send_json(msg)
    except WebSocketDisconnect:
        pass
    finally:
        if q in _subs:
            _subs.remove(q)
        del loop
