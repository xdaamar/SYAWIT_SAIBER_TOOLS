"""Wordlist helper: list wordlist files downloaded by setup, with line counts,
and resolve a wordlist name to a concrete path."""
from __future__ import annotations

from pathlib import Path

from .. import config


def list_wordlists() -> list[dict]:
    out = []
    if config.WORDLISTS_DIR.exists():
        for f in sorted(config.WORDLISTS_DIR.iterdir()):
            if f.is_file() and f.suffix in (".txt", ".lst"):
                try:
                    with open(f, "rb") as fh:
                        n = sum(1 for _ in fh)
                except OSError:
                    n = -1
                out.append({"name": f.name, "path": str(f), "lines": n,
                            "size_kb": round(f.stat().st_size / 1024, 1)})
    return out


def resolve(name_or_path: str) -> Path | None:
    """Accept a full path, or a wordlist name inside WORDLISTS_DIR."""
    p = Path(name_or_path)
    if p.exists():
        return p
    cand = config.WORDLISTS_DIR / name_or_path
    if cand.exists():
        return cand
    return None
