"""Form analyzer: turn discovered forms/URLs into an attack map that lists
every injectable parameter grouped by OWASP Top 10 test classes."""
from __future__ import annotations

from dataclasses import dataclass, field

ATTACK_CLASSES = {
    "A03_sql_injection": "SQL injection (error-based, boolean-based)",
    "A03_xss": "Reflected XSS",
    "A03_command_injection": "Command/OS injection",
    "A03_ssti": "Server-side template injection",
    "A03_path_traversal": "Path traversal / LFI",
    "A10_ssrf": "SSRF (URL parameters)",
}


@dataclass
class AttackPoint:
    url: str
    method: str
    param: str
    param_type: str
    classes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "url": self.url, "method": self.method, "param": self.param,
            "param_type": self.param_type, "test_classes": self.classes,
        }


def _classes_for(param_type: str, name: str) -> list[str]:
    n = (name or "").lower()
    t = (param_type or "").lower()
    classes = ["A03_sql_injection", "A03_xss"]
    if t in ("url", "file", "path") or any(k in n for k in ("url", "path", "file", "page", "dir", "include", "template")):
        classes += ["A03_path_traversal", "A10_ssrf" if "url" in n or t == "url" else "A03_ssti"]
        if "template" in n:
            classes.append("A03_ssti")
    if any(k in n for k in ("cmd", "exec", "host", "ping", "command", "ip")):
        classes.append("A03_command_injection")
    if t == "hidden":
        classes += ["A01_access_control"]
    return sorted(set(classes))


def analyze_forms(forms: list[dict], urls_with_params: list[str]) -> dict:
    points: list[AttackPoint] = []
    for f in forms:
        for inp in f.get("inputs", []):
            name = inp.get("name")
            if not name or inp.get("type") in ("submit", "button", "image"):
                continue
            points.append(AttackPoint(
                url=f.get("action", ""), method=f.get("method", "get"),
                param=name, param_type=inp.get("type", "text"),
                classes=_classes_for(inp.get("type", "text"), name),
            ))
    for u in urls_with_params:
        from urllib.parse import urlparse, parse_qsl
        q = urlparse(u).query
        for k, _v in parse_qsl(q, keep_blank_values=True):
            points.append(AttackPoint(url=u.split("?")[0], method="get", param=k,
                                      param_type="query",
                                      classes=_classes_for("query", k)))
    # coverage summary per OWASP class
    coverage: dict[str, int] = {}
    for p in points:
        for c in p.classes:
            coverage[c] = coverage.get(c, 0) + 1
    return {
        "attack_points": [p.to_dict() for p in points],
        "total": len(points),
        "coverage": dict(sorted(coverage.items())),
    }
