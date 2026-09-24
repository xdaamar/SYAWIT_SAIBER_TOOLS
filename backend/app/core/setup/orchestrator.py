"""Setup orchestrator: run component steps sequentially with pre-checks,
verify, per-step state, resume and clear error reporting."""
from __future__ import annotations

import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from ... import config
from . import components as comps
from .components import COMPONENTS, STATUS_OK, STATUS_OUTDATED
from .diagnostics import SetupError, classify_error
from ..state import read_setup_status, write_setup_status


class SetupRunner:
    """Runs the smart setup. One run at a time; cancel supported."""

    def __init__(self) -> None:
        self._running = False
        self._cancel = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._running

    def cancel(self) -> bool:
        if not self._running:
            return False
        self._cancel.set()
        return True

    def start_async(self, only: list[str] | None, on_event) -> bool:
        if self._running:
            return False
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run, args=(only, on_event), daemon=True
        )
        self._thread.start()
        return True

    # ------------------------------------------------------------------
    def _log_file(self) -> Path:
        config.ensure_dirs()
        return config.LOGS_DIR / f"setup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    def _run(self, only: list[str] | None, emit) -> None:
        self._running = True
        log_path = self._log_file()
        fh = open(log_path, "w", encoding="utf-8")

        def log(msg: str) -> None:
            stamp = datetime.now().strftime("%H:%M:%S")
            fh.write(f"[{stamp}] {msg}\n")
            fh.flush()
            emit("log", {"line": str(msg)})

        emit("start", {"log_file": str(log_path)})
        log(f"=== CTFSuite Smart Setup dimulai ({log_path.name}) ===")

        selected = [c for c in COMPONENTS if not only or c.name in only]
        failed: set[str] = set()
        steps: list[dict] = []
        errors: dict[str, dict] = {}

        for comp in selected:
            name = comp.name
            if self._cancel.is_set():
                log("[!] Setup dibatalkan user")
                emit("cancelled", {})
                break

            # Skip steps whose dependencies failed
            deps_failed = [d for d in getattr(comp, "depends_on", []) if d in failed]
            if deps_failed:
                log(f"[-] {comp.title}: dilewati (dependensi gagal: {', '.join(deps_failed)})")
                steps.append({"name": name, "status": "skipped",
                              "reason": f"dependensi gagal: {deps_failed}"})
                emit("step", {"component": name, "status": "skipped"})
                failed.add(name)
                continue

            emit("step", {"component": name, "status": "precheck"})
            try:
                pre = comp.detect()
            except Exception as e:
                pre = {}
                log(f"[!] detect {name} error: {e}")
            if pre.get("status") == STATUS_OK:
                log(f"[=] {comp.title}: sudah OK (versi {pre.get('version')}), skip")
                steps.append({"name": name, "status": "skipped_up_to_date",
                              "version": pre.get("version")})
                emit("step", {"component": name, "status": "ok",
                              "version": pre.get("version")})
                continue

            log(f"[>] {comp.title}: {pre.get('status', 'missing')} — menginstall...")
            emit("step", {"component": name, "status": "installing"})
            try:
                comp.install(log)
                post = comp.verify()
                if post.get("status") not in (STATUS_OK, STATUS_OUTDATED) and not comp.optional:
                    err = classify_error(stderr="verify gagal setelah install",
                                         context=name)
                    err.message = (f"{comp.title} terinstall tapi verifikasi gagal "
                                   f"(status: {post.get('status')})")
                    raise err
                log(f"[+] {comp.title}: OK ({post.get('version') or post.get('status')})")
                steps.append({"name": name, "status": "installed",
                              "version": post.get("version")})
                emit("step", {"component": name, "status": "ok",
                              "version": post.get("version")})
            except SetupError as e:
                log(f"[!] {comp.title} GAGAL: [{e.category}] {e.message}")
                for s in e.suggestions:
                    log(f"    saran: {s}")
                errors[name] = e.to_dict()
                steps.append({"name": name, "status": "error", "error": e.to_dict()})
                emit("step", {"component": name, "status": "error", "error": e.to_dict()})
                if not comp.optional:
                    failed.add(name)
            except Exception as e:  # unexpected — still classify it
                err = classify_error(exception=e, context=name)
                log(f"[!] {comp.title} GAGAL tak terduga: {traceback.format_exc(limit=3)}")
                errors[name] = err.to_dict()
                steps.append({"name": name, "status": "error", "error": err.to_dict()})
                emit("step", {"component": name, "status": "error", "error": err.to_dict()})
                if not comp.optional:
                    failed.add(name)

        statuses = comps.detect_all()
        ready = comps.overall_ready(statuses)
        write_setup_status({
            "last_run": time.time(),
            "ready": ready,
            "steps": steps,
            "errors": errors,
            "components": {s["component"]: s for s in statuses},
        })
        log(f"=== Setup selesai. ready={ready}, "
            f"{len(errors)} error ===")
        emit("done", {"ready": ready, "log_file": str(log_path)})
        fh.close()
        self._running = False

    def retry_component(self, name: str, emit) -> bool:
        comp = comps.COMPONENT_MAP.get(name)
        if not comp or self._running:
            return False
        return self.start_async(only=[name], emit=emit)


runner = SetupRunner()
