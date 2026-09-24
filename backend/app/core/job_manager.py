"""Job registry: every long-running operation (scan/exploit/brute) is a Job.

Jobs buffer their output lines, fan them out to WebSocket subscribers, and
can be cancelled (process-tree kill on Windows)."""
from __future__ import annotations

import queue
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from . import process as procutil

MAX_LINES = 5000


@dataclass
class Job:
    id: str
    kind: str
    title: str
    command: str
    status: str = "running"  # running | done | failed | cancelled
    created_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    exit_code: Optional[int] = None
    error: Optional[str] = None
    result: Optional[dict] = None
    lines: list = field(default_factory=list)
    proc: object = None
    cancel_flag: threading.Event = field(default_factory=threading.Event)
    _subs: list = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def append(self, line: str, stream: str = "out") -> None:
        with self._lock:
            entry = {
                "i": len(self.lines),
                "t": round(time.time() - self.created_at, 2),
                "s": stream,
                "line": str(line),
            }
            self.lines.append(entry)
            overflow = len(self.lines) - MAX_LINES
            if overflow > 0:
                del self.lines[:overflow]
            for q in list(self._subs):
                try:
                    q.put_nowait(entry)
                except queue.Full:
                    pass

    def subscribe(self) -> "queue.Queue":
        q: "queue.Queue" = queue.Queue(maxsize=10000)
        with self._lock:
            self._subs.append(q)
        return q

    def unsubscribe(self, q) -> None:
        with self._lock:
            if q in self._subs:
                self._subs.remove(q)

    def finish(self, status: str, exit_code: Optional[int] = None,
               error: Optional[str] = None, result: Optional[dict] = None) -> None:
        with self._lock:
            self.status = status
            self.exit_code = exit_code
            self.error = error
            if result is not None:
                self.result = result
            self.finished_at = time.time()
            end = {
                "i": -1,
                "event": "end",
                "status": status,
                "exit_code": exit_code,
                "error": error,
            }
            for q in list(self._subs):
                try:
                    q.put_nowait(end)
                except queue.Full:
                    pass

    def to_dict(self, with_lines: bool = False) -> dict:
        d = {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "command": self.command,
            "status": self.status,
            "created_at": self.created_at,
            "finished_at": self.finished_at,
            "exit_code": self.exit_code,
            "error": self.error,
            "line_count": len(self.lines),
            "result": self.result,
        }
        if with_lines:
            d["lines"] = self.lines
        return d


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._async_tasks: set = set()

    def create(self, kind: str, title: str, command: str) -> Job:
        job = Job(id=uuid.uuid4().hex[:12], kind=kind, title=title, command=command)
        with self._lock:
            self._jobs[job.id] = job
            if len(self._jobs) > 300:
                for jid in [j for j, jj in self._jobs.items()
                            if jj.status != "running"][:-300]:
                    self._jobs.pop(jid, None)
        return job

    def get(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def list(self) -> list[dict]:
        with self._lock:
            items = sorted(self._jobs.values(), key=lambda j: j.created_at, reverse=True)
        return [j.to_dict() for j in items[:100]]

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if not job or job.status != "running":
            return False
        job.cancel_flag.set()
        task = getattr(job, "_async_task", None)
        if task is not None:
            task.cancel()
            return True
        procutil.kill_tree(job.proc)
        return True


jobs = JobManager()


def launch_async_job(
    mgr: JobManager,
    kind: str,
    title: str,
    description: str,
    coro_fn,
) -> Job:
    """Create a job driven by a python coroutine instead of a subprocess.

    coro_fn(append) -> result dict; append(line, stream="out") streams lines.
    Must be called from async context (FastAPI handler).
    """
    import asyncio

    job = mgr.create(kind=kind, title=title, command=description)
    job.append(f"$ {description}", stream="cmd")

    async def _runner():
        try:
            result = await coro_fn(lambda line, stream="out": job.append(line, stream))
            if job.cancel_flag.is_set():
                job.finish("cancelled")
            else:
                job.finish("done", exit_code=0, result=result)
        except asyncio.CancelledError:
            job.finish("cancelled", error="dibatalkan user")
            raise
        except Exception as e:
            job.append(f"[!] error: {e}", stream="err")
            job.finish("failed", exit_code=1, error=str(e))

    task = asyncio.create_task(_runner())
    job._async_task = task  # type: ignore[attr-defined]
    mgr._async_tasks.add(task)
    task.add_done_callback(mgr._async_tasks.discard)
    return job


def launch_process_job(
    mgr: JobManager,
    kind: str,
    title: str,
    cmd: list,
    cwd: Optional[Path] = None,
    build_result: Optional[Callable[[Job, int, list], dict]] = None,
    env_extra: Optional[dict] = None,
    on_line: Optional[Callable[[Job, str], None]] = None,
) -> Job:
    """Create a job that runs a subprocess with live streamed output."""
    job = mgr.create(kind=kind, title=title, command=" ".join(str(c) for c in cmd))

    def _line(line: str) -> None:
        job.append(line)
        if on_line:
            try:
                on_line(job, line)
            except Exception:
                pass

    def _exit(rc: int) -> None:
        if job.cancel_flag.is_set():
            job.finish("cancelled", exit_code=rc)
            return
        result = None
        if build_result:
            try:
                result = build_result(job, rc, [e["line"] for e in list(job.lines)])
            except Exception as e:  # never lose the job over a parse hiccup
                job.append(f"[!] result parse error: {e}", stream="err")
        if rc == 0:
            job.finish("done", exit_code=rc, result=result)
        else:
            job.finish("failed", exit_code=rc, error=f"exit code {rc}", result=result)

    job.append(f"$ {job.command}", stream="cmd")
    job.proc, _ = procutil.stream_process(
        cmd, cwd=cwd, env_extra=env_extra, on_line=_line, on_exit=_exit
    )
    return job
