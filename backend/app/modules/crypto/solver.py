"""Crypto multi-decoder: paste anything, get ranked candidate decodings.

Handles base64/32, hex, URL, ROT-n, XOR single-byte brute, binary/octal/decimal,
morse, brainfuck, JWT (decode only) — with up to 3 layers of stacking and
English/readability scoring for ranking."""
from __future__ import annotations

import base64
import binascii
import re
import string
import urllib.parse
from collections import Counter

COMMON_WORDS = {
    "the", "and", "flag", "ctf", "key", "this", "that", "secret", "password",
    "hello", "world", "admin", "login", "test", "file", "http", "https", "com",
    "code", "with", "from", "your", "have", "not", "for", "you", "are", "was",
}

PRINTABLE = set(string.printable)


def score_text(s: str) -> float:
    """Higher = more likely to be meaningful plaintext."""
    if not s:
        return 0.0
    printable = sum(1 for c in s if c in PRINTABLE) / len(s)
    letters = sum(1 for c in s.lower() if c in string.ascii_lowercase) / len(s)
    words = sum(1 for w in COMMON_WORDS if w in s.lower())
    spaces = s.count(" ") / max(len(s), 1)
    return printable * 0.4 + letters * 0.3 + min(words * 0.15, 0.6) + min(spaces, 0.2)


def _try_b64(s: str) -> str | None:
    t = re.sub(r"\s+", "", s)
    pad = "=" * (-len(t) % 4)
    try:
        raw = base64.b64decode(t + pad, validate=False)
        txt = raw.decode("utf-8")
        return txt if txt.isprintable() or "\n" in txt else None
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _try_b32(s: str) -> str | None:
    try:
        return base64.b32decode(re.sub(r"\s+", "", s) + "=" * 8).decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError):
        return None


def _try_hex(s: str) -> str | None:
    t = re.sub(r"[\s:]+", "", s)
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2})+", t) or len(t) < 4:
        return None
    try:
        raw = bytes.fromhex(t)
        txt = raw.decode("utf-8")
        return txt if txt.isprintable() else None
    except (UnicodeDecodeError, ValueError):
        return None


def _try_url(s: str) -> str | None:
    if "%" not in s and "+" not in s:
        return None
    try:
        out = urllib.parse.unquote_plus(s)
        return out if out != s else None
    except Exception:
        return None


def _try_binary(s: str) -> str | None:
    t = re.sub(r"\s+", " ", s).strip()
    if not re.fullmatch(r"(?:[01]{8}\s*)+", t):
        return None
    try:
        return "".join(chr(int(b, 2)) for b in t.split())
    except ValueError:
        return None


def _try_octal(s: str) -> str | None:
    t = re.sub(r"\\|o", " ", s).strip()
    if not re.fullmatch(r"(?:[0-7]{2,3}\s*)+", t) or " " not in t:
        return None
    try:
        return "".join(chr(int(o, 8)) for o in t.split())
    except ValueError:
        return None


def _try_decimal(s: str) -> str | None:
    t = re.sub(r"\s+", " ", s).strip()
    if not re.fullmatch(r"(?:\d{2,3}\s*)+", t) or " " not in t:
        return None
    vals = [int(x) for x in t.split()]
    if not all(32 <= v < 127 for v in vals):
        return None
    return "".join(chr(v) for v in vals)


MORSE = {
    ".-": "a", "-...": "b", "-.-.": "c", "-..": "d", ".": "e", "..-.": "f",
    "--.": "g", "....": "h", "..": "i", ".---": "j", "-.-": "k", ".-..": "l",
    "--": "m", "-.": "n", "---": "o", ".--.": "p", "--.-": "q", ".-.": "r",
    "...": "s", "-": "t", "..-": "u", "...-": "v", ".--": "w", "-..-": "x",
    "-.--": "y", "--..": "z", "-----": "0", ".----": "1", "..---": "2",
    "...--": "3", "....-": "4", ".....": "5", "-....": "6", "--...": "7",
    "---..": "8", "----.": "9", "/": " ", ".-.-.-": ".", "--..--": ",",
}


def _try_morse(s: str) -> str | None:
    t = s.strip().replace("_", "-")
    if not re.fullmatch(r"[.\- /]+", t) or "." not in t:
        return None
    out = []
    for word in t.split("/"):
        letters = [MORSE.get(l, "?") for l in word.split()]
        if letters and "?" * len(letters) == "".join(letters) and "?" in letters:
            return None
        out.append("".join(letters))
    return " ".join(out)


