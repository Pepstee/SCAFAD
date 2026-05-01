"""Read-only settings introspector for SCAFAD GUI (Phase 4).

Phase 4 exposes the runtime detector configuration, redaction policy, and GUI
settings as a read-only surface.  Phase 5 will add mutation endpoints after
auth is wired (ADR-A4-6).

All functions are pure / side-effect-free and operate on already-initialised
application state objects passed in as parameters.
"""

from __future__ import annotations

import logging
from typing import Any

from .schemas import (
    DetectorEntry,
    DetectorPanel,
    FusionWeights,
    GUIConfigSnapshot,
    RedactionPolicy,
    RuntimeRuntimeConfig,
    SettingsResponse,
)

logger = logging.getLogger("scafad.gui.settings_view")


def get_gui_config_snapshot(settings: Any) -> GUIConfigSnapshot:
    """Project *settings* (a :class:`~.config.GUISettings`) into a safe DTO.

    The projection is explicit so that adding secret fields to ``GUISettings``
    in Phase 5 does not accidentally expose them through this endpoint.
    """
    return GUIConfigSnapshot(
        env=str(getattr(settings, "env", "dev")),
        host=str(getattr(settings, "host", "0.0.0.0")),
        port=int(getattr(settings, "port", 8088)),
        cors_origins=list(getattr(settings, "cors_origins", [])),
        version=str(getattr(settings, "version", "0.1.0")),
        commit=str(getattr(settings, "commit", "unknown")),
        sse_keepalive_seconds=float(getattr(settings, "sse_keepalive_seconds", 25.0)),
        db_path=str(getattr(settings, "db_path", "")),
    )


def get_runtime_config(adapter: Any) -> RuntimeRuntimeConfig:
    """Return a :class:`RuntimeRuntimeConfig` from the adapter snapshot."""
    config: dict = adapter.snapshot_config()
    available: bool = config.get("available", False)

    panel_data = config.get("detector_panel", {})
    detectors = [
        DetectorEntry(
            id=d["id"],
            weight=d.get("weight", 1.0),
            threshold=d.get("threshold"),
            last_signal_at=None,
        )
        for d in panel_data.get("detectors", [])
    ]
    detector_panel = DetectorPanel(
        available=panel_data.get("available", bool(detectors)),
        detectors=detectors,
    )

    fusion_data = config.get("fusion", {})
    fusion = FusionWeights(
        layer_weights=dict(fusion_data.get("layer_weights", {})),
        risk_band_thresholds=dict(fusion_data.get("risk_band_thresholds", {})),
    )

    return RuntimeRuntimeConfig(
        available=available,
        detector_panel=detector_panel,
        fusion=fusion,
    )


def get_redaction_policy() -> RedactionPolicy:
    """Return the active redaction policy (static in Phase 4).

    Phase 5 will read from a persistent policy table.
    """
    return RedactionPolicy(rules=[], retention_days=365)


def get_settings_projection(
    settings: Any,
    adapter: Any,
) -> SettingsResponse:
    """Compose the full :class:`SettingsResponse` from all three projections."""
    return SettingsResponse(
        runtime=get_runtime_config(adapter),
        policy=get_redaction_policy(),
        gui=get_gui_config_snapshot(settings),
    )


__all__ = [
    "get_gui_config_snapshot",
    "get_runtime_config",
    "get_redaction_policy",
    "get_settings_projection",
]
