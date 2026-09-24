"""RSA CTF toolkit: analyze n/e/c, run common attacks (small-e, common
factor, Fermat factorization, Wiener) and decrypt when possible."""
from __future__ import annotations

import math

from sympy import isprime


def _i(x) -> int:
    return int(x)


def _gmpy_iroot(c: int, e: int) -> tuple[int, bool]:
    """Integer e-th root via binary search (no gmpy dependency)."""
    if c < 0:
        return 0, False
    lo, hi = 0, 1 << ((c.bit_length() // e) + 2)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if mid ** e <= c:
            lo = mid
        else:
            hi = mid - 1
    return lo, lo ** e == c


def small_e_attack_precise(e: int, n: int, c: int) -> int | None:
    """c = m^e without padding, small e -> exact integer e-th root."""
    if e > 16:
        return None
    m, exact = _gmpy_iroot(c, e)
    if exact and m > 0:
        return m
    return None


def common_factor_attack(n1: int, n2: int) -> int | None:
    """Shared prime between two moduli (gcd)."""
    g = math.gcd(n1, n2)
    return g if 1 < g < min(n1, n2) else None


def fermat_factorization(n: int, max_steps: int = 100000) -> tuple[int, int] | None:
    """Factor n = p*q when p and q are close."""
    if n % 2 == 0:
        return (2, n // 2)
    a = _isqrt(n)
    if a * a < n:
        a += 1
    for _ in range(max_steps):
        b2 = a * a - n
        b = _isqrt(b2)
        if b * b == b2:
            return (a - b, a + b)
        a += 1
    return None


def _isqrt(n: int) -> int:
    if n < 0:
        raise ValueError
    x = n
    y = (x + 1) // 2
    while y < x:
        x = y
        y = (x + n // x) // 2
    return x


def wiener_attack(e: int, n: int) -> int | None:
    """Wiener's attack for small private exponents via continued fractions."""
    def cf(x, y):
        while y:
            a = x // y
            yield a
            x, y = y, x - a * y

    convs = []
    num_p, num = 0, 1
    den_p, den = 1, 0
    for a in cf(e, n):
        num_p, num = num, a * num + num_p
        den_p, den = den, a * den + den_p
        convs.append((num, den))
        k, d = num, den
        if k == 0 or (e * d - 1) % k != 0:
            continue
        phi = (e * d - 1) // k
        s = n - phi + 1
        disc = s * s - 4 * n
        if disc < 0:
            continue
        t = _isqrt(disc)
        if t * t == disc and (s + t) % 2 == 0:
            p = (s + t) // 2
            q = (s - t) // 2
            if p * q == n:
                return d
    return None


def decrypt_rsa(c: int, d: int, n: int) -> int:
    return pow(c, d, n)


def int_to_bytes(v: int) -> bytes:
    out = v.to_bytes((v.bit_length() + 7) // 8 or 1, "big")
    return out


def bytes_to_int(b: bytes) -> int:
    return int.from_bytes(b, "big")


def analyze(n: int, e: int, c: int | None = None,
            n2: int | None = None) -> dict:
    """Run all applicable attacks, report findings; decrypt c when possible."""
    result: dict = {
        "n_bits": n.bit_length(), "e": e,
        "n_is_prime": bool(isprime(n)),
        "attacks": [],
    }
    attempts: list[dict] = []

    if e <= 16 and c is not None:
        m = small_e_attack_precise(e, n, c)
        if m:
            attempts.append({"attack": "small_e (integer e-th root)",
                             "success": True, "plaintext_bytes": int_to_bytes(m)})

    if n2:
        g = common_factor_attack(n, n2)
        if g:
            attempts.append({"attack": "common_factor (gcd)", "success": True,
                             "factor": str(g),
                             "note": "p ditemukan; gunakan untuk derive d"})
            p, q = g, n // g
            phi = (p - 1) * (q - 1)
            d = pow(e, -1, phi)
            if c is not None:
                attempts.append({"attack": "common_factor -> decrypt",
                                 "success": True,
                                 "plaintext_bytes": int_to_bytes(pow(c, d, n))})

    if e.bit_length() * 0.25 > n.bit_length() ** -0.25 * 100 or n.bit_length() > 512:
        d = wiener_attack(e, n)
        if d:
            attempts.append({"attack": "wiener", "success": True, "d": str(d)})
            if c is not None:
                attempts.append({"attack": "wiener -> decrypt", "success": True,
                                 "plaintext_bytes": int_to_bytes(pow(c, d, n))})

    if n.bit_length() <= 512:
        fac = fermat_factorization(n, max_steps=50000)
        if fac:
            p, q = fac
            attempts.append({"attack": "fermat_factorization", "success": True,
                             "p": str(p), "q": str(q)})
            phi = (p - 1) * (q - 1)
            d = pow(e, -1, phi)
            if c is not None:
                attempts.append({"attack": "fermat -> decrypt", "success": True,
                                 "plaintext_bytes": int_to_bytes(pow(c, d, n))})

    result["attempts"] = attempts
    result["solved"] = any(a["success"] and "plaintext_bytes" in a for a in attempts)
    if not attempts:
        result["note"] = ("Tidak ada attack yang berhasil otomatis. "
                          "Coba RsaCtfTool untuk attack lain (boneh_durfee, hastad, dll).")
    return result
