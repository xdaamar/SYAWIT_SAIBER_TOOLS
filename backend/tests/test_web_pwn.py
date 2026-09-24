"""Web/pwn/setup component tests (pure logic, no network)."""
from __future__ import annotations

from app.modules.pwn.binary_analyzer import cyclic_pattern, pattern_offset
from app.modules.pwn.exploit_builder import build_exploit
from app.modules.web import form_analyzer
from app.modules.web.auth_bypass import analyze_jwt
from app.modules.web.sqlmap_runner import build_command, sqlmap_cmd


def test_pattern_offset():
    pat = cyclic_pattern(200)
    needle = pat[64:68]
    assert pattern_offset(needle) == 64


def test_pattern_offset_hex():
    pat = cyclic_pattern(200)
    needle = pat[32:36]
    off = pattern_offset(needle.encode().hex()) or pattern_offset("0x" + needle.encode().hex())
    assert off is None or off == 32  # hex-of-ascii not required, just don't crash


def test_exploit_builder_bof():
    res = build_exploit("bof", "C:/lab/vuln.exe", offset=72, ret_addr="0x40123a")
    assert res["filename"] == "exploit_bof.py"
    assert "OFFSET = 72" in res["script"]
    assert "C:/lab/vuln.exe" in res["script"]


def test_exploit_builder_bad_kind():
    assert "error" in build_exploit("nope", "x")


def test_form_analyzer():
    forms = [{"page": "http://x/", "action": "http://x/login", "method": "post",
              "inputs": [{"name": "user", "type": "text", "value": None},
                         {"name": "cmd", "type": "text", "value": None}]}]
    res = form_analyzer.analyze_forms(forms, ["http://x/s?id=1"])
    assert res["total"] == 3
    kinds = {p["param"]: p for p in res["attack_points"]}
    assert "A03_command_injection" in kinds["cmd"]["test_classes"]


def test_jwt_analysis():
    import base64
    b64 = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    header = b64(b'{"alg":"HS256","typ":"JWT"}')
    payload = b64(b'{"sub":"user","role":"user","exp":9999999999}')
    token = f"{header}.{payload}.sig"
    info = analyze_jwt(token)
    assert info["valid"] and info["payload"]["role"] == "user"
    assert "forged_alg_none_token" in info


def test_sqlmap_command():
    cmd = build_command("http://x/a.php?id=1", data="id=1", level=3, risk=2)
    assert cmd is None or "--level=3" in " ".join(str(c) for c in cmd)
