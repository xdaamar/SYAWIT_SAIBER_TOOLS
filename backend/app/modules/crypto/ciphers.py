"""Classical ciphers: Caesar brute with scoring, Vigenère decrypt and
key-length detection via index of coincidence."""
from __future__ import annotations

from collections import Counter

from .solver import rot_n, score_text

ENGLISH_FREQ = {
    "a": 8.2, "b": 1.5, "c": 2.8, "d": 4.3, "e": 12.7, "f": 2.2, "g": 2.0,
    "h": 6.1, "i": 7.0, "j": 0.15, "k": 0.77, "l": 4.0, "m": 2.4, "n": 6.7,
    "o": 7.5, "p": 1.9, "q": 0.095, "r": 6.0, "s": 6.3, "t": 9.1, "u": 2.8,
    "v": 0.98, "w": 2.4, "x": 0.15, "y": 2.0, "z": 0.074,
}


def caesar_brute(text: str) -> list[dict]:
    out = []
    for n in range(1, 26):
        dec = rot_n(text, n)
        out.append({"shift": n, "score": round(score_text(dec), 3), "text": dec[:500]})
    out.sort(key=lambda x: -x["score"])
    return out


def _letters_only(text: str) -> str:
    return "".join(c.lower() for c in text if c.isalpha())


def index_of_coincidence(text: str) -> float:
    letters = _letters_only(text)
    if len(letters) < 2:
        return 0.0
    counts = Counter(letters)
    n = len(letters)
    ic = sum(c * (c - 1) for c in counts.values()) / (n * (n - 1))
    return round(ic, 5)


def detect_key_length(ciphertext: str, max_len: int = 16) -> list[dict]:
    letters = _letters_only(ciphertext)
    results = []
    for klen in range(2, max_len + 1):
        if len(letters) < klen * 5:
            break
        ics = []
        for i in range(klen):
            chunk = letters[i::klen]
            ics.append(index_of_coincidence(chunk))
        avg = sum(ics) / len(ics)
        results.append({"key_length": klen, "avg_ic": round(avg, 4),
                        "english_like": avg > 0.06})
    results.sort(key=lambda x: -x["avg_ic"])
    return results


def vigenere_decrypt(ciphertext: str, key: str) -> str:
    key = [ord(c.lower()) - 97 for c in key if c.isalpha()]
    if not key:
        return ciphertext
    out = []
    ki = 0
    for c in ciphertext:
        if c.isalpha():
            base = 97 if c.islower() else 65
            shift = key[ki % len(key)]
            out.append(chr((ord(c.lower()) - 97 - shift) % 26 + base))
            ki += 1
        else:
            out.append(c)
    return "".join(out)


def vigenere_solve(ciphertext: str, max_len: int = 16) -> dict:
    """Guess key length by IC, then crack each column by chi-square."""
    letters = _letters_only(ciphertext)
    candidates = detect_key_length(ciphertext, max_len)
    if not candidates:
        return {"key": None, "plaintext": None, "note": "teks terlalu pendek"}
    best = {"key": None, "plaintext": None, "score": -1, "key_length": None}
    for cand in candidates[:5]:
        klen = cand["key_length"]
        key = ""
        for i in range(klen):
            chunk = letters[i::klen]
            best_shift, best_chi = 0, 1e18
            for s in range(26):
                dec = rot_n(chunk, s)
                counts = Counter(dec)
                n = len(chunk) or 1
                chi = sum(
                    (counts.get(c, 0) / n - ENGLISH_FREQ[c] / 100) ** 2
                    / (ENGLISH_FREQ[c] / 100)
                    for c in ENGLISH_FREQ
                )
                if chi < best_chi:
                    best_chi, best_shift = chi, s
            key += chr((26 - best_shift) % 26 + 97)
        dec = vigenere_decrypt(ciphertext, key)
        sc = score_text(dec)
        if sc > best["score"]:
            best = {"key": key, "plaintext": dec[:2000], "score": round(sc, 3),
                    "key_length": klen}
    return best
