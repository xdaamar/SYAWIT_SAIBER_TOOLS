"""Doctor: deep diagnosis of a component that keeps failing.

Collects PATH entries, tool lookup results, free disk space, proxy env and
component-specific probes, then returns a human-readable report.
"""
from __future__ import annotations

import os
import shutil
import socket

from ... import config
from .. import process as procutil


def _disk_free_gb(path: str) -> float:
    try:
        usage = shutil.disk_usage(path)
        return round(usage.free / 1e9, 2)
    except OSError:
        return -1


def _where(name: str) -> list[str]:
    rc, out, _ = procutil.run_capture(["where.exe", name], timeout=15)
    return [l.strip() for l in out.splitlines() if l.strip()] if rc == 0 else []


def run_doctor(component: str | None = None) -> dict:
    findings: list[dict] = []
    report: dict = {
        "component": component,
        "findings": findings,
        "environment": {
            "python_on_path": _where("python.exe") or _where("python3.exe"),
            "py_launcher": _where("py.exe"),
            "git": _where("git.exe"),
            "nmap": _where("nmap.exe"),
            "winget": _where("winget.exe"),
            "venv_exists": config.VENV_DIR.exists(),
            "venv_python_exists": config.VENV_PYTHON.exists(),
            "path_entries": [
                p for p in os.environ.get("PATH", "").split(os.pathsep) if p.strip()
            ],
            "proxy_env": {
                k: os.environ.get(k) for k in ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY")
                if os.environ.get(k)
            },
            "free_disk_gb": _disk_free_gb(str(config.BACKEND_DIR.drive or "C:\\")),
        },
    }

    def add(level: str, msg: str) -> None:
        findings.append({"level": level, "message": msg})

    py_paths = report["environment"]["python_on_path"]
    if py_paths:
        rc, out, err = procutil.run_capture([py_paths[0], "--version"], timeout=20)
        ver = (out or err).strip()
        add("info", f"Python ditemukan: {py_paths[0]} -> {ver}")
        m = None
        import re
        m = re.search(r"(\d+)\.(\d+)", ver)
        if m and (int(m.group(1)), int(m.group(2))) < (3, 10):
            add("error", f"Versi Python {ver} < 3.10 — install Python 3.10+ dari python.org.")
    else:
        add("error", "Tidak ada python.exe di PATH — install Python atau perbaiki PATH.")

    if not report["environment"]["venv_python_exists"]:
        add("warn", f"Venv belum ada di {config.VENV_DIR} — jalankan Setup.")
    else:
        rc, out, err = procutil.run_capture(
            [str(config.VENV_PYTHON), "-m", "pip", "--version"], timeout=60
        )
        if rc == 0:
            add("info", f"Venv OK: {(out or '').strip()}")
        else:
            add("error", f"Venv python rusak (rc={rc}): {(err or out)[:200]}")

    winget = report["environment"]["winget"]
    if not winget:
        add("warn", "winget tidak ditemukan — install nmap akan pakai fallback unduhan MSI resmi.")

    if component == "nmap":
        nm = report["environment"]["nmap"]
        if nm:
            rc, out, _ = procutil.run_capture([nm[0], "--version"], timeout=30)
            add("info" if rc == 0 else "error",
                f"nmap {nm[0]} --version rc={rc}: {(out or '').strip().splitlines()[:1]}")
        else:
            add("error", "nmap.exe tidak ada di PATH. Biasanya di C:\\Program Files (x86)\\Nmap\\.")
            add("info", "Solusi: klik Setup ulang dan setujui UAC, atau install manual dari nmap.org.")
    elif component == "sqlmap":
        if config.SQLMAP_DIR.exists():
            sm = config.SQLMAP_DIR / "sqlmap.py"
            if sm.exists():
                rc, out, _ = procutil.run_capture(
                    [str(config.VENV_PYTHON), str(sm), "--version"],
                    cwd=config.SQLMAP_DIR, timeout=120,
                )
                add("info" if rc == 0 else "error",
                    f"sqlmap --version rc={rc}: {(out or '').strip()[:120]}")
            else:
                add("error", f"Folder {config.SQLMAP_DIR} ada tapi sqlmap.py hilang — hapus folder lalu Setup ulang.")
        else:
            add("error", "sqlmap belum diunduh — jalankan Setup.")
    elif component == "wordlists":
        for fname in config.DEFAULT_WORDLIST_FILES:
            p = config.WORDLISTS_DIR / fname
            if p.exists() and p.stat().st_size > 0:
                add("info", f"OK: {fname} ({p.stat().st_size // 1024} KB)")
            else:
                add("error", f"Hilang/kosong: {fname} — jalankan Setup ulang.")

    try:
        with socket.create_connection((config.HOST, config.PORT), timeout=2):
            add("warn", f"Port {config.PORT} sudah dipakai (kemungkinan backend lain).")
    except OSError:
        add("info", f"Port {config.PORT} bebas.")

    report["summary"] = (
        f"{sum(1 for f in findings if f['level'] == 'error')} error, "
        f"{sum(1 for f in findings if f['level'] == 'warn')} warning"
    )
    return report
