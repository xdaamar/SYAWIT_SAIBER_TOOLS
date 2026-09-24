"""Windows-safe subprocess helpers with UTF-8 tolerant decoding."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable, Optional, Sequence

CREATE_NO_WINDOW = 0x08000000  # Windows-only; ignored on other platforms


def popen_kwargs(cwd: Optional[Path] = None, env_extra: Optional[dict] = None) -> dict:
    env = os.environ.copy()
    if env_extra:
        env.update({k: str(v) for k, v in env_extra.items()})
    return {
        "cwd": str(cwd) if cwd else None,
        "env": env,
        "stdin": subprocess.DEVNULL,
        "creationflags": CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    }


def decode(b: bytes) -> str:
    """Decode tool output tolerantly (tools emit mixed encodings on Windows)."""
    if b is None:
        return ""
    for enc in ("utf-8", "cp1252"):
        try:
            return b.decode(enc)
        except UnicodeDecodeError:
            continue
    return b.decode("utf-8", errors="replace")


def run_capture(
    cmd: Sequence[str],
    cwd: Optional[Path] = None,
    timeout: Optional[float] = 60,
    env_extra: Optional[dict] = None,
) -> tuple[int, str, str]:
    """Run a command, capture output, return (rc, stdout, stderr)."""
    try:
        proc = subprocess.run(
            list(cmd),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            **popen_kwargs(cwd, env_extra),
        )
        return proc.returncode, decode(proc.stdout), decode(proc.stderr)
    except FileNotFoundError as e:
        return 127, "", f"executable not found: {e}"
    except subprocess.TimeoutExpired as e:
        out = decode(e.stdout) if e.stdout else ""
        err = decode(e.stderr) if e.stderr else ""
        return 124, out, err or f"timeout after {timeout}s"


def stream_process(
    cmd,
    cwd: Optional[Path] = None,
    env_extra: Optional[dict] = None,
    on_line: Optional[Callable[[str], None]] = None,
    on_exit: Optional[Callable[[int], None]] = None,
):
    """Start a process whose combined output is pumped to on_line on a thread.

    Returns (proc, reader_thread)."""
    proc = subprocess.Popen(
        list(cmd),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        **popen_kwargs(cwd, env_extra),
    )

    def _pump() -> None:
        assert proc.stdout is not None
        for raw in iter(proc.stdout.readline, b""):
            line = decode(raw).rstrip("\r\n")
            if on_line:
                on_line(line)
        try:
            proc.stdout.close()
        except OSError:
            pass
        rc = proc.wait()
        if on_exit:
            on_exit(rc)

    t = threading.Thread(target=_pump, daemon=True)
    t.start()
    return proc, t


def kill_tree(proc) -> None:
    """Terminate a process and its children (Windows-safe)."""
    if proc is None:
        return
    try:
        import psutil

        parent = psutil.Process(proc.pid)
        for child in parent.children(recursive=True):
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        parent.kill()
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
