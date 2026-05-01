"""Read-only settings routes for SCAFAD GUI (Phase 4).

All four endpoints are GET-only.  Phase 5 adds mutation after auth is wired
(ADR-A4-6).

Endpoints
---------
GET /api/settings          combined response (all three sub-projections)
GET /api/settings/runtime  runtime detector config + fusion weights
GET /api/settings/policy   redaction / retention policy
GET /api/settings/gui      sanitised GUI configuration snapshot
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from ..schemas import (
    GUIConfigSnapshot,
    RedactionPolicy,
    RuntimeRuntimeConfig,
    SettingsResponse,
)
from ..settings_view import (
    get_gui_config_snapshot,
    get_redaction_policy,
    get_runtime_config,
    get_settings_projection,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsResponse)
def get_settings(request: Request) -> SettingsResponse:
    """Return all three settings projections in one response."""
    settings = request.app.state.settings
    adapter = request.app.state.runtime_adapter
    return get_settings_projection(settings=settings, adapter=adapter)


@router.get("/runtime", response_model=RuntimeRuntimeConfig)
def get_settings_runtime(request: Request) -> RuntimeRuntimeConfig:
    """Return read-only runtime config (detector panel + fusion weights).

    Returns ``{available: false, ...}`` when the runtime is not yet warmed.
    """
    adapter = request.app.state.runtime_adapter
    return get_runtime_config(adapter=adapter)


@router.get("/policy", response_model=RedactionPolicy)
def get_settings_policy(request: Request) -> RedactionPolicy:  # noqa: ARG001
    """Return read-only redaction / retention policy."""
    return get_redaction_policy()


@router.get("/gui", response_model=GUIConfigSnapshot)
def get_settings_gui(request: Request) -> GUIConfigSnapshot:
    """Return sanitised GUI configuration snapshot (no secrets)."""
    settings = request.app.state.settings
    return get_gui_config_snapshot(settings=settings)
