"""Report API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..core.job_manager import jobs
from ..modules.report import collect_findings, generate

router = APIRouter(prefix="/api/report", tags=["report"])


class ReportBody(BaseModel):
    job_ids: list[str] = []
    findings: list[dict] = []
    fmt: str = "md"
    target: str = ""


@router.post("/generate")
def generate_report(body: ReportBody):
    outputs = []
    for jid in body.job_ids:
        job = jobs.get(jid)
        if job and job.result:
            outputs.append({"module": job.kind, **({"findings": job.result.get("findings")}
                                                  if isinstance(job.result, dict) else {})})
    rows = collect_findings(outputs)
    rows.extend(collect_findings([{"module": r.get("module", "manual"),
                                   "findings": [r]} for r in body.findings]))
    if not rows:
        raise HTTPException(400, "tidak ada temuan untuk dilaporkan")
    try:
        result = generate(rows, fmt=body.fmt, target=body.target)
    except Exception as e:
        raise HTTPException(500, f"gagal membuat laporan: {e}")
    return result


@router.get("/list")
def list_reports():
    d = config.DATA_DIR / "reports"
    d.mkdir(parents=True, exist_ok=True)
    items = []
    for f in sorted(d.iterdir(), reverse=True):
        if f.is_file() and f.suffix in (".md", ".html"):
            items.append({"name": f.name, "path": str(f),
                          "size_kb": round(f.stat().st_size / 1024, 1)})
    return {"reports": items}
