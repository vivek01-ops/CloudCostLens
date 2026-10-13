"""Platform metadata endpoint (does not require database access)."""

from __future__ import annotations

from core.config import get_settings
from fastapi import APIRouter

router = APIRouter(tags=["meta"])


@router.get("/meta")
def meta() -> dict[str, object]:
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "version": settings.version,
        "demo_mode": settings.demo_mode,
        "default_regions": settings.default_regions,
        "feature_flags": {
            "auth_enabled": False,  # enabled in Milestone 6
            "execution_enabled": False,
        },
    }