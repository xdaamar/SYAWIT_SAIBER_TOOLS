"""SYAWIT_SAIBER_TOOLS backend application."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import config
from .api import (routes_crypto, routes_jobs, routes_pwn, routes_recon,
                  routes_report, routes_setup, routes_settings, routes_shells,
                  routes_web)


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    config.PORT_FILE.write_text(str(config.PORT), encoding="utf-8")
    yield


app = FastAPI(title="SYAWIT_SAIBER_TOOLS Backend", version=config.VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://127.0.0.1", "http://localhost:*",
                   "null"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (routes_setup, routes_jobs, routes_recon, routes_web,
          routes_crypto, routes_pwn, routes_shells, routes_report, routes_settings):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "version": config.VERSION}
