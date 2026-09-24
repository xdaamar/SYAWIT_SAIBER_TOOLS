"""Report generator: collect findings from completed jobs into a Markdown or
HTML report with an executive summary by severity."""
from __future__ import annotations

import html
import time
from pathlib import Path

from .. import config

SEV_ORDER = ["critical", "high", "medium", "low", "info"]

SEV_EMOJI = {"critical": "🔴", "high": "🟠", "medium": "🟡",
             "low": "🔵", "info": "⚪"}


def collect_findings(job_outputs: list[dict]) -> list[dict]:
    """Normalize findings from various module outputs into report rows."""
    rows: list[dict] = []
    for out in job_outputs:
        module = out.get("module", "?")
        for f in out.get("findings", []) or []:
            rows.append({
                "module": module,
                "title": f.get("title", "?"),
                "severity": (f.get("severity") or "info").lower(),
                "url": f.get("url", ""),
                "evidence": f.get("evidence", ""),
                "recommendation": f.get("recommendation", ""),
            })
    return rows


def summarize(rows: list[dict]) -> dict:
    by_sev = {s: 0 for s in SEV_ORDER}
    for r in rows:
        by_sev[r["severity"]] = by_sev.get(r["severity"], 0) + 1
    return {"total": len(rows), "by_severity": by_sev}


def _markdown(rows: list[dict], meta: dict) -> str:
    s = summarize(rows)
    lines = [
        f"# Laporan CTFSuite",
        "",
        f"- Dibuat: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Target: {meta.get('target', '(berbagai)')}",
        f"- Total temuan: **{s['total']}**",
        "",
        "| Severity | Jumlah |", "|---|---|",
    ]
    for sev in SEV_ORDER:
        n = s["by_severity"].get(sev, 0)
        if n:
            lines.append(f"| {SEV_EMOJI[sev]} {sev.upper()} | {n} |")
    lines += ["", "## Temuan", ""]
    for i, r in enumerate(sorted(rows, key=lambda r: SEV_ORDER.index(r["severity"])), 1):
        lines += [
            f"### {i}. [{r['severity'].upper()}] {r['title']}",
            "",
            f"- **Modul**: {r['module']}",
            f"- **URL**: {r['url'] or '-'}",
            f"- **Bukti**: `{(r['evidence'] or '')[:200]}`",
            f"- **Rekomendasi**: {r['recommendation'] or '-'}",
            "",
        ]
    lines += ["---", "*Hasil scan otomatis — verifikasi manual sebelum ditindak.*"]
    return "\n".join(lines)


def _html(rows: list[dict], meta: dict) -> str:
    s = summarize(rows)
    e = html.escape

    def _row(r: dict) -> str:
        return (f"<tr><td>{SEV_EMOJI.get(r['severity'],'')} {e(r['severity'])}</td>"
                f"<td>{e(r['module'])}</td><td>{e(r['title'])}</td>"
                f"<td>{e(r['url'])}</td><td><code>{e(r['evidence'][:160])}</code></td>"
                f"<td>{e(r['recommendation'])}</td></tr>")

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Laporan CTFSuite</title>
<style>body{{font-family:Segoe UI,Roboto,sans-serif;background:#0f1115;color:#e6e6e6;margin:2rem}}
h1{{color:#7ee787}} table{{border-collapse:collapse;width:100%;font-size:.9rem}}
td,th{{border:1px solid #333;padding:.45rem .6rem;text-align:left;vertical-align:top}}
tr:nth-child(even){{background:#181b21}} code{{color:#79c0ff}}</style></head><body>
<h1>Laporan CTFSuite</h1>
<p>Dibuat {time.strftime('%Y-%m-%d %H:%M:%S')} · Target {e(meta.get('target',''))} ·
Total temuan <b>{s['total']}</b></p>
<table><tr><th>Severity</th><th>Modul</th><th>Judul</th><th>URL</th><th>Bukti</th><th>Rekomendasi</th></tr>
{''.join(_row(r) for r in sorted(rows, key=lambda r: SEV_ORDER.index(r['severity'])))}
</table><p><i>Hasil scan otomatis — verifikasi manual sebelum ditindak.</i></p></body></html>"""


def generate(rows: list[dict], fmt: str = "md", target: str = "",
             out_path: str | None = None) -> dict:
    """Write the report to DATA_DIR/reports (or out_path) and return its path."""
    reports_dir = config.DATA_DIR / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    meta = {"target": target}
    if fmt == "html":
        content = _html(rows, meta)
        path = Path(out_path or reports_dir / f"report_{int(time.time())}.html")
    else:
        content = _markdown(rows, meta)
        path = Path(out_path or reports_dir / f"report_{int(time.time())}.md")
    path.write_text(content, encoding="utf-8")
    return {"path": str(path), "findings": len(rows),
            "summary": summarize(rows), "format": fmt}
