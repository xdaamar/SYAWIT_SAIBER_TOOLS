"""OWASP Top 10 lightweight probes — safe-by-default, non-destructive
markers only, each finding carries evidence and a severity guess."""
from __future__ import annotations

import re
import time
from urllib.parse import urljoin, urlparse

from .http_client import make_client

MARKER = "syawit7f3a"

SECURITY_HEADERS = [
    "strict-transport-security", "content-security-policy",
    "x-content-type-options", "x-frame-options",
]

SENSITIVE_PATHS = [
    "/.git/HEAD", "/.env", "/robots.txt", "/backup.zip", "/backup.tar.gz",
    "/db.sql", "/admin/", "/phpinfo.php", "/server-status", "/.DS_Store",
    "/debug/", "/actuator", "/.svn/entries", "/web.config.bak",
]

SQLI_ERRORS = [
    "you have an error in your sql syntax", "warning: mysql", "unclosed quotation",
    "quoted string not properly terminated", "sqlsyntaxerrorexception",
    "sql error", "sqlite3.operationalerror", "sqlite3.programmingerror",
    "ora-01756", "pg_query() [", "psql: fatal",
]

XSS_PAYLOAD = f"<h1>{MARKER}</h1>"
SSTI_PAYLOAD = "{{7*'7'}}"
CMD_PAYLOAD = f"; echo {MARKER}"
TRAV_PAYLOAD = "../../../../etc/passwd"


def _evidence(snippet: str, limit: int = 300) -> str:
    return re.sub(r"\s+", " ", snippet)[:limit]


