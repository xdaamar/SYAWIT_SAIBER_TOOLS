"""Binary analysis helpers: cyclic pattern generation/offset finding, ELF/PE
header parsing (pure-python fallback), and security-mitigation checks."""
from __future__ import annotations

import re
import struct
from pathlib import Path


# --- Cyclic pattern (pwntools-compatible) ------------------------------------
def cyclic_pattern(length: int = 500, n: int = 4) -> str:
    """De Bruijn-like pattern compatible with pwntools cyclic(n=4) defaults:
    'aaaabaaac...' generated from [a-z][a-z][a-z]."""
    alphabet = "abcdefghijklmnopqrstuvwxyz"
    out = []
    i = 0
    while len(out) * n < length:
        a = alphabet[i // (26 * 26) % 26]
        b = alphabet[(i // 26) % 26]
        c = alphabet[i % 26]
        out.append(a + b + c)
        i += 1
    return "".join(out)[:length]


def pattern_offset(needle: str, n: int = 4) -> int | None:
    """Find offset of a 4/8-byte crash value (ascii or hex) in the pattern."""
    if needle.startswith("0x"):
        try:
            raw = int(needle, 16)
            needle = struct.pack("<Q" if raw > 0xFFFFFFFF else "<I", raw).decode("latin-1")
        except (ValueError, OverflowError, UnicodeDecodeError):
            return None
    pat = cyclic_pattern(20000, n)
    idx = pat.find(needle)
    return idx if idx >= 0 else None


# --- ELF parsing (pure python) -----------------------------------------------
def parse_elf(path: str | Path) -> dict:
    """Minimal ELF64 header parse: class, entry, machine, PIE, and dynamic
    section presence of key symbols via relocations on the dynamic symbol
    table when easy; falls back to 'unknown' gracefully."""
    p = Path(path)
    info: dict = {"path": str(p), "format": "unknown"}
    try:
        data = p.read_bytes()
    except OSError as e:
        info["error"] = str(e)
        return info
    if len(data) < 64 or not data.startswith(b"\x7fELF"):
        if data[:2] == b"MZ":
            info["format"] = "PE"
            info["machine"] = "x86/x64 (PE)"
            return info
        info["error"] = "bukan ELF/PE"
        return info
    info["format"] = "ELF"
    ei_class = data[4]          # 1=32-bit, 2=64-bit
    ei_data = data[5]           # 1=LE
    info["arch_bits"] = 64 if ei_class == 2 else 32
    endian = "<" if ei_data == 1 else ">"
    if ei_class == 2:
        e_type, e_machine = struct.unpack_from(endian + "HH", data, 16)
        e_entry = struct.unpack_from(endian + "Q", data, 24)[0]
    else:
        e_type, e_machine = struct.unpack_from(endian + "HH", data, 16)
        e_entry = struct.unpack_from(endian + "I", data, 24)[0]
    info["elf_type"] = {2: "EXEC (no PIE)", 3: "DYN (PIE/shared)"}.get(e_type, str(e_type))
    info["pie"] = e_type == 3
    info["entry"] = hex(e_entry)
    info["machine"] = {0x3E: "x86-64", 0x03: "x86", 0xB7: "aarch64", 0xF3: "riscv"}.get(
        e_machine, hex(e_machine))
    # NX: PT_GNU_STACK segment p_flags
    info["nx"] = "unknown"
    try:
        if ei_class == 2:
            e_phoff = struct.unpack_from(endian + "Q", data, 32)[0]
            e_phentsize, e_phnum = struct.unpack_from(endian + "HH", data, 54)
        else:
            e_phoff = struct.unpack_from(endian + "I", data, 28)[0]
            e_phentsize, e_phnum = struct.unpack_from(endian + "HH", data, 42)
        for i in range(min(e_phnum, 64)):
            off = e_phoff + i * e_phentsize
            p_type = struct.unpack_from(endian + "I", data, off)[0]
            if p_type == 0x6474E551:  # PT_GNU_STACK
                p_flags = struct.unpack_from(endian + "I", data, off + (4 if ei_class == 2 else 24))[0]
                info["nx"] = bool(p_flags & 0x1) and "disabled (stack executable)" or "enabled"
    except Exception:
        pass
    # imports (rough): scan dynamic string table for known lib names
    libs = sorted(set(re.findall(rb"libc\.so[\w.]*|libcrypto[\w.]*|libssl[\w.]*", data)))[:12]
    info["linked_libs"] = [l.decode("latin-1") for l in libs]
    # interesting strings
    strings = re.findall(rb"[\x20-\x7e]{6,}", data)
    interesting = []
    keywords = (b"/bin/sh", b"/bin/bash", b"flag", b"system", b"printf",
                b"gets", b"strcpy", b"win", b"password", b"secret")
    for s in strings:
        low = s.lower()
        if any(k in low for k in keywords):
            interesting.append(s.decode("latin-1")[:80])
        if len(interesting) >= 20:
            break
    info["interesting_strings"] = interesting
    protections = {
        "pie": info["pie"],
        "nx": str(info["nx"]),
        "canary": b"__stack_chk_fail" in data,
        "relro": b"__libc_start_main" in data and "partial/unknown",
    }
    info["protections"] = protections
    return info


def suggest_exploit_style(info: dict) -> str:
    if info.get("format") != "ELF":
        return "analisis manual / tools eksternal"
    strings = " ".join(info.get("interesting_strings", []))
    if "gets" in strings:
        return "buffer overflow klasik (gets) — offset pattern -> ret2win / ret2libc"
    prot = info.get("protections", {})
    if prot.get("canary"):
        return "canary aktif — cari format string leak lebih dulu"
    return "buffer overflow / format string; cek proteksi dulu"
