"""Settings API: read/update settings, accept disclaimer, wordlist listing."""
from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from .. import config
from ..core.state import accept_disclaimer, is_disclaimer_accepted
from ..modules.wordlists import list_wordlists

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_settings():
    s = config.load_settings()
    # never leak absolute-ish details the UI doesn't need? keep simple: return all
    return {"settings": s, "paths": {
        "tools_dir": str(config.TOOLS_DIR),
        "wordlists_dir": str(config.WORDLISTS_DIR),
        "logs_dir": str(config.LOGS_DIR),
        "data_dir": str(config.DATA_DIR),
    }, "disclaimer_accepted": is_disclaimer_accepted()}


class SettingsBody(BaseModel):
    values: dict


@router.put("")
def put_settings(body: SettingsBody):
    allowed = set(config.DEFAULT_SETTINGS)
    update = {k: v for k, v in body.values.items() if k in allowed}
    if not update:
        return {"settings": config.load_settings(), "updated": 0}
    return {"settings": config.save_settings(update), "updated": len(update)}


@router.post("/accept-disclaimer")
def accept():
    accept_disclaimer()
    return {"disclaimer_accepted": True}


@router.get("/wordlists")
def wordlists():
    return {"wordlists": list_wordlists()}
