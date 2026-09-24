"""Jobs API: list, detail, cancel, and live output WebSocket."""
from __future__ import annotations

import asyncio
import queue

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from ..core import job_manager

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
def list_jobs():
    return {"jobs": job_manager.jobs.list()}


@router.get("/{job_id}")
def get_job(job_id: str, with_lines: bool = True):
    job = job_manager.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job tidak ditemukan")
    return job.to_dict(with_lines=with_lines)


@router.post("/{job_id}/cancel")
def cancel_job(job_id: str):
    ok = job_manager.jobs.cancel(job_id)
    if not ok:
        raise HTTPException(409, "job tidak bisa dibatalkan (tidak ada / bukan running)")
    return {"cancelled": True}


@router.post("/{job_id}/resubmit")
async def resubmit(job_id: str):
    """Re-run a finished job by re-launching its command (process jobs only)."""
    job = job_manager.jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job tidak ditemukan")
    if not job.command:
        raise HTTPException(400, "job tidak punya command untuk diulang")
    cmd = job.command.split()
    new_job = job_manager.launch_process_job(
        job_manager.jobs, job.kind, job.title, cmd,
        build_result=lambda j, rc, lines: None,
    )
    return {"job": new_job.to_dict()}


@router.websocket("/{job_id}/ws")
async def job_ws(ws: WebSocket, job_id: str):
    await ws.accept()
    job = job_manager.jobs.get(job_id)
    if not job:
        await ws.send_json({"event": "error", "error": "job tidak ditemukan"})
        await ws.close()
        return

    q = job.subscribe()
    loop = asyncio.get_running_loop()

    async def _reader():
        while True:
            entry = await loop.run_in_executor(None, q.get)
            await ws.send_json(entry)
            if entry.get("event") == "end":
                break

    try:
        # send existing buffered lines first
        with job._lock:
            backlog = list(job.lines)
        for entry in backlog:
            await ws.send_json(entry)
        if job.status != "running":
            await ws.send_json({"event": "end", "status": job.status,
                                "exit_code": job.exit_code, "error": job.error})
            return
        await _reader()
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        job.unsubscribe(q)
