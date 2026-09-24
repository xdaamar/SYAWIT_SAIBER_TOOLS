"""Component registry for Smart Setup.

Every component knows how to detect itself (existence + version vs the
minimum in versions.json), install itself idempotently, and verify the
result. Components that are already OK are skipped by the orchestrator —
never reinstalled.
"""
from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import zipfile
from pathlib import Path

from ... import config
from .. import process as procutil
from .diagnostics import SetupError, SUGGESTIONS, classify_error

SUGGESTIONS_PYTHON = SUGGESTIONS["python_too_old"]

VERSIONS = json.loads((Path(__file__).parent / "versions.json").read_text("utf-8"))

STATUS_OK, STATUS_MISSING, STATUS_OUTDATED, STATUS_BROKEN, STATUS_PARTIAL = (
    "ok", "missing", "outdated", "broken", "partial",
)


def parse_version(text: str) -> tuple:
    m = re.search(r"(\d+(?:\.\d+)+)", text or "")
    if not m:
        return (0,)
    return tuple(int(p) for p in m.group(1).split("."))


def compare_version(found: tuple, min_version: str) -> int:
    """1 = found >= min, -1 = found < min, 0 = unknown."""
    if not found or found == (0,):
        return 0
    return 1 if found >= parse_version(min_version) else -1


def _detect_version(cmd: list, pattern: str = r"(\d+(?:\.\d+)+)", timeout: int = 60) -> tuple:
    rc, out, err = procutil.run_capture(cmd, timeout=timeout)
    m = re.search(pattern, (out or "") + (err or ""))
    return tuple(int(p) for p in m.group(1).split(".")) if m else ()


class Component:
    name: str = "base"
    title: str = "Base"
    optional: bool = False

    def detect(self) -> dict:
        raise NotImplementedError

    def install(self, log) -> None:
        raise NotImplementedError

    def verify(self) -> dict:
        return self.detect()

    # -- helpers ------------------------------------------------------------
    def _status(self, version_found: tuple, extra: dict | None = None) -> dict:
        spec = VERSIONS.get(self.name, {})
        cmp_res = compare_version(version_found, spec.get("min", "0")) if version_found else 0
        status = {1: STATUS_OK, 0: STATUS_BROKEN, -1: STATUS_OUTDATED}[cmp_res]
        d = {
            "component": self.name,
            "title": self.title,
            "optional": self.optional,
            "status": status,
            "installed": version_found != (),
            "version": ".".join(str(x) for x in version_found) if version_found else None,
            "required": spec.get("min"),
            "note": spec.get("note"),
        }
        if extra:
            d.update(extra)
        return d

    def _install_fail(self, rc: int, err: str, context: str) -> SetupError:
        return classify_error(exit_code=rc, stderr=err, context=context)


class PythonComponent(Component):
    name, title = "python", "Python 3.10+"

    def detect(self) -> dict:
        for cand in (["py", "-3"], ["python"], ["python3"]):
            ver = _detect_version(cand + ["--version"])
            if ver:
                return self._status(ver, {"path": cand[0]})
        return self._status(())


class PipComponent(Component):
    name, title = "pip", "pip (di venv)"

    def detect(self) -> dict:
        if not config.VENV_PYTHON.exists():
            return self._status(())
        ver = _detect_version([str(config.VENV_PYTHON), "-m", "pip", "--version"])
        return self._status(ver)

    def install(self, log) -> None:
        rc, out, err = procutil.run_capture(
            [str(config.VENV_PYTHON), "-m", "pip", "install", "--upgrade", "pip"],
            timeout=300,
        )
        log(out)
        log(err)
        if rc != 0:
            raise self._install_fail(rc, err, "pip upgrade")


class VenvComponent(Component):
    name, title = "venv", "Virtual environment"

    def detect(self) -> dict:
        ok = config.VENV_PYTHON.exists() and config.VENV_PIP.exists()
        return {"component": self.name, "title": self.title, "optional": False,
                "status": STATUS_OK if ok else STATUS_MISSING, "installed": ok,
                "version": "3.14" if ok else None, "required": "exists"}

    def install(self, log) -> None:
        if config.VENV_DIR.exists():
            log("[i] venv sudah ada, skip pembuatan")
            return
        py = PythonComponent().detect()
        if py["status"] not in (STATUS_OK, STATUS_OUTDATED):
            raise SetupError(
                "python_too_old",
                "Python 3.10+ tidak ditemukan di PATH",
                suggestions=SUGGESTIONS_PYTHON,
            )
        launcher = py.get("path", "python")
        cmd = [launcher, "-m", "venv", str(config.VENV_DIR)]
        if launcher == "py":
            cmd = ["py", "-3", "-m", "venv", str(config.VENV_DIR)]
        rc, out, err = procutil.run_capture(cmd, timeout=300)
        log(out)
        log(err)
        if rc != 0 or not config.VENV_PYTHON.exists():
            raise self._install_fail(rc, err, "venv creation")


