"""Nmap runner: build commands, run as job, parse XML output."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from ... import config

PRESETS = {
    "quick": {"flags": ["-T4", "-F"], "label": "Quick (top 1000 ports)"},
    "full_tcp": {"flags": ["-T4", "-p", "-"], "label": "Full TCP (semua port)"},
    "udp_top": {"flags": ["-sU", "--top-ports", "200"], "label": "UDP top 200"},
    "service_version": {"flags": ["-sV", "-T4"], "label": "Service & version detection"},
    "os_detect": {"flags": ["-O", "-sV", "-T4"], "label": "OS + service detection"},
    "vuln_scripts": {"flags": ["-sV", "--script", "vuln"], "label": "Vuln scripts (default category)"},
    "http_enum": {"flags": ["-sV", "--script", "http-enum,http-title"], "label": "HTTP enumeration"},
}

INTERESTING = {"http", "https", "ftp", "ssh", "smb", "microsoft-ds", "mysql",
               "mssql", "postgresql", "redis", "mongodb", "rdp", "telnet",
               "smtp", "pop3", "imap", "vnc"}


def nmap_exe() -> str | None:
    exe = shutil.which("nmap")
    if exe:
        return exe
    for cand in (r"C:\Program Files (x86)\Nmap\nmap.exe",
                 r"C:\Program Files\Nmap\nmap.exe"):
        if Path(cand).exists():
            return cand
    return None


def xml_out_path() -> Path:
    return config.DATA_DIR / "last_nmap.xml"


def build_command(target: str, preset: str, extra_args: str = "") -> list | None:
    """Compose the nmap command; returns None if nmap is missing."""
    exe = nmap_exe()
    if not exe:
        return None
    p = PRESETS.get(preset, PRESETS["quick"])
    cmd = [exe, *p["flags"], "-oX", str(xml_out_path()), target]
    if extra_args:
        cmd.extend(extra_args.split())
    return cmd


def parse_xml(path: Path) -> dict:
    """Parse nmap XML into a structured summary."""
    tree = ET.parse(path)
    root = tree.getroot()
    hosts = []
    for host in root.findall("host"):
        addr = host.find("address")
        ip = addr.get("addr") if addr is not None else "?"
        hostname = None
        hn = host.find("hostnames/hostname")
        if hn is not None:
            hostname = hn.get("name")
        ports = []
        for port in host.findall("ports/port"):
            state_el = port.find("state")
            if state_el is None or state_el.get("state") != "open":
                continue
            svc = port.find("service")
            service = svc.get("name") if svc is not None else "?"
            product = " ".join(filter(None, [
                svc.get("product") if svc is not None else None,
                svc.get("version") if svc is not None else None,
            ]))
            scripts = {}
            for sc in port.findall("script"):
                scripts[sc.get("id")] = (sc.get("output") or "")[:2000]
            ports.append({
                "port": int(port.get("portid", 0)),
                "protocol": port.get("protocol", "tcp"),
                "service": service,
                "product": product,
                "interesting": service.lower() in INTERESTING,
                "scripts": scripts,
            })
        os_match = None
        osel = host.find("os/osmatch")
        if osel is not None:
            os_match = f"{osel.get('name')} ({osel.get('accuracy')}%)"
        hosts.append({"ip": ip, "hostname": hostname, "os": os_match, "ports": ports})
    runstats = root.find("runstats/finished")
    return {
        "scanner": "nmap",
        "args": root.get("args"),
        "hosts": hosts,
        "elapsed": runstats.get("elapsed") if runstats is not None else None,
        "exit": runstats.get("exit") if runstats is not None else None,
    }


def attack_surface(parsed: dict) -> list[dict]:
    """Highlight potentially juicy services from parsed results."""
    out = []
    for h in parsed.get("hosts", []):
        for p in h.get("ports", []):
            if p["interesting"] or p.get("scripts"):
                out.append({
                    "host": h["ip"],
                    "port": p["port"],
                    "service": p["service"],
                    "product": p["product"],
                    "reason": "script output" if p.get("scripts") else "service umum menarik",
                })
    return out
