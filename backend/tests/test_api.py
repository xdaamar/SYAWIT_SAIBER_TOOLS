"""API smoke tests via TestClient (no external tools required)."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_settings_roundtrip():
    r = client.put("/api/settings", json={"values": {"http_timeout": 15, "bogus": 1}})
    assert r.status_code == 200
    assert r.json()["updated"] == 1  # 'bogus' filtered out
    r = client.get("/api/settings")
    assert r.status_code == 200
    assert r.json()["settings"]["http_timeout"] == 15


def test_crypto_hash_endpoint():
    r = client.post("/api/crypto/hash", json={"text": "abc"})
    assert r.status_code == 200
    assert len(r.json()["hashes"]["md5"]) == 32


def test_crypto_solve_endpoint():
    import base64
    payload = base64.b64encode(b"ctf flag here").decode()
    r = client.post("/api/crypto/solve", json={"text": payload})
    assert r.status_code == 200
    body = r.json()
    assert "ctf flag here" in body["best"]["preview"]


def test_pwn_pattern_endpoint():
    r = client.get("/api/pwn/pattern?length=100")
    assert r.status_code == 200
    pat = r.json()["pattern"]
    r2 = client.post("/api/pwn/offset", json={"value": pat[48:52]})
    assert r2.json()["offset"] == 48


def test_jobs_list():
    r = client.get("/api/jobs")
    assert r.status_code == 200
    assert "jobs" in r.json()


def test_nmap_presets():
    r = client.get("/api/recon/nmap/presets")
    assert r.status_code == 200
    assert any(p["id"] == "quick" for p in r.json()["presets"])


def test_setup_status_endpoint():
    r = client.get("/api/setup/status")
    assert r.status_code == 200
    body = r.json()
    assert "ready" in body and "components" in body


def test_report_generate_rejects_empty():
    r = client.post("/api/report/generate", json={"job_ids": [], "findings": []})
    assert r.status_code == 400


def test_report_generate_from_findings():
    f = [{"module": "web", "title": "XSS test", "severity": "high",
          "url": "http://x/", "evidence": "marker", "recommendation": "escape"}]
    r = client.post("/api/report/generate", json={"findings": f, "fmt": "md"})
    assert r.status_code == 200
    assert r.json()["findings"] == 1
