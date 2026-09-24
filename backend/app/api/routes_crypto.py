"""Crypto API routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.job_manager import jobs, launch_async_job
from ..modules.crypto import ciphers, hashes
from ..modules.crypto.rsa import analyze as rsa_analyze
from ..modules.crypto.solver import decode as solver_decode

router = APIRouter(prefix="/api/crypto", tags=["crypto"])


class SolveBody(BaseModel):
    text: str
    max_depth: int = 3


@router.post("/solve")
def solve(body: SolveBody):
    try:
        return solver_decode(body.text, max_depth=body.max_depth)
    except Exception as e:
        raise HTTPException(500, str(e))


class HashBody(BaseModel):
    text: str


@router.post("/hash")
def hash_all(body: HashBody):
    return hashes.all_hashes(body.text)


class IdentifyBody(BaseModel):
    digest: str


@router.post("/hash/identify")
def hash_identify(body: IdentifyBody):
    return {"candidates": hashes.identify(body.digest)}


class CrackBody(BaseModel):
    digest: str
    algo: str = "auto"
    wordlist: str | None = None


@router.post("/hash/crack")
async def hash_crack(body: CrackBody):
    return hashes.crack(body.digest, body.algo, body.wordlist)


class CipherBody(BaseModel):
    text: str
    op: str = "auto"  # auto | caesar | vigenere
    key: str = ""


@router.post("/ciphers")
def cipher_tools(body: CipherBody):
    if body.op == "caesar":
        return {"mode": "caesar_brute", "results": ciphers.caesar_brute(body.text)}
    if body.op == "vigenere" and body.key:
        return {"mode": "vigenere_decrypt", "key": body.key,
                "plaintext": ciphers.vigenere_decrypt(body.text, body.key)}
    if body.op == "vigenere":
        return ciphers.vigenere_solve(body.text)
    # auto: index of coincidence + vigenere analysis + caesar top hits
    return {
        "ioc": ciphers.index_of_coincidence(body.text),
        "vigenere": ciphers.vigenere_solve(body.text),
        "caesar_top3": ciphers.caesar_brute(body.text)[:3],
    }


class RsaBody(BaseModel):
    n: str
    e: str
    c: str | None = None
    timeout: bool = True


@router.post("/rsa/analyze")
async def rsa(body: RsaBody):
    """Run in a worker so big-n math doesn't block the event loop."""
    import asyncio

    def _run():
        return rsa_analyze(int(body.n), int(body.e), int(body.c) if body.c else None)

    try:
        result = await asyncio.to_thread(_run)
    except ValueError as e:
        raise HTTPException(400, f"nilai tidak valid: {e}")
    return result
