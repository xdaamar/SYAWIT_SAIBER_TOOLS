#!/usr/bin/env python3
"""demo_target.py — deliberately vulnerable LOCAL test target.

CTFSuite demo aplikasi web rentan untuk menguji modul-modul secara end-to-end
di localhost. HANYA bind di 127.0.0.1. Jangan pernah expose ke jaringan.

Jalankan:  python scripts/demo_target.py  (default http://127.0.0.1:5000)
"""
from __future__ import annotations

import html
import os
import sqlite3
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qsl, urlparse

PORT = int(os.environ.get("DEMO_PORT", "5000"))
DB_PATH = os.path.join(os.path.dirname(__file__), "demo_users.db")

MARKER = "ctfsuite7f3a"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("CREATE TABLE IF NOT EXISTS users "
                 "(id INTEGER PRIMARY KEY, username TEXT, password TEXT, role TEXT)")
    conn.execute("DELETE FROM users")
    conn.executemany("INSERT INTO users (username, password, role) VALUES (?,?,?)",
                     [("admin", "supersecret", "admin"),
                      ("user", "password", "user"),
                      ("guest", "guest123", "guest")])
    conn.commit()
    conn.close()


PAGE = """<!doctype html><html><head><title>CTFSuite Demo Shop</title></head>
<body><h1>Demo Shop (rentan — localhost only)</h1>
<ul>
<li><a href="/search?id=1">/search?id=1</a> — SQLi (error-based)</li>
<li><a href="/xss?q=hello">/xss?q=</a> — Reflected XSS</li>
<li><a href="/file?path=README.md">/file?path=</a> — Path traversal</li>
<li><a href="/cmd?host=127.0.0.1">/cmd?host=</a> — Command injection</li>
<li><a href="/tpl?name=world">/tpl?name=</a> — SSTI</li>
<li><a href="/login">/login</a> — Login (default creds / SQLi bypass)</li>
</ul>
<p>SSTI template: {name}</p>
</body></html>"""

LOGIN_PAGE = """<!doctype html><html><head><title>Login</title></head>
<body><h1>Login</h1><form method="POST" action="/login">
<input name="username" placeholder="username"><br>
<input name="password" type="password" placeholder="password"><br>
<input type="submit" value="Login"></form></body></html>"""


class DemoHandler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: str, ctype: str = "text/html") -> None:
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", f"{ctype}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        qs = dict(parse_qsl(u.query, keep_blank_values=True))
        path = u.path

        if path == "/":
            self._send(200, PAGE.format(name=qs.get("name", "world")))
        elif path == "/robots.txt":
            self._send(200, "User-agent: *\nDisallow: /admin\nDisallow: /backup.zip\n")
        elif path == "/.git/HEAD":
            self._send(200, "ref: refs/heads/main\n")
        elif path == "/backup.zip":
            self._send(200, "PK\x03\x04 fake backup (demo)")
        elif path == "/search":
            uid = qs.get("id", "")
            conn = sqlite3.connect(DB_PATH)
            try:
                # INTENTIONALLY vulnerable: string-formatted SQL
                rows = conn.execute(
                    f"SELECT username, role FROM users WHERE id = {uid}").fetchall()
                self._send(200, "<h2>Hasil</h2>" + "".join(
                    f"<p>{html.escape(str(r))}</p>" for r in rows))
            except Exception as e:
                # INTENTIONALLY leaks SQL error
                self._send(200, f"<p>SQL error: {e}</p>")
            finally:
                conn.close()
        elif path == "/xss":
            q = qs.get("q", "")
            # INTENTIONALLY unescaped reflection
            self._send(200, f"<p>Kamu mencari: {q}</p>")
        elif path == "/file":
            p = qs.get("path", "")
            base = os.path.dirname(os.path.abspath(__file__))
            # INTENTIONALLY vulnerable to traversal
            full = os.path.join(base, p)
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8", errors="replace") as f:
                    self._send(200, "<pre>" + html.escape(f.read()[:2000]) + "</pre>")
            else:
                self._send(404, "not found")
        elif path == "/cmd":
            host = qs.get("host", "")
            try:
                # INTENTIONALLY shell=True with user input
                out = subprocess.run(f"ping -n 1 {host}", shell=True,
                                     capture_output=True, timeout=5)
                text = (out.stdout + out.stderr).decode(errors="replace")
                self._send(200, "<pre>" + html.escape(text[:1500]) + "</pre>")
            except Exception as e:
                self._send(200, f"error: {e}")
        elif path == "/tpl":
            name = qs.get("name", "world")
            # Fake SSTI: vulnerable-ish template evaluation marker
            if "{{" in name and "}}" in name:
                expr = name.split("{{")[1].split("}}")[0].strip()
                try:
                    # tiny "7*'7" demo only — no arbitrary eval beyond demo digits
                    if expr == "7*'7'":
                        self._send(200, f"<p>template: {7777777}</p>")
                        return
                except Exception:
                    pass
            self._send(200, f"<p>template: {html.escape(name)}</p>")
        elif path == "/login":
            self._send(200, LOGIN_PAGE)
        elif path == "/api/health":
            self._send(200, '{"status":"demo-ok"}')
        else:
            self._send(404, "not found")

    def do_POST(self) -> None:  # noqa: N802
        u = urlparse(self.path)
        if u.path != "/login":
            self._send(404, "not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode()
        form = dict(parse_qsl(body, keep_blank_values=True))
        user = form.get("username", "")
        pwd = form.get("password", "")

        conn = sqlite3.connect(DB_PATH)
        try:
            # INTENTIONALLY vulnerable: classic OR 1=1 bypass
            rows = conn.execute(
                "SELECT username, role FROM users WHERE username = '" + user +
                "' AND password = '" + pwd + "'").fetchall()
        finally:
            conn.close()

        if rows:
            if any(r[1] == "admin" for r in rows):
                self.send_response(302)
                self.send_header("Location", "/admin")
                self.send_header("Set-Cookie", "session=demo-admin; Path=/")
                self.end_headers()
            else:
                self._send(200, f"<p>Welcome {html.escape(user)}!</p>")
        else:
            self._send(200, LOGIN_PAGE + "<p style='color:red'>Login gagal</p>")

    def log_message(self, fmt, *args) -> None:  # quiet
        sys.stdout.write("[demo] " + (fmt % args) + "\n")


def main() -> None:
    init_db()
    server = ThreadingHTTPServer(("127.0.0.1", PORT), DemoHandler)
    print(f"demo target: http://127.0.0.1:{PORT}  (Ctrl+C untuk stop)")
    print(f"marker probe: {MARKER}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
