"""Persistent app state (disclaimer flag, setup status)."""
from __future__ import annotations

import time

from .. import config


def is_disclaimer_accepted() -> bool:
    return bool(config.load_settings().get("disclaimer_accepted", False))


def accept_disclaimer() -> None:
    config.save_settings({"disclaimer_accepted": True})


def read_setup_status() -> dict:
    return config.load_json(config.SETUP_STATUS_FILE, {})


def write_setup_status(status: dict) -> None:
    status = dict(status)
    status["updated_at"] = time.time()
    config.save_json(config.SETUP_STATUS_FILE, status)