def _try_brainfuck(s: str) -> str | None:
    if not re.fullmatch(r"[><+\-.,\[\]\s]*", s.strip()) or "[" not in s:
        return None
    prog = [c for c in s if c in "><+-.,[]"]
    tape = [0] * 30000
    ptr = ip = 0
    out = []
    jumps = {}
    stack = []
    for i, c in enumerate(prog):
        if c == "[":
            stack.append(i)
        elif c == "]":
            if not stack:
                return None
            j = stack.pop()
            jumps[i], jumps[j] = j, i
    if stack:
        return None
    steps = 0
    while ip < len(prog) and steps < 2_000_000:
        c = prog[ip]
        if c == ">":
            ptr = (ptr + 1) % len(tape)
        elif c == "<":
            ptr = (ptr - 1) % len(tape)
        elif c == "+":
            tape[ptr] = (tape[ptr] + 1) % 256
        elif c == "-":
            tape[ptr] = (tape[ptr] - 1) % 256
        elif c == ".":
            out.append(chr(tape[ptr]))
        elif c == "[" and tape[ptr] == 0:
            ip = jumps[ip]
        elif c == "]" and tape[ptr] != 0:
            ip = jumps[ip]
        ip += 1
        steps += 1
    return "".join(out) if out else None


def _try_jwt(s: str) -> str | None:
    parts = s.strip().split(".")
    if len(parts) != 3:
        return None
    try:
        import json
        pad = lambda p: p + "=" * (-len(p) % 4)  # noqa: E731

        def b64json(p):
            raw = base64.urlsafe_b64decode(pad(p))
            return json.loads(raw.decode("utf-8"))

        header, payload = b64json(parts[0]), b64json(parts[1])
        import json as j
        return j.dumps({"header": header, "payload": payload,
                        "signature_hex": binascii.hexlify(
                            base64.urlsafe_b64decode(pad(parts[2]))).decode()},
                       indent=2)
    except Exception:
        return None


def rot_n(s: str, n: int) -> str:
    out = []
    for c in s:
        if "a" <= c <= "z":
            out.append(chr((ord(c) - 97 + n) % 26 + 97))
        elif "A" <= c <= "Z":
            out.append(chr((ord(c) - 65 + n) % 26 + 65))
        else:
            out.append(c)
    return "".join(out)


def xor_single(s: str, key: int) -> str | None:
    try:
        raw = bytes.fromhex(re.sub(r"[\s:]+", "", s))
    except ValueError:
        raw = s.encode("latin-1", errors="replace")
    out = bytes(b ^ key for b in raw)
    try:
        txt = out.decode("utf-8")
        return txt if txt.isprintable() else None
    except UnicodeDecodeError:
        return None


SINGLE = [
    ("base64", _try_b64), ("base32", _try_b32), ("hex", _try_hex),
    ("url", _try_url), ("binary", _try_binary), ("octal", _try_octal),
    ("decimal", _try_decimal), ("morse", _try_morse), ("brainfuck", _try_brainfuck),
    ("jwt", _try_jwt),
]


def decode(data: str, max_depth: int = 3) -> dict:
    """Decode data with all known transforms, stacking up to max_depth layers."""
    candidates: list[dict] = []
    seen: set[str] = set()

    def walk(text: str, path: list, depth: int) -> None:
        if depth > max_depth:
            return
        results = []
        for name, fn in SINGLE:
            out = fn(text)
            if out and out != text:
                results.append((name, out))
        # ROT all shifts (skip 0); report only readable ones
        for n in range(1, 26):
            out = rot_n(text, n)
            if score_text(out) > 0.55:
                results.append((f"rot{n}", out))
        # XOR single byte on hex-ish or binary input
        if re.fullmatch(r"(?:[0-9a-fA-F]{2})+", re.sub(r"[\s:]+", "", text)):
            for k in range(1, 256):
                out = xor_single(text, k)
                if out and score_text(out) > 0.6:
                    results.append((f"xor:0x{k:02x}", out))
        for name, out in results:
            sc = score_text(out)
            sig = (name, out[:200])
            if sig in seen:
                continue
            seen.add(sig)
            candidates.append({
                "method": ".".join(path + [name]),
                "score": round(sc, 3),
                "preview": out[:400],
                "full": out if depth == max_depth else None,
                "depth": depth,
            })
            if sc < 0.95:
                walk(out, path + [name], depth + 1)

    walk(data.strip(), [], 1)
    candidates.sort(key=lambda c: (c["depth"], -c["score"]))
    for c in candidates[:15]:
        c.pop("full", None)
    return {"input_length": len(data), "candidates": candidates[:50],
            "best": candidates[0] if candidates else None}