class PipDepsComponent(Component):
    name, title = "pip_deps", "Dependencies Python (requirements.txt)"

    def detect(self) -> dict:
        if not config.VENV_PYTHON.exists():
            return {"component": self.name, "title": self.title, "status": STATUS_MISSING,
                    "installed": False, "version": None, "required": "requirements.txt"}
        rc, out, _ = procutil.run_capture(
            [str(config.VENV_PYTHON), "-m", "pip", "list", "--format=json"], timeout=120
        )
        if rc != 0:
            return {"component": self.name, "title": self.title, "status": STATUS_BROKEN,
                    "installed": False, "version": None, "required": "requirements.txt"}
        try:
            installed = {p["name"].lower(): p["version"] for p in json.loads(out)}
        except ValueError:
            installed = {}
        missing = []
        for line in (config.BACKEND_DIR / "requirements.txt").read_text("utf-8").splitlines():
            line = line.split("#")[0].strip()
            if not line:
                continue
            pkg = re.split(r"[<>=~!\[]", line)[0].strip().lower()
            if pkg and pkg not in installed:
                missing.append(pkg)
        status = STATUS_MISSING if missing else STATUS_OK
        return {"component": self.name, "title": self.title, "status": status,
                "installed": not missing, "version": f"{len(installed)} paket",
                "required": "requirements.txt", "missing_packages": missing}

    def install(self, log) -> None:
        rc, out, err = procutil.run_capture(
            [str(config.VENV_PYTHON), "-m", "pip", "install", "-r",
             str(config.BACKEND_DIR / "requirements.txt")],
            timeout=1800,
        )
        log(out[-4000:])
        log(err[-2000:])
        if rc != 0:
            raise self._install_fail(rc, err, "pip install -r requirements.txt")

    def verify(self) -> dict:
        d = self.detect()
        if d["status"] != STATUS_OK:
            d["status"] = STATUS_BROKEN
        return d


class GitComponent(Component):
    name, title = "git", "Git"

    def detect(self) -> dict:
        ver = _detect_version(["git", "--version"])
        return self._status(ver, {"path": shutil.which("git")})


class NmapComponent(Component):
    name, title = "nmap", "Nmap"

    def detect(self) -> dict:
        exe = shutil.which("nmap")
        if not exe:
            for cand in (r"C:\Program Files (x86)\Nmap\nmap.exe",
                         r"C:\Program Files\Nmap\nmap.exe"):
                if Path(cand).exists():
                    exe = cand
                    break
        if not exe:
            return self._status((), {"path": None})
        ver = _detect_version([exe, "--version"], timeout=90)
        return self._status(ver, {"path": exe})

    def install(self, log) -> None:
        # Preferred: winget (may trigger UAC). Fallback: official MSI installer.
        if shutil.which("winget"):
            log("[i] menjalankan: winget install Insecure.Nmap (setujui UAC bila muncul)")
            rc, out, err = procutil.run_capture(
                ["winget", "install", "--id", "Insecure.Nmap", "--accept-source-agreements",
                 "--accept-package-agreements", "--silent"],
                timeout=900,
            )
            log(out[-3000:])
            log(err[-1500:])
            if rc == 0:
                return
            log(f"[!] winget rc={rc}, mencoba fallback installer MSI resmi...")
            if classify_error(stderr=err).category == "permission":
                raise self._install_fail(rc, err, "winget install nmap (UAC)")
        self._install_msi(log)

    def _install_msi(self, log) -> None:
        import urllib.request
        url = "https://nmap.org/dist/nmap-7.95-setup.exe"
        dest = config.TOOLS_DIR / "nmap-setup.exe"
        log(f"[i] mengunduh {url} ...")
        try:
            urllib.request.urlretrieve(url, dest)  # noqa: S310 - fixed official URL
        except Exception as e:
            raise classify_error(exception=e, context="unduh installer nmap") from e
        log("[i] menjalankan installer — SETUJUI prompt UAC yang muncul")
        rc, out, err = procutil.run_capture([str(dest), "/S"], timeout=1800)
        log(out)
        log(err)
        if rc not in (0,):
            log(f"[!] installer rc={rc} (bisa jadi UAC ditolak)")


