"""Error classification for setup failures.

Classifies (exit_code, stderr, exception) into a SetupError with a human
message, evidence lines and concrete fix suggestions, so the user can fix
problems quickly instead of staring at raw pip dumps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES = {
    "network": "Network / koneksi",
    "permission": "Permission / UAC",
    "winget_missing": "winget tidak tersedia",
    "antivirus_blocked": "Kemungkinan diblokir antivirus",
    "python_too_old": "Versi Python terlalu lama",
    "pip_conflict": "Konflik dependensi pip",
    "disk_full": "Disk penuh",
    "checksum_mismatch": "Checksum unduhan tidak cocok",
    "tool_broken": "Tool terinstall tapi tidak jalan",
    "port_in_use": "Port sudah dipakai",
    "unknown": "Error tidak diketahui",
}

PATTERNS = [
    ("network", r"timed?\s*out|timeout|connection\s*(reset|refused|timed)|"
     r"getaddrinfo failed|name or service not known|temporary failure in name resolution|"
     r"proxy|ssl|certificate verify failed|couldn't connect|network is unreachable|"
     r"winerror 10060|winerror 10061|winerror 10054"),
    ("permission", r"access is denied|permission denied|elevation|requires admin|"
     r"winerror 5\b|error 5\b|administrator|uac|0x8007"),
    ("winget_missing", r"winget.*not (found|recognized)|'winget' is not recognized"),
    ("antivirus_blocked", r"operation did not complete successfully because the file contains a virus|"
     r"blocked by (group policy|your administrator)|trojan|detected: |threat (found|detected)|"
     r"winerror 32\b|being used by another process"),
    ("python_too_old", r"requires Python|python_requires|no matching distribution.*python|"
     r"unsupported python"),
    ("pip_conflict", r"resolutionerror|resolvererror|conflict is caused by|"
     r"incompatible|cannot install .* because these package versions|"
     r"dependency conflict|no matching distribution"),
    ("disk_full", r"no space left on device|disk full|winerror 112\b|insufficient space"),
    ("checksum_mismatch", r"hash mismatch|checksum|sha256 mismatch|hash does not match"),
]


@dataclass
class SetupError:
    category: str
    message: str
    evidence: list = field(default_factory=list)
    suggestions: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "category_label": CATEGORIES.get(self.category, self.category),
            "message": self.message,
            "evidence": self.evidence,
            "suggestions": self.suggestions,
        }


SUGGESTIONS = {
    "network": [
        "Periksa koneksi internet dan proxy (Settings > Proxy).",
        "Coba lagi — error jaringan sering bersifat sementara.",
    ],
    "permission": [
        "Klik ulang step ini dan setujui prompt UAC Windows.",
        "Atau install komponen ini manual (lihat README bagian Troubleshooting).",
    ],
    "winget_missing": [
        "Install App Installer dari Microsoft Store untuk mendapat winget.",
        "Aplikasi akan otomatis memakai fallback unduhan langsung.",
    ],
    "antivirus_blocked": [
        "Tambahkan folder project ini ke exclusion Windows Defender / antivirus.",
        "Pastikan file tidak dikarantina lalu klik Retry.",
    ],
    "python_too_old": [
        "Install Python 3.10+ dari python.org atau `winget install Python.Python.3.12`.",
    ],
    "pip_conflict": [
        "Jalankan Doctor untuk melihat paket yang bentrok.",
        "Hapus backend/.venv lalu jalankan Setup ulang (venv dibuat bersih).",
    ],
    "disk_full": [
        "Kosongkan ruang disk (butuh minimal ~2 GB) lalu Retry.",
    ],
    "checksum_mismatch": [
        "Kemungkinan unduhan korup — klik Retry untuk mengunduh ulang.",
    ],
    "tool_broken": [
        "Jalankan Doctor untuk diagnosis detail.",
        "Hapus folder tool lalu jalankan Setup ulang.",
    ],
    "port_in_use": [
        "Port 8765 dipakai proses lain. Matikan proses itu atau jalankan ulang app.",
    ],
    "unknown": [
        "Klik Doctor untuk diagnosis mendalam, atau buka file log di menu Setup.",
    ],
}


def _last_lines(text: str, n: int = 6) -> list:
    lines = [ln.rstrip() for ln in (text or "").splitlines() if ln.strip()]
    return lines[-n:]


def classify_error(
    exit_code: int | None = None,
    stderr: str = "",
    exception: Exception | None = None,
    context: str = "",
) -> SetupError:
    text = "\n".join(filter(None, [stderr, str(exception or "")])).lower()
    category = "unknown"
    if exception is not None:
        name = type(exception).__name__.lower()
        if any(k in text or k in name for k in ("timeout", "connection", "getaddrinfo", "ssl")):
            category = "network"
    if category == "unknown":
        for cat, pat in PATTERNS:
            if re.search(pat, text):
                category = cat
                break
    return SetupError(
        category=category,
        message=(str(exception)[:300] if exception else
                 f"exit code {exit_code}" + (f" ({context})" if context else "")),
        evidence=_last_lines(stderr or str(exception or "")),
        suggestions=SUGGESTIONS.get(category, SUGGESTIONS["unknown"]),
    )
