"""Hash toolkit: identify hash types and crack with local wordlists."""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

IDENT = [
    ("md5", 32), ("sha1", 40), ("sha224", 56), ("sha256", 64), ("sha384", 96),
    ("sha512", 128), ("blake2b(64)", 128), ("blake2s(32)", 64),
]

ALGOS = {
    "md5": hashlib.md5, "sha1": hashlib.sha1, "sha224": hashlib.sha224,
    "sha256": hashlib.sha256, "sha384": hashlib.sha384, "sha512": hashlib.sha512,
}


def identify(h: str) -> list[dict]:
    h = h.strip().lower()
    out = []
    for name, ln in IDENT:
        if ln == len(h) and re.fullmatch(r"[0-9a-f]+", h):
            conf = "high" if name.startswith(("md5", "sha1", "sha256", "sha512")) else "low"
            out.append({"type": name, "length": ln, "confidence": conf})
    if re.fullmatch(r"[0-9a-f]{32}:[0-9a-f]{32}", h):
        out.append({"type": "ntlm+salt / domain cached", "length": len(h), "confidence": "low"})
    if h.startswith(("$2y$", "$2b$", "$2a$")):
        out.append({"type": "bcrypt", "length": len(h), "confidence": "high"})
    if h.startswith("$6$"):
        out.append({"type": "sha512crypt", "length": len(h), "confidence": "high"})
    if h.startswith("$5$"):
        out.append({"type": "sha256crypt", "length": len(h), "confidence": "high"})
    return out


def all_hashes(text: str) -> dict:
    """Compute every supported digest of a text (encode helper)."""
    data = text.encode("utf-8")
    return {"input": text, "hashes": {name: fn(data).hexdigest()
                                      for name, fn in ALGOS.items()}}


def _candidate_words(word: str) -> list[str]:
    return [word, word.lower(), word.upper(), word.capitalize()]


def crack(target: str, algo: str, wordlist_path: str | None,
          max_words: int = 2_000_000) -> dict:
    """Plain dictionary attack (with common case variants)."""
    algo = algo.lower()
    if algo not in ALGOS:
        return {"ok": False, "error": f"algo tidak didukung: {algo} "
                f"(didukung: {', '.join(ALGOS)})"}
    hfun = ALGOS[algo]
    target = target.strip().lower()
    words: list[str]
    if wordlist_path and Path(wordlist_path).exists():
        words = []
        with open(wordlist_path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_words:
                    break
                w = line.rstrip("\r\n")
                if w:
                    words.append(w)
    else:
        words = ["", "password", "123456", "admin", "letmein", "root", "test",
                 "secret", "ctf", "flag", "changeme", "qwerty", "1234567890"]
    for w in words:
        for cand in _candidate_words(w):
            if hfun(cand.encode()).hexdigest() == target:
                return {"ok": True, "cracked": cand, "algo": algo,
                        "words_tried": min(len(words), max_words)}
    return {"ok": False, "error": "tidak ditemukan di wordlist",
            "words_tried": len(words), "algo": algo}


def crack_all_variants(target: str, wordlist_path: str | None) -> dict:
    """Try the most common algos (md5, sha1, sha256) automatically."""
    tried = {}
    for algo in ("md5", "sha1", "sha256"):
        if len(target.strip()) == {"md5": 32, "sha1": 40, "sha256": 64}[algo]:
            r = crack(target, algo, wordlist_path)
            if r.get("ok"):
                return r
            tried[algo] = r.get("words_tried")
    return {"ok": False, "error": "tidak ditemukan di wordlist (md5/sha1/sha256)",
            "tried": tried}
