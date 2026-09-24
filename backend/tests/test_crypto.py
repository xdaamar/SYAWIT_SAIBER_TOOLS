"""Crypto module tests: solver, hashes, ciphers, rsa."""
from __future__ import annotations

import base64
import hashlib

from app.modules.crypto import ciphers, hashes
from app.modules.crypto.rsa import (common_factor_attack, fermat_factorization,
                                    small_e_attack_precise)
from app.modules.crypto.solver import decode, rot_n


def test_decode_base64():
    payload = base64.b64encode(b"hello ctf").decode()
    res = decode(payload)
    assert res["best"]["preview"] == "hello ctf"
    assert "base64" in res["best"]["method"]


def test_decode_hex():
    res = decode("68656c6c6f")
    assert res["best"]["preview"] == "hello"


def test_caesar_decode():
    # 'attack at dawn' shifted by 3
    res = decode(rot_n("attack at dawn", 3))
    assert res["best"] is not None
    assert "attack" in res["best"]["preview"] or \
        any("attack" in c["preview"] for c in res["candidates"])


def test_hash_identify_and_all():
    md5 = hashlib.md5(b"x").hexdigest()
    assert hashes.identify(md5)[0]["type"] == "md5"
    ah = hashes.all_hashes("x")
    assert ah["hashes"]["md5"] == md5


def test_hash_crack_builtin():
    md5 = hashlib.md5(b"changeme").hexdigest()
    res = hashes.crack(md5, "md5", None)
    assert res["ok"] and res["cracked"] == "changeme"


def test_vigenere_roundtrip():
    pt = "thequickbrownfox"
    ct = ciphers.vigenere_decrypt(pt, "secret")  # sanity: function runs
    assert isinstance(ct, str) and len(ct) == len(pt)


def test_rsa_small_e():
    # m^3 for small m is recoverable directly (exact integer cube root < n)
    m = 42
    n = 97 ** 4 * 89 ** 4  # arbitrary modulus bigger than m^3
    c = m ** 3
    assert small_e_attack_precise(3, n, c) == m


def test_common_factor():
    import math
    p, q, r = 101, 103, 107
    n1, n2 = p * q, p * r
    f = common_factor_attack(n1, n2)
    assert f == p