async def run_owasp_scan(base_url: str, params_urls: list[str] | None = None,
                         forms: list[dict] | None = None,
                         cookies: dict | None = None,
                         headers: dict | None = None, log=print) -> dict:
    findings: list[dict] = []
    params_urls = params_urls or []
    forms = forms or []

    def add(check_id: str, owasp: str, title: str, severity: str,
            url: str, evidence: str, recommendation: str) -> None:
        findings.append({
            "id": check_id, "owasp": owasp, "title": title,
            "severity": severity, "url": url,
            "evidence": _evidence(evidence), "recommendation": recommendation,
        })
        log(f"[!] {severity} {check_id}: {title} @ {url}")

    async with make_client(base_url=base_url, cookies=cookies, headers=headers) as client:
        # --- A05: security headers on base page -----------------------------
        try:
            r = await client.get(base_url)
            missing = [h for h in SECURITY_HEADERS if h not in {k.lower() for k in r.headers}]
            if missing:
                add("A05-headers", "A05:2021 Security Misconfiguration",
                    f"Security headers hilang: {', '.join(missing)}", "low",
                    base_url, str(dict(r.headers))[:400],
                    "Tambahkan HSTS, CSP, X-Content-Type-Options, X-Frame-Options.")
            server = r.headers.get("server", "")
            if re.search(r"\d", server):
                add("A06-fingerprint", "A06:2021 Vulnerable Components",
                    f"Server header membocorkan versi: {server}", "info",
                    base_url, server, "Sembunyikan versi server.")
        except Exception as e:
            log(f"[!] base fetch gagal: {e}")
            return {"findings": findings, "scanned": 0}

        # --- A05: sensitive/backup paths ------------------------------------
        for path in SENSITIVE_PATHS:
            url = urljoin(base_url, path)
            try:
                r = await client.get(url)
            except Exception:
                continue
            body = r.text
            if r.status_code == 200 and len(body) > 10:
                if path == "/.git/HEAD" and "ref: refs/" in body:
                    add("A05-git", "A05:2021", "Folder .git terekspos", "high",
                        url, body[:120], "Blokir akses .git di web server.")
                elif path == "/.env" and re.search(r"=\s*\S+", body) and "<html" not in body.lower():
                    add("A05-env", "A05:2021", "File .env terekspos", "critical",
                        url, body[:200], "Jangan letakkan .env di webroot.")
                elif path == "/phpinfo.php" and "phpinfo()" in body:
                    add("A05-phpinfo", "A05:2021", "phpinfo terekspos", "medium",
                        url, "phpinfo() output", "Hapus phpinfo.php dari produksi.")
                elif path in ("/robots.txt",) and "disallow" in body.lower():
                    log(f"[i] robots.txt ditemukan — catat untuk wordlist manual")
                elif path not in ("/robots.txt",):
                    add("A05-path", "A05:2021", f"Path sensitif merespons 200: {path}",
                        "medium", url, body[:150], "Pastikan file memang harus publik.")

        # --- A03: parameter probes (GET) ------------------------------------
        for u in params_urls[:20]:
            base = u.split("?")[0]
            from urllib.parse import urlparse, parse_qsl, urlencode
            q = parse_qsl(urlparse(u).query, keep_blank_values=True)
            if not q:
                continue
            # reflected XSS probe on first param
            k = q[0][0]
            try:
                r = await client.get(base, params={k: XSS_PAYLOAD})
                if MARKER in r.text:
                    add("A03-xss", "A03:2021 Injection",
                        f"Reflected XSS kemungkinan di param '{k}'", "high",
                        u, f"marker {MARKER} muncul di response",
                        "Escape output / pakai templating auto-escape.")
            except Exception:
                continue
            # SQLi error probe
            try:
                r = await client.get(base, params={k: "'\"`)"})
                low = r.text.lower()
                for err in SQLI_ERRORS:
                    if err in low:
                        add("A03-sqli", "A03:2021 Injection",
                            f"Pesan error SQL muncul di param '{k}'", "high",
                            u, _evidence(low),
                            "Pakai prepared statements; lanjut verifikasi via SQLMap.")
                        break
            except Exception:
                pass
            # path traversal probe
            try:
                r = await client.get(base, params={k: TRAV_PAYLOAD})
                if re.search(r"root:[x*]!:0:0:|root:x:0:0:", r.text):
                    add("A03-lfi", "A03:2021 Injection",
                        f"Path traversal kemungkinan di param '{k}'", "critical",
                        u, "root:x:0:0 ditemukan di response",
                        "Validasi & whitelist path file.")
            except Exception:
                pass
            # SSTI probe
            try:
                r = await client.get(base, params={k: SSTI_PAYLOAD})
                if "7777777" in r.text:
                    add("A03-ssti", "A03:2021 Injection",
                        f"SSTI kemungkinan di param '{k}'", "critical",
                        u, "{{7*'7'}} -> 7777777", "Jangan render input user sebagai template.")
            except Exception:
                pass
            # command injection probe
            try:
                r = await client.get(base, params={k: CMD_PAYLOAD})
                if MARKER in r.text:
                    add("A03-cmdi", "A03:2021 Injection",
                        f"Command injection kemungkinan di param '{k}'", "critical",
                        u, f"marker {MARKER} dari echo", "Hindari shell=True; sanitasi input.")
            except Exception:
                pass
            time.sleep(0.05)

        # --- A02: transport/cookie hygiene ----------------------------------
        if base_url.startswith("http://"):
            add("A02-plain", "A02:2021 Cryptographic Failures",
                "Target berjalan di HTTP plaintext", "medium", base_url,
                "no TLS", "Gunakan HTTPS.")
        try:
            r = await client.get(base_url)
            for cookie in r.cookies.jar:
                if not cookie.has_nonstandard_attr("Secure") or \
                        not cookie.has_nonstandard_attr("HttpOnly"):
                    add("A02-cookie", "A02:2021 Cryptographic Failures",
                        f"Cookie '{cookie.name}' tanpa flag Secure/HttpOnly", "low",
                        base_url, str(cookie), "Set Secure; HttpOnly; SameSite.")
        except Exception:
            pass

    return {"findings": findings, "scanned": len(params_urls) + len(SENSITIVE_PATHS)}
