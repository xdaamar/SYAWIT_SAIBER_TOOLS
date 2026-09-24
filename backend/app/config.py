"""Central configuration & paths for the CTFSuite backend."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path

APP_NAME = "CTFSuite"
VERSION = "0.1.0"


def _env_path(name: str, default: Path) -> Path:
    v = os.environ.get(name)
    return Path(v).resolve() if v else default


# --- Directory layout -------------------------------------------------------
# config.py lives in <repo>/backend/app/
BACKEND_DIR = _env_path("CTFSUITE_BACKEND_DIR", Path(__file__).resolve().parent.parent)
APP_DIR = BACKEND_DIR / "app"
TOOLS_DIR = _env_path("CTFSUITE_TOOLS_DIR", BACKEND_DIR / "tools")
LOGS_DIR = _env_path("CTFSUITE_LOGS_DIR", APP_DIR / "logs")
DATA_DIR = _env_path("CTFSUITE_DATA_DIR", APP_DIR / "data")
SQLMAP_DIR = TOOLS_DIR / "sqlmap"
RSACTFTOOL_DIR = TOOLS_DIR / "RsaCtfTool"
WORDLISTS_DIR = TOOLS_DIR / "wordlists"
VENV_DIR = BACKEND_DIR / ".venv"
VENV_PYTHON = VENV_DIR / "Scripts" / "python.exe"
VENV_PIP = VENV_DIR / "Scripts" / "pip.exe"
PORT_FILE = BACKEND_DIR / ".port"

REPO_DIR = BACKEND_DIR.parent
SCRIPTS_DIR = REPO_DIR / "scripts"
NMAP_ELEVATED_SCRIPT = SCRIPTS_DIR / "setup_admin_nmap.ps1"


def _appdata_dir() -> Path:
    base = (
        os.environ.get("CTFSUITE_APPDATA_DIR")
        or os.environ.get("APPDATA")
        or str(Path.home())
    )
    return Path(base) / APP_NAME


APPDATA_DIR = _appdata_dir()
SETTINGS_FILE = APPDATA_DIR / "settings.json"
SETUP_STATUS_FILE = APPDATA_DIR / "setup_status.json"

# Wordlist files the setup downloads (small curated subset of SecLists).
DEFAULT_WORDLIST_FILES = {
    "web_content_common.txt": "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/common.txt",
    "web_content_quickhits.txt": "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Discovery/Web-Content/quickhits.txt",
    "passwords_top_1000000.txt": "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10-million-password-list-top-1000000.txt",
    "passwords_top_100000.txt": "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Passwords/Common-Credentials/10-million-password-list-top-100000.txt",
    "usernames_top.txt": "https://raw.githubusercontent.com/danielmiessler/SecLists/master/Usernames/Names/names.txt",
}

DEFAULT_SETTINGS = {
    "disclaimer_accepted": False,
    "proxy": "",
    "verify_tls": False,
    "http_timeout": 10,
    "rate_limit_delay": 0.2,
    "wordlist_passwords": str(WORDLISTS_DIR / "passwords_top_100000.txt"),
    "wordlist_usernames": str(WORDLISTS_DIR / "usernames_top.txt"),
    "wordlist_webcontent": str(WORDLISTS_DIR / "web_content_common.txt"),
    "theme": "dark",
}

_lock = threading.Lock()


def ensure_dirs() -> None:
    for p in (BACKEND_DIR, APP_DIR, TOOLS_DIR, LOGS_DIR, DATA_DIR, WORDLISTS_DIR, APPDATA_DIR):
        p.mkdir(parents=True, exist_ok=True)


def load_json(path: Path, default):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        tmp = path.with_suffix(path.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        tmp.replace(path)


def load_settings() -> dict:
    s = dict(DEFAULT_SETTINGS)
    s.update(load_json(SETTINGS_FILE, {}))
    return s


def save_settings(update: dict) -> dict:
    s = load_settings()
    s.update(update)
    save_json(SETTINGS_FILE, s)
    return s


# --- Server -----------------------------------------------------------------
HOST = "127.0.0.1"
PORT = int(os.environ.get("CTFSUITE_PORT", "8765"))


def api_base() -> str:
    return f"http://{HOST}:{PORT}"
