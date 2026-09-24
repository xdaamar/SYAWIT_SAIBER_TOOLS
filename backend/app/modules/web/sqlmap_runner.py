"""SQLMap integration: build a command from a target/form description and
run it as a streamed job."""
from __future__ import annotations

import shutil
from pathlib import Path

from ... import config


def sqlmap_cmd() -> list | None:
    """Locate sqlmap: tools/sqlmap/sqlmap.py first, then PATH."""
    sm = config.SQLMAP_DIR / "sqlmap.py"
    if sm.exists():
        return [str(config.VENV_PYTHON), str(sm)]
    exe = shutil.which("sqlmap")
    if exe:
        return [exe]
    return None


def build_command(url: str, data: str = "", level: int = 1, risk: int = 1,
                  forms: bool = False, dump: bool = False,
                  cookie: str = "", extra: str = "") -> list | None:
    base = sqlmap_cmd()
    if not base:
        return None
    out_dir = config.DATA_DIR / "sqlmap_out"
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        *base,
        "-u", url,
        "--batch",
        "--output-dir", str(out_dir),
        f"--level={max(1, min(5, level))}",
        f"--risk={max(1, min(3, risk))}",
    ]
    if data:
        cmd += ["--data", data]
    if forms:
        cmd.append("--forms")
    if cookie:
        cmd += ["--cookie", cookie]
    if dump:
        cmd.append("--dump")
    if extra:
        cmd.extend(extra.split())
    return cmd


def parse_summary(lines: list[str]) -> dict:
    """Extract key findings from sqlmap console output."""
    summary = {"injections": [], "dbms": None, "waf": None}
    for ln in lines:
        low = ln.lower()
        if "parameter:" in low and ("injectable" in low or "might be injectable" in low):
            summary["injections"].append(ln.strip())
        if "back-end dbms:" in low:
            summary["dbms"] = ln.split(":", 1)[-1].strip()
        if "waf/ips" in low:
            summary["waf"] = ln.strip()
    return summary