class SqlmapComponent(Component):
    name, title = "sqlmap", "sqlmap"

    def detect(self) -> dict:
        sm = config.SQLMAP_DIR / "sqlmap.py"
        if not sm.exists():
            return self._status((), {"path": str(sm)})
        ver = _detect_version([str(config.VENV_PYTHON), str(sm), "--version"],
                              timeout=300)
        return self._status(ver, {"path": str(sm)})

    def install(self, log) -> None:
        import urllib.request
        dest = config.SQLMAP_DIR
        if dest.exists():
            log("[i] folder sqlmap ada tapi rusak — hapus dulu")
            shutil.rmtree(dest, ignore_errors=True)
        config.TOOLS_DIR.mkdir(parents=True, exist_ok=True)
        if shutil.which("git"):
            rc, out, err = procutil.run_capture(
                ["git", "clone", "--depth", "1",
                 "https://github.com/sqlmapproject/sqlmap.git", str(dest)],
                timeout=900,
            )
            log(out)
            log(err)
            if rc == 0:
                return
            log(f"[!] git clone rc={rc}, fallback unduh zip...")
        zip_url = "https://github.com/sqlmapproject/sqlmap/archive/refs/heads/master.zip"
        zpath = config.TOOLS_DIR / "sqlmap.zip"
        log(f"[i] mengunduh {zip_url} ...")
        try:
            urllib.request.urlretrieve(zip_url, zpath)  # noqa: S310
        except Exception as e:
            raise classify_error(exception=e, context="unduh sqlmap zip") from e
        with zipfile.ZipFile(zpath) as z:
            z.extractall(config.TOOLS_DIR)
        src = config.TOOLS_DIR / "sqlmap-master"
        if src.exists():
            src.rename(dest)
        zpath.unlink(missing_ok=True)


class WordlistsComponent(Component):
    name, title = "wordlists", "Wordlists (SecLists subset)"

    def _missing(self) -> list[str]:
        return [f for f in config.DEFAULT_WORDLIST_FILES
                if not (config.WORDLISTS_DIR / f).exists()
                or (config.WORDLISTS_DIR / f).stat().st_size == 0]

    def detect(self) -> dict:
        files = list(config.DEFAULT_WORDLIST_FILES)
        missing = self._missing()
        if not missing:
            status = STATUS_OK
        elif len(missing) < len(files):
            status = STATUS_PARTIAL
        else:
            status = STATUS_MISSING
        return {"component": self.name, "title": self.title, "status": status,
                "installed": len(missing) < len(files), "version": None,
                "required": f"{len(files)} file", "missing_files": missing}

    def install(self, log) -> None:
        import urllib.request
        config.WORDLISTS_DIR.mkdir(parents=True, exist_ok=True)
        errors = []
        for fname, url in config.DEFAULT_WORDLIST_FILES.items():
            dest = config.WORDLISTS_DIR / fname
            if dest.exists() and dest.stat().st_size > 0:
                log(f"[i] {fname} sudah ada, skip")
                continue
            log(f"[i] mengunduh {fname} ...")
            try:
                urllib.request.urlretrieve(url, dest)  # noqa: S310
            except Exception as e:
                errors.append(f"{fname}: {e}")
                log(f"[!] gagal: {fname}: {e}")
        if errors:
            raise classify_error(stderr="\n".join(errors),
                                 context="unduh wordlists")


class RsaCtfToolComponent(Component):
    name, title = "RsaCtfTool", "RsaCtfTool (opsional)"
    optional = True

    def detect(self) -> dict:
        ok = (config.RSACTFTOOL_DIR / "RsaCtfTool.py").exists()
        return {"component": self.name, "title": self.title, "optional": True,
                "status": STATUS_OK if ok else STATUS_MISSING, "installed": ok,
                "version": None, "required": "opsional"}

    def install(self, log) -> None:
        rc, out, err = procutil.run_capture(
            ["git", "clone", "--depth", "1",
             "https://github.com/RsaCtfTool/RsaCtfTool.git", str(config.RSACTFTOOL_DIR)],
            timeout=600,
        )
        log(out)
        log(err)
        if rc != 0:
            raise self._install_fail(rc, err, "git clone RsaCtfTool")


class WslComponent(Component):
    name, title = "wsl", "WSL (opsional, untuk ELF)"
    optional = True

    def detect(self) -> dict:
        rc, out, _ = procutil.run_capture(["wsl.exe", "--status"], timeout=60)
        ok = rc == 0 and bool(out.strip())
        return {"component": self.name, "title": self.title, "optional": True,
                "status": STATUS_OK if ok else STATUS_MISSING, "installed": ok,
                "version": None, "required": "opsional"}

    def install(self, log) -> None:
        raise SetupError("permission", "WSL harus diinstall manual",
                         suggestions=["Jalankan `wsl --install` di PowerShell admin",
                                      "Modul pwn tetap bisa analisis ELF tanpa WSL"])


# Ordered by dependency graph: python -> venv -> pip -> deps -> git -> nmap ->
# sqlmap -> wordlists -> optional extras.
COMPONENTS: list[Component] = [
    PythonComponent(),
    VenvComponent(),
    PipComponent(),
    PipDepsComponent(),
    GitComponent(),
    NmapComponent(),
    SqlmapComponent(),
    WordlistsComponent(),
    RsaCtfToolComponent(),
    WslComponent(),
]

COMPONENT_MAP = {c.name: c for c in COMPONENTS}


def detect_all() -> list[dict]:
    return [c.detect() for c in COMPONENTS]


def overall_ready(statuses: list[dict]) -> bool:
    return all(
        s["status"] in (STATUS_OK, STATUS_OUTDATED)
        for s in statuses if not s.get("optional")
    )
