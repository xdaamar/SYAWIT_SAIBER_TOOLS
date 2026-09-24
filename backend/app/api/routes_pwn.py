"""Pwn API routes."""
from __future__ import annotations

import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import config
from ..modules.pwn.binary_analyzer import (cyclic_pattern, parse_elf,
                                           pattern_offset,
                                           suggest_exploit_style)
from ..modules.pwn.exploit_builder import build_exploit, list_templates

router = APIRouter(prefix="/api/pwn", tags=["pwn"])


class AnalyzeBody(BaseModel):
    path: str


@router.post("/analyze")
def analyze(body: AnalyzeBody):
    p = Path(body.path)
    if not p.exists():
        raise HTTPException(404, f"file tidak ada: {p}")
    info = parse_elf(str(p))
    info["suggestion"] = suggest_exploit_style(info)
    return info


@router.get("/pattern")
def get_pattern(length: int = 200):
    length = max(16, min(length, 20000))
    return {"pattern": cyclic_pattern(length), "length": length}


class OffsetBody(BaseModel):
    value: str


@router.post("/offset")
def find_offset(body: OffsetBody):
    off = pattern_offset(body.value.strip())
    return {"value": body.value, "offset": off,
            "hint": None if off is not None else
            "tidak ditemukan di pattern — pastikan 4/8 byte & nilai ascii crash (atau hex 0x...)"}


class ExploitBody(BaseModel):
    kind: str
    exe_path: str
    offset: int = 0
    ret_addr: str = "0x0"
    libc_path: str = "/lib/x86_64-linux-gnu/libc.so.6"
    pop_rdi: str = "0x0"
    arch: str = "amd64"
    save: bool = True


@router.post("/exploit")
def exploit(body: ExploitBody):
    built = build_exploit(body.kind, body.exe_path, offset=body.offset,
                          ret_addr=body.ret_addr, libc_path=body.libc_path,
                          pop_rdi=body.pop_rdi, arch=body.arch)
    if "error" in built:
        raise HTTPException(400, built["error"])
    if body.save:
        out_dir = config.DATA_DIR / "exploits"
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{int(time.time())}_{built['filename']}"
        out.write_text(built["script"], encoding="utf-8")
        built["saved_to"] = str(out)
    return built


@router.get("/templates")
def templates():
    return {"templates": list_templates()}
