"""Recon API routes: nmap scan as a streaming job with XML parsing."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.job_manager import jobs, launch_process_job
from ..modules.recon import nmap_runner

router = APIRouter(prefix="/api/recon", tags=["recon"])


class NmapBody(BaseModel):
    target: str
    preset: str = "quick"
    extra_args: str = ""


@router.get("/nmap/presets")
def presets():
    return {"presets": [
        {"id": key, "args": " ".join(v["flags"]), "desc": v["label"]}
        for key, v in nmap_runner.PRESETS.items()
    ]}


@router.post("/nmap/preview")
def preview(body: NmapBody):
    cmd = nmap_runner.build_command(body.target, body.preset, body.extra_args)
    if not cmd:
        raise HTTPException(409, "nmap tidak ditemukan — jalankan Setup dulu")
    return {"command": " ".join(cmd), "argv": cmd,
            "desc": nmap_runner.PRESETS.get(body.preset, {}).get("label", body.preset)}


@router.post("/nmap/run")
def run(body: NmapBody):
    if not body.target.strip():
        raise HTTPException(400, "target kosong")
    cmd = nmap_runner.build_command(body.target, body.preset, body.extra_args)
    if not cmd:
        raise HTTPException(409, "nmap tidak ditemukan — jalankan Setup dulu")

    xml_path = nmap_runner.xml_out_path()

    def build_result(job, rc, lines):
        if not xml_path.exists():
            return None
        parsed = nmap_runner.parse_xml(xml_path)
        return {"xml": str(xml_path), "hosts": parsed.get("hosts", []),
                "attack_surface": nmap_runner.attack_surface(parsed),
                "elapsed": parsed.get("elapsed")}

    job = launch_process_job(
        jobs, "recon", f"nmap {body.target} ({body.preset})", cmd,
        build_result=build_result,
    )
    return {"job": job.to_dict()}
